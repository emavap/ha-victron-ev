"""Base entity helpers for Victron EVSE."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VictronEvseCoordinator


class VictronEvseEntity(CoordinatorEntity[VictronEvseCoordinator]):
    """Shared behavior for Victron EVSE entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VictronEvseCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id or coordinator.config_entry.entry_id}_{key}"
        )

    @property
    def device_info(self):
        """Return device info."""
        return self.coordinator.device_info
