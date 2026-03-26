"""Sensor platform for Victron EVSE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NUMERIC_SENSOR_DEFAULTS, TEXT_SENSOR_DEFAULTS
from .coordinator import VictronEvseCoordinator
from .entity import VictronEvseEntity
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class VictronNumericSensorDescription(SensorEntityDescription):
    """Description for numeric EVSE sensors."""

    value_key: str


@dataclass(frozen=True, kw_only=True)
class VictronTextSensorDescription(SensorEntityDescription):
    """Description for text EVSE sensors."""

    value_key: str


NUMERIC_SENSORS: tuple[VictronNumericSensorDescription, ...] = tuple(
    VictronNumericSensorDescription(
        key=key,
        value_key=key,
        **defaults,
    )
    for key, defaults in NUMERIC_SENSOR_DEFAULTS.items()
)

TEXT_SENSORS: tuple[VictronTextSensorDescription, ...] = tuple(
    VictronTextSensorDescription(
        key=key,
        value_key=key,
        **defaults,
    )
    for key, defaults in TEXT_SENSOR_DEFAULTS.items()
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: VictronEvseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [VictronNumericSensor(coordinator, description) for description in NUMERIC_SENSORS]
        + [VictronTextSensor(coordinator, description) for description in TEXT_SENSORS]
    )


class VictronNumericSensor(VictronEvseEntity, SensorEntity):
    """Representation of a numeric EVSE sensor."""

    entity_description: VictronNumericSensorDescription

    def __init__(
        self,
        coordinator: VictronEvseCoordinator,
        description: VictronNumericSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the sensor state."""
        return self.coordinator.data.get(self.entity_description.value_key)

    @property
    def available(self) -> bool:
        """Return true when the sensor data is available."""
        return (
            super().available
            and self.entity_description.value_key in self.coordinator.data
            and self.coordinator.data.get(self.entity_description.value_key) is not None
        )


class VictronTextSensor(VictronEvseEntity, SensorEntity):
    """Representation of a text EVSE sensor."""

    entity_description: VictronTextSensorDescription

    def __init__(
        self,
        coordinator: VictronEvseCoordinator,
        description: VictronTextSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        """Return the text sensor state."""
        value = self.coordinator.data.get(self.entity_description.value_key)
        return None if value is None else str(value)

    @property
    def available(self) -> bool:
        """Return true when the sensor data is available."""
        return (
            super().available
            and self.entity_description.value_key in self.coordinator.data
            and self.coordinator.data.get(self.entity_description.value_key) is not None
        )
