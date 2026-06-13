"""Sensor platform for Kiln Monitor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSORS, dig
from .coordinator import KilnDataCoordinator
from .entity import KilnBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinators: list[KilnDataCoordinator] = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []

    # Create sensors for each kiln
    for coordinator in coordinators:
        for sensor_key, sensor_config in SENSORS.items():
            sensors.append(
                KilnSensor(
                    coordinator=coordinator,
                    sensor_key=sensor_key,
                    sensor_config=sensor_config,
                )
            )
        sensors.append(KilnFiringsOnCurrentElementsSensor(coordinator))

        _LOGGER.info("Created %d sensors for kiln %s",
                    len(SENSORS) + 1, coordinator.kiln_name)

    async_add_entities(sensors)


class KilnSensor(KilnBaseEntity, SensorEntity):
    """Representation of a Kiln sensor."""

    def __init__(
        self,
        coordinator: KilnDataCoordinator,
        sensor_key: str,
        sensor_config: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._sensor_config = sensor_config
        
        # Entity attributes - include kiln name for multiple kilns
        kiln_name = coordinator.kiln_name or "Kiln"
        self._attr_name = f"{kiln_name} {sensor_config['name']}"
        self._attr_unique_id = f"{coordinator.serial_number}_{sensor_key}"
        self._attr_native_unit_of_measurement = sensor_config["unit"]
        
        # Set device class if specified
        if sensor_config["device_class"] == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        
        # Set state class if specified
        if sensor_config["state_class"] == "measurement":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif sensor_config["state_class"] == "total":
            self._attr_state_class = SensorStateClass.TOTAL
        elif sensor_config["state_class"] == "total_increasing":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        data = dig(self.coordinator.data, self._sensor_config["data_path"])
        if data is None:
            return None

        try:
            value_type = self._sensor_config["value_type"]
            if value_type is float:
                return float(data)
            if value_type is int:
                return int(data)
            return str(data)
        except (ValueError, TypeError) as exc:
            _LOGGER.error("Failed to parse sensor %s for kiln %s: %s",
                         self._sensor_key, self.coordinator.kiln_name, exc)
            return None


class KilnFiringsOnCurrentElementsSensor(KilnBaseEntity, SensorEntity):
    """Read-only count of firings accumulated on the current element set.

    Derived as ``current numFirings - numFirings(at install date)``, where the
    install date comes from the "Elements installed" date entity. Shows
    "unknown" until an install date is set and recorded history covers it.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "firings_on_current_elements"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "firings"
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: KilnDataCoordinator) -> None:
        """Initialize the firings-on-current-elements sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.serial_number}_firings_on_current_elements"
        )

    @property
    def native_value(self) -> int | None:
        """Return firings accumulated on the current element set."""
        return self.coordinator.firings_on_current_elements