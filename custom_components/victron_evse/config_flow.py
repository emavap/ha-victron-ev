"""Config flow for the Victron EV charger integration."""

from __future__ import annotations

import logging
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CHARGER_MODEL,
    CONF_DEVICE_UID,
    CONF_DEVICE_SERIAL,
    CONF_IDLE_SCAN_INTERVAL,
    CONF_REGISTER_PROFILE,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TIMEOUT,
    DEFAULT_IDLE_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_REGISTER_PROFILE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PROFILE_AUTO,
    PROFILE_EVCS,
    PROFILE_EVSE,
)
from .modbus import VictronEvseModbusError, VictronEvseModbusHub

_LOGGER = logging.getLogger(__name__)


def _profile_selector(default: str):
    """Build the shared register profile selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=PROFILE_AUTO, label="Auto-detect"),
                selector.SelectOptionDict(value=PROFILE_EVCS, label="EVCS"),
                selector.SelectOptionDict(value=PROFILE_EVSE, label="EVSE"),
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _number_box_selector(minimum: int, maximum: int):
    """Build a number selector shown as a numeric input box."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _normalize_host(host: str) -> str:
    """Normalize a host value for comparisons."""
    return str(host).strip().lower()


def _normalized_modbus_input(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize user-entered Modbus settings from selectors/forms."""
    normalized = dict(data)
    if CONF_HOST in normalized:
        normalized[CONF_HOST] = str(normalized[CONF_HOST]).strip()
    if CONF_PORT in normalized:
        normalized[CONF_PORT] = int(normalized[CONF_PORT])
    if CONF_SLAVE in normalized:
        normalized[CONF_SLAVE] = int(normalized[CONF_SLAVE])
    if CONF_TIMEOUT in normalized:
        normalized[CONF_TIMEOUT] = int(normalized[CONF_TIMEOUT])
    return normalized


def _network_target_matches(entry: ConfigEntry, data: dict[str, Any]) -> bool:
    """Return true when an entry points at the same network target."""
    normalized = _normalized_modbus_input(data)
    return (
        _normalize_host(entry.data.get(CONF_HOST, "")) == _normalize_host(normalized[CONF_HOST])
        and entry.data.get(CONF_PORT) == normalized[CONF_PORT]
        and entry.data.get(CONF_SLAVE) == normalized[CONF_SLAVE]
    )


def _stable_unique_id(
    serial: str | None,
    data: dict[str, Any],
    existing_entry: ConfigEntry | None = None,
) -> tuple[str, str | None]:
    """Build the stable config-entry unique ID."""
    if existing_entry is not None and existing_entry.unique_id:
        existing_uid = existing_entry.data.get(CONF_DEVICE_UID)
        if isinstance(existing_uid, str) and existing_uid:
            return existing_entry.unique_id, existing_uid
        return existing_entry.unique_id, existing_entry.unique_id.removeprefix("victron_")

    if isinstance(serial, str) and serial:
        return f"victron_{serial.lower()}", None

    normalized = _normalized_modbus_input(data)
    target = (
        f"victron-evse:{_normalize_host(normalized[CONF_HOST])}:"
        f"{normalized[CONF_PORT]}:{normalized[CONF_SLAVE]}"
    )
    device_uid = uuid5(NAMESPACE_DNS, target).hex
    return f"victron_{device_uid}", device_uid


async def validate_input(
    hass,
    data: dict[str, Any],
    existing_entry: ConfigEntry | None = None,
) -> dict[str, str | None]:
    """Validate user input by opening a Modbus session."""
    normalized = _normalized_modbus_input(data)
    hub = VictronEvseModbusHub(
        host=normalized[CONF_HOST],
        port=normalized[CONF_PORT],
        slave=normalized[CONF_SLAVE],
        timeout=normalized.get(
            CONF_TIMEOUT,
            (
                existing_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                if existing_entry is not None
                else DEFAULT_TIMEOUT
            ),
        ),
        register_profile=normalized.get(CONF_REGISTER_PROFILE, DEFAULT_REGISTER_PROFILE),
    )
    try:
        profile, device_info = await hass.async_add_executor_job(hub.detect_profile)
    except VictronEvseModbusError as err:
        _LOGGER.warning(
            "Modbus validation failed for %s:%s unit %s profile %s: %s",
            normalized[CONF_HOST],
            normalized[CONF_PORT],
            normalized[CONF_SLAVE],
            normalized.get(CONF_REGISTER_PROFILE, DEFAULT_REGISTER_PROFILE),
            err,
        )
        raise CannotConnect from err
    finally:
        await hass.async_add_executor_job(hub.close)

    serial = device_info.get(CONF_DEVICE_SERIAL)
    unique_id, device_uid = _stable_unique_id(
        serial,
        normalized,
        existing_entry,
    )
    return {
        "title": normalized.get(CONF_NAME) or f"{DEFAULT_NAME} ({normalized[CONF_HOST]})",
        "unique_id": unique_id,
        CONF_REGISTER_PROFILE: profile.key,
        CONF_CHARGER_MODEL: device_info.get(CONF_CHARGER_MODEL),
        CONF_DEVICE_SERIAL: serial,
        CONF_DEVICE_UID: device_uid,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron EV charger."""

    VERSION = 1

    def _async_abort_if_network_target_configured(
        self,
        data: dict[str, Any],
        exclude_entry_id: str | None = None,
    ) -> None:
        """Abort if another entry already uses the same network target."""
        for entry in self._async_current_entries():
            if exclude_entry_id is not None and entry.entry_id == exclude_entry_id:
                continue
            if _network_target_matches(entry, data):
                raise AbortFlow("already_configured")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                normalized_input = _normalized_modbus_input(user_input)
                self._async_abort_if_network_target_configured(normalized_input)
                info = await validate_input(self.hass, normalized_input)
            except AbortFlow:
                raise
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
                        CONF_NAME: normalized_input.get(CONF_NAME) or DEFAULT_NAME,
                        CONF_HOST: normalized_input[CONF_HOST],
                        CONF_PORT: normalized_input[CONF_PORT],
                        CONF_REGISTER_PROFILE: info[CONF_REGISTER_PROFILE],
                        CONF_SLAVE: normalized_input[CONF_SLAVE],
                        CONF_CHARGER_MODEL: info.get(CONF_CHARGER_MODEL),
                        CONF_DEVICE_SERIAL: info.get(CONF_DEVICE_SERIAL),
                        CONF_DEVICE_UID: info.get(CONF_DEVICE_UID),
                    },
                    options={
                        CONF_REGISTER_PROFILE: info[CONF_REGISTER_PROFILE],
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_IDLE_SCAN_INTERVAL: DEFAULT_IDLE_SCAN_INTERVAL,
                        CONF_TIMEOUT: normalized_input[CONF_TIMEOUT],
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
                    vol.Required(
                        CONF_REGISTER_PROFILE,
                        default=DEFAULT_REGISTER_PROFILE,
                    ): _profile_selector(DEFAULT_REGISTER_PROFILE),
                    vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): _number_box_selector(
                        1, 247
                    ),
                    vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=60)
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
                normalized_input = _normalized_modbus_input(user_input)
                self._async_abort_if_network_target_configured(
                    normalized_input,
                    exclude_entry_id=entry.entry_id,
                )
                info = await validate_input(
                    self.hass, normalized_input, existing_entry=entry
                )
            except AbortFlow:
                raise
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
                        CONF_NAME: normalized_input.get(CONF_NAME) or DEFAULT_NAME,
                        CONF_HOST: normalized_input[CONF_HOST],
                        CONF_PORT: normalized_input[CONF_PORT],
                        CONF_REGISTER_PROFILE: info[CONF_REGISTER_PROFILE],
                        CONF_SLAVE: normalized_input[CONF_SLAVE],
                        CONF_CHARGER_MODEL: info.get(CONF_CHARGER_MODEL),
                        CONF_DEVICE_SERIAL: info.get(CONF_DEVICE_SERIAL),
                        CONF_DEVICE_UID: info.get(CONF_DEVICE_UID),
                    },
                    options={
                        **entry.options,
                        CONF_REGISTER_PROFILE: info[CONF_REGISTER_PROFILE],
                        CONF_TIMEOUT: normalized_input[CONF_TIMEOUT],
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
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Required(
                        CONF_PORT,
                        default=entry.data[CONF_PORT],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Required(
                        CONF_REGISTER_PROFILE,
                        default=entry.options.get(
                            CONF_REGISTER_PROFILE,
                            entry.data.get(CONF_REGISTER_PROFILE, DEFAULT_REGISTER_PROFILE),
                        ),
                    ): _profile_selector(
                        entry.options.get(
                            CONF_REGISTER_PROFILE,
                            entry.data.get(CONF_REGISTER_PROFILE, DEFAULT_REGISTER_PROFILE),
                        )
                    ),
                    vol.Required(
                        CONF_SLAVE,
                        default=entry.data[CONF_SLAVE],
                    ): _number_box_selector(1, 247),
                    vol.Required(
                        CONF_TIMEOUT,
                        default=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
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
    """Handle options for Victron EV charger."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_REGISTER_PROFILE: user_input[CONF_REGISTER_PROFILE],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_IDLE_SCAN_INTERVAL: user_input[CONF_IDLE_SCAN_INTERVAL],
                    CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REGISTER_PROFILE,
                        default=self._config_entry.options.get(
                            CONF_REGISTER_PROFILE,
                            self._config_entry.data.get(
                                CONF_REGISTER_PROFILE, DEFAULT_REGISTER_PROFILE
                            ),
                        ),
                    ): _profile_selector(
                        self._config_entry.options.get(
                            CONF_REGISTER_PROFILE,
                            self._config_entry.data.get(
                                CONF_REGISTER_PROFILE, DEFAULT_REGISTER_PROFILE
                            ),
                        )
                    ),
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
