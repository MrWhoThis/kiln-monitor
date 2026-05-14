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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSORS
from .coordinator import KilnDataCoordinator

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
        
        _LOGGER.info("Created %d sensors for kiln %s", 
                    len(SENSORS), coordinator.kiln_name)

    async_add_entities(sensors)


class KilnSensor(CoordinatorEntity[KilnDataCoordinator], SensorEntity):
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
    def device_info(self) -> DeviceInfo:
        """Return device information about this kiln."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial_number)},
            name=self.coordinator.kiln_name or "Kiln",
            manufacturer="Bartinst",
            model="Kiln",
            sw_version=self._get_firmware_version(),
            serial_number=self.coordinator.serial_number,
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
            
        try:
            # Navigate through the data path
            data = self.coordinator.data
            for key in self._sensor_config["data_path"]:
                data = data.get(key, {})
            
            # Convert to the specified type if value exists
            if data is not None:
                value_type = self._sensor_config["value_type"]
                if value_type == float:
                    return float(data)
                elif value_type == int:
                    return int(data)
                else:
                    return str(data)
            
            return None
            
        except (KeyError, ValueError, TypeError) as exc:
            _LOGGER.error("Failed to parse sensor %s for kiln %s: %s", 
                         self._sensor_key, self.coordinator.kiln_name, exc)
            return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success 
            and self.coordinator.data is not None
        )

    def _get_firmware_version(self) -> str | None:
        """Get firmware version from data."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("settings", {}).get("firmwareVersion")