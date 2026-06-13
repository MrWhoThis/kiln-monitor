"""Shared base entity and helpers for Kiln Monitor."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, dig
from .coordinator import KilnDataCoordinator


class KilnBaseEntity(CoordinatorEntity[KilnDataCoordinator]):
    """Base entity binding all Kiln Monitor entities to one kiln device."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this kiln."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial_number)},
            name=self.coordinator.kiln_name or "Kiln",
            manufacturer="Bartinst",
            model="Kiln",
            sw_version=dig(self.coordinator.data, ["settings", "firmwareVersion"]),
            serial_number=self.coordinator.serial_number,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
        )
