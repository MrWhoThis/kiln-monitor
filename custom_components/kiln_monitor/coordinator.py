"""DataUpdateCoordinator for Kiln Monitor."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_URL,
    LOGIN_URL,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class KilnDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Kiln API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        config_data: dict[str, str],
        update_interval_minutes: int = DEFAULT_UPDATE_INTERVAL,
        kiln_info: dict[str, Any] | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="Kiln API",
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self._base_update_interval = timedelta(minutes=update_interval_minutes)
        self.session = session
        self.email = config_data[CONF_EMAIL]
        self.password = config_data[CONF_PASSWORD]
        self.token: str | None = None
        
        # If kiln_info is provided, use it; otherwise these will be set during first fetch
        if kiln_info:
            self.kiln_id: str | None = kiln_info.get("kiln_id")
            self.serial_number: str | None = kiln_info.get("serial_number")
            self.kiln_name: str | None = kiln_info.get("name", "Kiln")
        else:
            self.kiln_id: str | None = None
            self.serial_number: str | None = None
            self.kiln_name: str | None = None
            
        self._consecutive_failures = 0
        self._max_retries = 3
        self._retry_delay = 30  # seconds

    def update_interval_minutes(self, minutes: int) -> None:
        """Update the refresh interval."""
        self._base_update_interval = timedelta(minutes=minutes)
        self.update_interval = self._base_update_interval
        _LOGGER.debug("Update interval changed to %d minutes for kiln %s",
                     minutes, self.kiln_name)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        for attempt in range(self._max_retries):
            try:
                # Step 1: Ensure we have a valid token
                await self._ensure_authenticated()
                
                # Step 2: Fetch kiln data
                data = await self._fetch_kiln_data()
                
                # Reset failure counter and restore configured interval on success
                self._consecutive_failures = 0
                if self.update_interval != self._base_update_interval:
                    _LOGGER.info(
                        "Kiln %s recovered, restoring update interval to %s",
                        self.kiln_name, self._base_update_interval,
                    )
                    self.update_interval = self._base_update_interval
                return data
                
            except Exception as exc:
                self._consecutive_failures += 1
                _LOGGER.warning(
                    "Attempt %d/%d failed for kiln %s data fetch: %s", 
                    attempt + 1, self._max_retries, self.kiln_name, exc
                )
                
                # If this is a 500 error or auth issue, try to re-authenticate
                if "500" in str(exc) or "auth" in str(exc).lower():
                    _LOGGER.info("Clearing token for kiln %s due to potential auth issue", 
                               self.kiln_name)
                    self.token = None
                
                # If this isn't the last attempt, wait and retry
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)
                    continue
                
                # If we've had too many consecutive failures, back off exponentially up to 60 min
                if self._consecutive_failures >= 5:
                    current_minutes = self.update_interval.total_seconds() / 60
                    new_minutes = min(60, max(15, current_minutes * 2))
                    if new_minutes > current_minutes:
                        _LOGGER.warning(
                            "Too many consecutive failures (%d) for kiln %s, backing off update interval to %d min",
                            self._consecutive_failures, self.kiln_name, new_minutes,
                        )
                        self.update_interval = timedelta(minutes=new_minutes)
                
                raise UpdateFailed(f"Kiln API error for {self.kiln_name} after {self._max_retries} attempts: {exc}") from exc

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
                if resp.status == 401:
                    raise UpdateFailed("Invalid credentials - check email and password")
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
                
        except asyncio.TimeoutError:
            raise UpdateFailed("Login request timed out")
        except Exception as exc:
            _LOGGER.error("Authentication failed for kiln %s: %s", self.kiln_name, exc)
            raise UpdateFailed(f"Authentication error: {exc}") from exc

    async def _fetch_kiln_data(self) -> dict[str, Any]:
        """Fetch kiln data using kiln_id."""
        if not self.kiln_id:
            raise UpdateFailed(f"No kiln_id available for kiln {self.kiln_name}")
            
        data_headers = {
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
                    # Token might be expired, clear it to force re-auth
                    self.token = None
                    raise UpdateFailed("Authentication token expired during data fetch")
                elif resp.status == 404:
                    # Kiln might not exist or be accessible
                    raise UpdateFailed("Kiln not found - check if kiln is online")
                elif resp.status == 500:
                    raise UpdateFailed("Server error when fetching kiln data (status 500)")
                elif resp.status != 200:
                    raise UpdateFailed(f"Kiln data fetch failed with status {resp.status}")
                
                data = await resp.json()

            if not isinstance(data, list) or not data:
                raise UpdateFailed("Empty or invalid kiln data response")

            _LOGGER.debug("Successfully fetched data for kiln %s", self.kiln_name)
            return data[0]
            
        except asyncio.TimeoutError:
            raise UpdateFailed("Kiln data request timed out")