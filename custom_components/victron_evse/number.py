"""Number entities for Victron EVSE."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_CURRENT, MIN_CURRENT, REGISTER_MANUAL_CURRENT
from .coordinator import VictronEvseCoordinator
from .entity import VictronEvseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: VictronEvseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VictronManualCurrentNumber(coordinator)])


class VictronManualCurrentNumber(VictronEvseEntity, NumberEntity):
    """Writable manual current limit."""

    _attr_translation_key = "manual_charging_current"
    _attr_icon = "mdi:current-ac"
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator: VictronEvseCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, REGISTER_MANUAL_CURRENT)

    @property
    def native_value(self) -> float | None:
        """Return the current configured manual limit."""
        value = self.coordinator.data.get(REGISTER_MANUAL_CURRENT)
        return None if value is None else float(value)

    @property
    def native_min_value(self) -> float:
        """Return the minimum allowed current."""
        return float(self.coordinator.data.get("min_current", MIN_CURRENT))

    @property
    def native_max_value(self) -> float:
        """Return the maximum allowed current."""
        return float(self.coordinator.data.get("max_current", MAX_CURRENT))

    async def async_set_native_value(self, value: float) -> None:
        """Update the manual charging current."""
        await self.coordinator.async_write_register(5016, int(value))
