"""Switch entities for Victron EVSE."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REGISTER_AUTO_START
from .coordinator import VictronEvseCoordinator
from .entity import VictronEvseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator: VictronEvseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            VictronChargingSwitch(coordinator),
            VictronAutoStartSwitch(coordinator),
        ]
    )


class VictronChargingSwitch(VictronEvseEntity, SwitchEntity):
    """Start or stop charging."""

    _attr_translation_key = "charging"

    def __init__(self, coordinator: VictronEvseCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "charging_switch")

    @property
    def is_on(self) -> bool:
        """Return true when charging is active."""
        return bool(self.coordinator.data.get("charging_active"))

    @property
    def available(self) -> bool:
        """Return true when start/stop control is possible."""
        return super().available and bool(self.coordinator.data.get("start_stop_available"))

    @property
    def icon(self) -> str:
        """Return a contextual icon."""
        if not self.available:
            return "mdi:minus"
        if self.is_on:
            return "mdi:stop"
        return "mdi:play"

    async def async_turn_on(self, **kwargs) -> None:
        """Start charging."""
        await self.coordinator.async_write_register(5010, 1)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop charging."""
        await self.coordinator.async_write_register(5010, 0)


class VictronAutoStartSwitch(VictronEvseEntity, SwitchEntity):
    """Control the auto-start setting."""

    _attr_translation_key = "auto_start"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, coordinator: VictronEvseCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, REGISTER_AUTO_START)

    @property
    def is_on(self) -> bool:
        """Return true when auto-start is enabled."""
        return bool(self.coordinator.data.get(REGISTER_AUTO_START))

    @property
    def available(self) -> bool:
        """Return true when the charger exposes the auto-start register."""
        return (
            super().available
            and self.coordinator.data.get(REGISTER_AUTO_START) is not None
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Enable auto-start."""
        await self.coordinator.async_write_register(5049, 1)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable auto-start."""
        await self.coordinator.async_write_register(5049, 0)
