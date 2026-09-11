"""The Kiln Monitor integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    CONF_ACTIVE_UPDATE_INTERVAL,
    CONF_IDLE_UPDATE_INTERVAL,
    DEFAULT_ACTIVE_UPDATE_INTERVAL,
    DEFAULT_IDLE_UPDATE_INTERVAL,
    ELEMENT_STORAGE_KEY,
    ELEMENT_STORAGE_VERSION,
    SETTINGS_URL,
)
from .coordinator import KilnDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.DATE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kiln Monitor from a config entry."""
    session = async_get_clientsession(hass)
    
    active_interval = entry.options.get(
        CONF_ACTIVE_UPDATE_INTERVAL, DEFAULT_ACTIVE_UPDATE_INTERVAL
    )
    idle_interval = entry.options.get(
        CONF_IDLE_UPDATE_INTERVAL, DEFAULT_IDLE_UPDATE_INTERVAL
    )

    element_store = Store(
        hass,
        ELEMENT_STORAGE_VERSION,
        f"{ELEMENT_STORAGE_KEY}.{entry.entry_id}",
    )
    stored_element_data = await element_store.async_load()
    if not isinstance(stored_element_data, dict):
        stored_element_data = {}
    stored_kilns = stored_element_data.get("kilns", {})
    if not isinstance(stored_kilns, dict):
        stored_kilns = {}

    # First, get all kilns for this account
    try:
        kilns = await _fetch_all_kilns(hass, session, entry.data)
    except Exception as exc:
        _LOGGER.error("Failed to fetch kiln list: %s", exc)
        raise ConfigEntryNotReady(f"Could not fetch kiln list: {exc}") from exc
    
    if not kilns:
        _LOGGER.error("No kilns found for this account")
        raise ConfigEntryNotReady("No kilns found for this account")
    
    _LOGGER.info("Found %d kiln(s) for account", len(kilns))

    # Create a coordinator for each kiln
    coordinators: list[KilnDataCoordinator] = []

    async def async_save_element_state() -> None:
        """Persist element dates and baselines independently of entity state."""
        kiln_states = dict(stored_kilns)
        kiln_states.update(
            {
                coordinator.serial_number: coordinator.element_tracking_state()
                for coordinator in coordinators
                if coordinator.serial_number
            }
        )
        await element_store.async_save({"kilns": kiln_states})

    for kiln_info in kilns:
        serial_number = kiln_info.get("serial_number")
        element_state = (
            stored_kilns.get(str(serial_number), {})
            if serial_number is not None
            else {}
        )
        coordinator = KilnDataCoordinator(
            hass,
            session,
            entry.data,
            active_interval_minutes=active_interval,
            idle_interval_minutes=idle_interval,
            kiln_info=kiln_info,
            element_state=element_state,
            save_element_state=async_save_element_state,
        )
        coordinators.append(coordinator)
        await coordinator.async_config_entry_first_refresh()
        await coordinator.async_initialize_element_tracking()
        
        _LOGGER.info(
            "Set up coordinator for kiln: %s (Serial: %s)", 
            kiln_info.get("name", "Unknown"), 
            kiln_info.get("serial_number", "Unknown")
        )
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators
    
    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def _fetch_all_kilns(hass: HomeAssistant, session, config_data: dict) -> list[dict]:
    """Fetch list of all kilns for the account."""
    from .coordinator import KilnDataCoordinator
    
    # Create a temporary coordinator just to authenticate and get kiln list
    temp_coordinator = KilnDataCoordinator(hass, session, config_data)
    
    # Authenticate
    await temp_coordinator._ensure_authenticated()
    
    # Fetch settings to get all kilns
    settings_headers = {
        "content-type": "application/json",
        "accept": "application/json",
        "auth-token": f"binst-cookie={temp_coordinator.token}",
        "kaid-version": "kaid-plus",
        "sec-fetch-site": "cross-site",
        "accept-language": "en-US,en;q=0.9",
        "x-app-name-token": "kiln-aid",
        "sec-fetch-mode": "cors",
        "origin": "ionic://localhost",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "email": temp_coordinator.email,
        "sec-fetch-dest": "empty"
    }
    
    async with session.post(
        SETTINGS_URL, 
        headers=settings_headers, 
        json={},
        timeout=30
    ) as resp:
        if resp.status != 200:
            raise Exception(f"Failed to fetch kiln settings: status {resp.status}")
        
        settings_data = await resp.json()
    
    if not isinstance(settings_data, list):
        raise Exception("Invalid settings response format")
    
    return settings_data


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # pop(..., None) so a failed setup (no entry stored) doesn't KeyError on unload.
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options changes."""
    coordinators: list[KilnDataCoordinator] = hass.data[DOMAIN][entry.entry_id]

    active_interval = entry.options.get(
        CONF_ACTIVE_UPDATE_INTERVAL, DEFAULT_ACTIVE_UPDATE_INTERVAL
    )
    idle_interval = entry.options.get(
        CONF_IDLE_UPDATE_INTERVAL, DEFAULT_IDLE_UPDATE_INTERVAL
    )

    for coordinator in coordinators:
        coordinator.update_intervals(active_interval, idle_interval)

    _LOGGER.info(
        "Updated Kiln Monitor intervals (active=%dm, idle=%dm) for %d kiln(s)",
        active_interval, idle_interval, len(coordinators),
    )
