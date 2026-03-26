"""Tests for the Victron EVSE config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType

from custom_components.victron_evse.const import (
    CONF_IDLE_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_IDLE_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_user_flow_creates_entry(hass):
    """Test the user step creates a config entry."""
    with patch(
        "custom_components.victron_evse.config_flow.validate_input",
        AsyncMock(
            return_value={
                "title": "Garage Charger",
                "unique_id": "10.0.0.2:502:1",
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
                CONF_SLAVE: 1,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage Charger"
    assert result["data"] == {
        CONF_NAME: "Garage Charger",
        CONF_HOST: "10.0.0.2",
        CONF_PORT: 502,
        CONF_SLAVE: 1,
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
                    CONF_SLAVE: 1,
                },
            )
        existing_entry = created["result"]

    result = await hass.config_entries.options.async_init(existing_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
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
