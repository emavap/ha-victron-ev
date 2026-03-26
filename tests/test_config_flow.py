"""Tests for the Victron EVSE config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType

from custom_components.victron_evse.const import (
    CONF_CHARGER_MODEL,
    CONF_DEVICE_SERIAL,
    CONF_IDLE_SCAN_INTERVAL,
    CONF_REGISTER_PROFILE,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_REGISTER_PROFILE,
    DEFAULT_IDLE_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PROFILE_EVCS,
)
from custom_components.victron_evse.config_flow import validate_input
from custom_components.victron_evse.modbus import EVCS_PROFILE


@pytest.mark.asyncio
async def test_user_flow_creates_entry(hass):
    """Test the user step creates a config entry."""
    with patch(
        "custom_components.victron_evse.config_flow.validate_input",
        AsyncMock(
            return_value={
                "title": "Garage Charger",
                "unique_id": "10.0.0.2:502:1",
                CONF_REGISTER_PROFILE: PROFILE_EVCS,
                CONF_CHARGER_MODEL: "EVCS 32A V2",
                CONF_DEVICE_SERIAL: "HQ123456",
            }
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Garage Charger",
                CONF_HOST: "10.0.0.2",
                CONF_PORT: 502,
                CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
                CONF_SLAVE: 1,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage Charger"
    assert result["data"] == {
        CONF_NAME: "Garage Charger",
        CONF_HOST: "10.0.0.2",
        CONF_PORT: 502,
        CONF_REGISTER_PROFILE: PROFILE_EVCS,
        CONF_SLAVE: 1,
        CONF_CHARGER_MODEL: "EVCS 32A V2",
        CONF_DEVICE_SERIAL: "HQ123456",
    }
    assert result["options"] == {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_IDLE_SCAN_INTERVAL: DEFAULT_IDLE_SCAN_INTERVAL,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
    }


@pytest.mark.asyncio
async def test_options_flow_updates_intervals(hass):
    """Test options flow stores polling settings."""
    entry = hass.config_entries.async_entries(DOMAIN)
    if entry:
        existing_entry = entry[0]
    else:
        with patch(
            "custom_components.victron_evse.config_flow.validate_input",
            AsyncMock(
                return_value={
                    "title": DEFAULT_NAME,
                    "unique_id": "10.0.0.2:502:1",
                    CONF_REGISTER_PROFILE: PROFILE_EVCS,
                    CONF_CHARGER_MODEL: "EVCS 32A V2",
                    CONF_DEVICE_SERIAL: "HQ123456",
                }
            ),
        ):
            flow = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "user"},
            )
            created = await hass.config_entries.flow.async_configure(
                flow["flow_id"],
                {
                    CONF_NAME: DEFAULT_NAME,
                    CONF_HOST: "10.0.0.2",
                    CONF_PORT: 502,
                    CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
                    CONF_SLAVE: 1,
                },
            )
        existing_entry = created["result"]

    result = await hass.config_entries.options.async_init(existing_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SCAN_INTERVAL: 15,
            CONF_IDLE_SCAN_INTERVAL: 240,
            CONF_TIMEOUT: 7,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL: 15,
        CONF_IDLE_SCAN_INTERVAL: 240,
        CONF_TIMEOUT: 7,
    }
    assert existing_entry.data[CONF_REGISTER_PROFILE] == PROFILE_EVCS


@pytest.mark.asyncio
async def test_validate_input_uses_detected_profile_and_serial_unique_id(hass):
    """Validation should persist the detected profile and stable serial identity."""
    with patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.detect_profile",
        return_value=(
            EVCS_PROFILE,
            {
                CONF_CHARGER_MODEL: "EVCS 32A V2",
                CONF_DEVICE_SERIAL: "HQ123456",
            },
        ),
    ), patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.close",
        return_value=None,
    ):
        result = await validate_input(
            hass,
            {
                CONF_NAME: "Garage Charger",
                CONF_HOST: "10.0.0.2",
                CONF_PORT: 502,
                CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
                CONF_SLAVE: 1,
            },
        )

    assert result["title"] == "Garage Charger"
    assert result["unique_id"] == "victron_hq123456"
    assert result[CONF_REGISTER_PROFILE] == PROFILE_EVCS
    assert result[CONF_CHARGER_MODEL] == "EVCS 32A V2"
    assert result[CONF_DEVICE_SERIAL] == "HQ123456"


@pytest.mark.asyncio
async def test_validate_input_falls_back_to_host_identity_without_serial(hass):
    """Validation should keep the network identity when no serial is available."""
    with patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.detect_profile",
        return_value=(
            EVCS_PROFILE,
            {
                CONF_CHARGER_MODEL: "EVCS 32A V2",
                CONF_DEVICE_SERIAL: None,
            },
        ),
    ), patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.close",
        return_value=None,
    ):
        result = await validate_input(
            hass,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_HOST: "10.0.0.2",
                CONF_PORT: 502,
                CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
                CONF_SLAVE: 1,
            },
        )

    assert result["unique_id"] == "10.0.0.2:502:1"
