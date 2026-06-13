"""DataUpdateCoordinator for Kiln Monitor."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_KILN_STATUSES,
    DATA_URL,
    DOMAIN,
    LOGIN_URL,
    NUMFIRINGS_DATA_PATH,
    STATUS_URL,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_ACTIVE_UPDATE_INTERVAL,
    DEFAULT_IDLE_UPDATE_INTERVAL,
    dig,
)

_LOGGER = logging.getLogger(__name__)


class KilnDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Kiln API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        config_data: dict[str, str],
        active_interval_minutes: int = DEFAULT_ACTIVE_UPDATE_INTERVAL,
        idle_interval_minutes: int = DEFAULT_IDLE_UPDATE_INTERVAL,
        kiln_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize."""
        self._active_interval = timedelta(minutes=active_interval_minutes)
        self._idle_interval = timedelta(minutes=idle_interval_minutes)
        # Start at the idle interval; first successful fetch will switch to active
        # if the kiln is firing.
        super().__init__(
            hass,
            _LOGGER,
            name="Kiln API",
            update_interval=self._idle_interval,
        )
        self.session = session
        self.email = config_data[CONF_EMAIL]
        self.password = config_data[CONF_PASSWORD]
        self.token: str | None = None
        # Element-set tracking: the user enters the install date; the baseline
        # (numFirings at that date) is derived from recorded history.
        self._installed_at: date | None = None
        self._element_baseline: int | None = None

        if kiln_info:
            self.kiln_id: str | None = kiln_info.get("kiln_id")
            self.serial_number: str | None = kiln_info.get("serial_number")
            self.kiln_name: str | None = kiln_info.get("name", "Kiln")
        else:
            self.kiln_id: str | None = None
            self.serial_number: str | None = None
            self.kiln_name: str | None = None

        self._consecutive_failures = 0

    def update_intervals(
        self, active_interval_minutes: int, idle_interval_minutes: int
    ) -> None:
        """Update the active and idle refresh intervals."""
        self._active_interval = timedelta(minutes=active_interval_minutes)
        self._idle_interval = timedelta(minutes=idle_interval_minutes)
        new_interval = self._interval_for_status(self._current_status())
        if self.update_interval != new_interval:
            self.update_interval = new_interval
        _LOGGER.debug(
            "Intervals updated for kiln %s: active=%dm idle=%dm (now using %s)",
            self.kiln_name,
            active_interval_minutes,
            idle_interval_minutes,
            new_interval,
        )

    def _current_status(self) -> Any:
        """Return the last-known kilnStatus value, or None if not yet fetched."""
        if not self.data:
            return None
        return self.data.get("list", {}).get("kilnStatus")

    def _interval_for_status(self, status: Any) -> timedelta:
        """Return the polling interval appropriate for the given kilnStatus."""
        if isinstance(status, str) and status.strip().lower() in ACTIVE_KILN_STATUSES:
            return self._active_interval
        return self._idle_interval

    # ------------------------------------------------------------------
    # Element-set tracking
    #
    # numFirings is the kiln's lifetime firing counter. The user enters the date
    # the current element set was installed; the baseline (numFirings as of that
    # date) is read back from Home Assistant's long-term statistics for the
    # numFirings sensor. "Firings on the current set" is then current - baseline.
    # The date itself is persisted by the date entity via RestoreEntity.
    # ------------------------------------------------------------------

    def current_num_firings(self) -> int | None:
        """Return the kiln's lifetime firing count, or None if not yet known."""
        value = dig(self.data, NUMFIRINGS_DATA_PATH)
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @property
    def element_installed_at(self) -> date | None:
        """Date the current element set was installed, if set."""
        return self._installed_at

    @property
    def firings_on_current_elements(self) -> int | None:
        """Firings accumulated on the current element set, or None if unknown."""
        lifetime = self.current_num_firings()
        if lifetime is None or self._element_baseline is None:
            return None
        # Guard against a baseline that ended up above the lifetime count.
        return max(0, lifetime - self._element_baseline)

    async def async_set_installed_date(self, value: date | None) -> None:
        """Set the element install date and recompute the derived baseline."""
        self._installed_at = value
        await self._async_recompute_element_baseline()
        self.async_update_listeners()

    async def _async_recompute_element_baseline(self) -> None:
        """Derive the baseline (numFirings at the install date) from history."""
        if self._installed_at is None:
            self._element_baseline = None
            return
        # Just-changed case: count from now, even before statistics compile.
        if self._installed_at >= dt_util.now().date():
            self._element_baseline = self.current_num_firings()
            return
        self._element_baseline = await self._async_num_firings_at_install()

    async def _async_num_firings_at_install(self) -> int | None:
        """Read numFirings at the start of the install date from statistics.

        Returns None when no recorded value covers that date (e.g. the date
        predates this kiln's recorded history), which surfaces as "unknown".
        """
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{self.serial_number}_numFirings"
        )
        if entity_id is None:
            return None
        day_start = dt_util.start_of_local_day(self._installed_at)
        window_start = day_start - timedelta(days=30)
        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            window_start,
            day_start,
            {entity_id},
            "hour",
            None,
            {"state"},
        )
        rows = stats.get(entity_id)
        if not rows:
            return None
        # Rows are ascending by start; the last is the value just before install.
        state = rows[-1].get("state")
        if state is None:
            return None
        try:
            return int(float(state))
        except (ValueError, TypeError):
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            await self._ensure_authenticated()
            data = await self._fetch_kiln_data()
        except ConfigEntryAuthFailed:
            # Credentials are bad — retrying won't help, surface to HA so reauth fires
            raise
        except UpdateFailed:
            self._consecutive_failures += 1
            # After repeated failures, stretch the polling interval up to 60 min
            # so we don't hammer the API. The next successful poll resets it.
            if self._consecutive_failures >= 5:
                current_minutes = self.update_interval.total_seconds() / 60
                new_minutes = min(60, max(15, current_minutes * 2))
                if new_minutes > current_minutes:
                    _LOGGER.warning(
                        "Too many consecutive failures (%d) for kiln %s, backing off update interval to %d min",
                        self._consecutive_failures, self.kiln_name, new_minutes,
                    )
                    self.update_interval = timedelta(minutes=new_minutes)
            raise

        # Reset failure counter and pick the interval that matches the kiln's
        # current status (fast while firing, slow while idle).
        self._consecutive_failures = 0
        status = data.get("list", {}).get("kilnStatus")
        desired_interval = self._interval_for_status(status)
        if self.update_interval != desired_interval:
            _LOGGER.info(
                "Kiln %s status=%s — setting update interval to %s",
                self.kiln_name, status, desired_interval,
            )
            self.update_interval = desired_interval

        return data

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        if not self.token:
            await self._authenticate()

    async def _authenticate(self) -> None:
        """Authenticate with the API and get token."""
        login_headers = {
            "Accept": "application/json",
            "kaid-version": "kaid-plus",
            "Sec-Fetch-Site": "cross-site",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Mode": "cors",
            "Content-Type": "application/json",
            "Origin": "ionic://localhost",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty"
        }

        login_payload = {
            "email": self.email,
            "password": self.password
        }

        try:
            async with self.session.post(
                LOGIN_URL, 
                headers=login_headers, 
                json=login_payload,
                timeout=30
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise ConfigEntryAuthFailed(
                        f"Invalid credentials for kiln {self.kiln_name} (status {resp.status})"
                    )
                elif resp.status == 429:
                    raise UpdateFailed("Rate limited - too many login attempts")
                elif resp.status != 200:
                    raise UpdateFailed(f"Login failed with status {resp.status}")

                auth_data = await resp.json()
                self.token = auth_data.get("authentication_token")
                if not self.token:
                    raise UpdateFailed("Token not found in login response")

                _LOGGER.debug("Successfully authenticated with Kiln API for kiln %s",
                            self.kiln_name)

        except ConfigEntryAuthFailed:
            raise
        except asyncio.TimeoutError:
            raise UpdateFailed("Login request timed out")
        except Exception as exc:
            _LOGGER.error("Authentication failed for kiln %s: %s", self.kiln_name, exc)
            raise UpdateFailed(f"Authentication error: {exc}") from exc

    def _data_headers(self) -> dict[str, str]:
        """Build the standard authenticated headers for kiln API calls."""
        return {
            "content-type": "application/json",
            "accept": "application/json",
            "auth-token": f"binst-cookie={self.token}",
            "kaid-version": "kaid-plus",
            "sec-fetch-site": "cross-site",
            "accept-language": "en-US,en;q=0.9",
            "x-app-name-token": "kiln-aid",
            "sec-fetch-mode": "cors",
            "origin": "ionic://localhost",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "email": self.email,
            "sec-fetch-dest": "empty"
        }

    async def _fetch_kiln_data(self) -> dict[str, Any]:
        """Fetch kiln data using kiln_id."""
        if not self.kiln_id:
            raise UpdateFailed(f"No kiln_id available for kiln {self.kiln_name}")

        data_headers = self._data_headers()

        data_payload = {
            "externalIds": [self.kiln_id]
        }

        try:
            async with self.session.post(
                DATA_URL, 
                headers=data_headers, 
                json=data_payload,
                timeout=30
            ) as resp:
                if resp.status == 401:
                    # Token expired; clear it so the next poll re-authenticates.
                    self.token = None
                    raise UpdateFailed("Authentication token expired during data fetch")
                if resp.status == 404:
                    raise UpdateFailed("Kiln not found - check if kiln is online")
                if resp.status >= 500:
                    # Server-side error: drop the token in case it's auth-related,
                    # the next poll will re-authenticate.
                    self.token = None
                    raise UpdateFailed(
                        f"Server error when fetching kiln data (status {resp.status})"
                    )
                if resp.status != 200:
                    raise UpdateFailed(f"Kiln data fetch failed with status {resp.status}")
                
                data = await resp.json()

            if not isinstance(data, list) or not data:
                raise UpdateFailed("Empty or invalid kiln data response")

            kiln_data = data[0]

            # Supplement with firing details (estimated time remaining, current
            # segment, set point). This is best-effort: a failure here must not
            # take down the core temperature/status sensors.
            status = await self._fetch_firing_status(data_headers)
            if status is not None:
                kiln_data["status"] = status

            _LOGGER.debug("Successfully fetched data for kiln %s", self.kiln_name)
            return kiln_data

        except UpdateFailed:
            raise
        except asyncio.TimeoutError:
            raise UpdateFailed("Kiln data request timed out")
        except Exception as exc:
            raise UpdateFailed(f"Kiln data request failed: {exc}") from exc

    async def _fetch_firing_status(
        self, data_headers: dict[str, str]
    ) -> dict[str, Any] | None:
        """Fetch firing status (estimated time remaining, segment, set point).

        Returns the status dict for this kiln, or None if it could not be
        retrieved. Unlike the main data fetch this never raises, so a hiccup on
        this secondary endpoint can't fail the whole update.
        """
        # This endpoint expects the external id as a bare string, not an array.
        status_payload = {"externalIds": self.kiln_id}

        try:
            async with self.session.post(
                STATUS_URL,
                headers=data_headers,
                json=status_payload,
                timeout=30
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "Firing status fetch for kiln %s returned status %s",
                        self.kiln_name, resp.status,
                    )
                    return None

                status_data = await resp.json()

            if not isinstance(status_data, list) or not status_data:
                _LOGGER.debug(
                    "Empty firing status response for kiln %s", self.kiln_name
                )
                return None

            return status_data[0]

        except Exception as exc:
            _LOGGER.debug(
                "Could not fetch firing status for kiln %s: %s",
                self.kiln_name, exc,
            )
            return None