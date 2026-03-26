"""Config flow for the Victron EVSE integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_IDLE_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TIMEOUT,
    DEFAULT_IDLE_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .modbus import VictronEvseModbusError, VictronEvseModbusHub

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass, data: dict[str, Any]) -> dict[str, str]:
    """Validate user input by opening a Modbus session."""
    hub = VictronEvseModbusHub(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        slave=data[CONF_SLAVE],
        timeout=DEFAULT_TIMEOUT,
    )
    try:
        await hass.async_add_executor_job(hub.validate_connection)
    except VictronEvseModbusError as err:
        raise CannotConnect from err
    finally:
        await hass.async_add_executor_job(hub.close)

    host = str(data[CONF_HOST]).strip().lower()
    return {
        "title": data.get(CONF_NAME) or f"{DEFAULT_NAME} ({data[CONF_HOST]})",
        "unique_id": f"{host}:{data[CONF_PORT]}:{data[CONF_SLAVE]}",
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron EVSE."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow validation")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_SLAVE: user_input[CONF_SLAVE],
                    },
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_IDLE_SCAN_INTERVAL: DEFAULT_IDLE_SCAN_INTERVAL,
                        CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=247)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a reconfiguration flow."""
        entry = self._get_entry_from_context()
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfigure flow validation")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_mismatch(reason="already_configured")

                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=info["unique_id"],
                    title=info["title"],
                    data={
                        **entry.data,
                        CONF_NAME: user_input.get(CONF_NAME) or DEFAULT_NAME,
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_SLAVE: user_input[CONF_SLAVE],
                    },
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=entry.data.get(CONF_NAME, DEFAULT_NAME),
                    ): str,
                    vol.Required(
                        CONF_HOST,
                        default=entry.data[CONF_HOST],
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=entry.data[CONF_PORT],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Required(
                        CONF_SLAVE,
                        default=entry.data[CONF_SLAVE],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "VictronEvseOptionsFlow":
        """Return the options flow."""
        return VictronEvseOptionsFlow(config_entry)

    def _get_entry_from_context(self):
        """Return the linked config entry for reconfigure flows."""
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return None
        return self.hass.config_entries.async_get_entry(entry_id)


class VictronEvseOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Victron EVSE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self._config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_IDLE_SCAN_INTERVAL,
                        default=self._config_entry.options.get(
                            CONF_IDLE_SCAN_INTERVAL, DEFAULT_IDLE_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=1800)),
                    vol.Required(
                        CONF_TIMEOUT,
                        default=self._config_entry.options.get(
                            CONF_TIMEOUT, DEFAULT_TIMEOUT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                }
            ),
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
