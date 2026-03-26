"""Select entities for Victron EVSE."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHARGE_MODE_MAP, CHARGE_MODE_REVERSE_MAP, DOMAIN, REGISTER_CHARGE_MODE
from .coordinator import VictronEvseCoordinator
from .entity import VictronEvseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator: VictronEvseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VictronChargeModeSelect(coordinator)])


class VictronChargeModeSelect(VictronEvseEntity, SelectEntity):
    """Control the EVSE charge mode."""

    _attr_translation_key = "charge_mode"
    _attr_icon = "mdi:knob"

    def __init__(self, coordinator: VictronEvseCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, REGISTER_CHARGE_MODE)
        self._attr_options = list(CHARGE_MODE_MAP.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.coordinator.data.get("charge_mode_option")

    async def async_select_option(self, option: str) -> None:
        """Change the EVSE charge mode."""
        await self.coordinator.async_write_register(5009, CHARGE_MODE_REVERSE_MAP[option])
