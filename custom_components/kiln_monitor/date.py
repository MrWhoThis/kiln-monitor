"""Date platform for Kiln Monitor (element-set install date)."""
from __future__ import annotations

import logging
from datetime import date

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import KilnDataCoordinator
from .entity import KilnBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the date platform."""
    coordinators: list[KilnDataCoordinator] = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        KilnElementInstalledDate(coordinator) for coordinator in coordinators
    )


class KilnElementInstalledDate(KilnBaseEntity, RestoreEntity, DateEntity):
    """Install date of the current element set.

    This is the single input for element tracking: enter the date the elements
    were changed and "Firings on current elements" is derived from the kiln's
    recorded firing history as of that date. Home Assistant restores the date
    across restarts via RestoreEntity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "elements_installed"
    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: KilnDataCoordinator) -> None:
        """Initialize the install-date entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_elements_installed"

    async def async_added_to_hass(self) -> None:
        """Restore the previously set install date and seed the coordinator."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (None, "unknown", "unavailable"):
            return
        try:
            restored = date.fromisoformat(last_state.state)
        except ValueError:
            return
        await self.coordinator.async_set_installed_date(restored)

    @property
    def native_value(self) -> date | None:
        """Return the stored install date."""
        return self.coordinator.element_installed_at

    async def async_set_value(self, value: date) -> None:
        """Record the date the current element set was installed."""
        await self.coordinator.async_set_installed_date(value)
