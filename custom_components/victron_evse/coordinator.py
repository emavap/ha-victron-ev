"""Coordinator for the Victron EVSE integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_IDLE_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TIMEOUT,
    DEFAULT_IDLE_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .modbus import VictronEvseModbusError, VictronEvseModbusHub

_LOGGER = logging.getLogger(__name__)


class VictronEvseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate EVSE data updates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.config_entry = entry
        self.hub = VictronEvseModbusHub(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            slave=entry.data[CONF_SLAVE],
            timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    @property
    def device_name(self) -> str:
        """Return the configured device name."""
        return self.config_entry.data.get(CONF_NAME, DEFAULT_NAME)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return static device info for all entities."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.unique_id or self.config_entry.entry_id)},
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "name": self.device_name,
            "configuration_url": f"http://{self.config_entry.data[CONF_HOST]}",
        }

    async def async_setup(self) -> None:
        """Validate initial connectivity before platform setup."""
        try:
            await self.hass.async_add_executor_job(self.hub.validate_connection)
        except VictronEvseModbusError as err:
            raise ConfigEntryNotReady(str(err)) from err

    async def async_close(self) -> None:
        """Close transport resources."""
        await self.hass.async_add_executor_job(self.hub.close)

    async def async_write_register(self, address: int, value: int) -> None:
        """Write a register and refresh state."""
        await self.hass.async_add_executor_job(self.hub.write_register, address, value)
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the charger."""
        try:
            data = await self.hass.async_add_executor_job(self.hub.read_all)
        except VictronEvseModbusError as err:
            raise UpdateFailed(str(err)) from err

        active_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        idle_interval = self.config_entry.options.get(
            CONF_IDLE_SCAN_INTERVAL, DEFAULT_IDLE_SCAN_INTERVAL
        )
        self.update_interval = timedelta(
            seconds=active_interval if data["should_poll_fast"] else idle_interval
        )
        return data
