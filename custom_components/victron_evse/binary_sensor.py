"""Binary sensors for Victron EVSE."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BINARY_SENSOR_DEFAULTS, DOMAIN
from .coordinator import VictronEvseCoordinator
from .entity import VictronEvseEntity


@dataclass(frozen=True, kw_only=True)
class VictronBinarySensorDescription(BinarySensorEntityDescription):
    """Description for binary sensors."""

    value_key: str


BINARY_SENSORS: tuple[VictronBinarySensorDescription, ...] = tuple(
    VictronBinarySensorDescription(
        key=key,
        value_key=key,
        **defaults,
    )
    for key, defaults in BINARY_SENSOR_DEFAULTS.items()
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    coordinator: VictronEvseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VictronBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class VictronBinarySensor(VictronEvseEntity, BinarySensorEntity):
    """Representation of a binary EVSE sensor."""

    entity_description: VictronBinarySensorDescription

    def __init__(
        self,
        coordinator: VictronEvseCoordinator,
        description: VictronBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return true when the sensor data is available."""
        return (
            super().available
            and self.entity_description.value_key in self.coordinator.data
            and self.coordinator.data.get(self.entity_description.value_key) is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is active."""
        value = self.coordinator.data.get(self.entity_description.value_key)
        return None if value is None else bool(value)
