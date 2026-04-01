"""Tests for the Victron EVSE coordinator."""

from datetime import timedelta

import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.victron_evse.const import (
    CONF_DEVICE_SERIAL,
    CONF_DEVICE_UID,
    CONF_IDLE_SCAN_INTERVAL,
    CONF_REGISTER_PROFILE,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PROFILE_EVCS,
)
from custom_components.victron_evse.coordinator import VictronEvseCoordinator


@pytest.mark.asyncio
async def test_coordinator_switches_between_fast_and_idle_polling(hass):
    """Polling interval should follow the current charger activity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garage Charger",
        data={
            CONF_NAME: "Garage Charger",
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SLAVE: 1,
        },
        options={
            CONF_SCAN_INTERVAL: 15,
            CONF_IDLE_SCAN_INTERVAL: 240,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        unique_id="victron_test",
    )

    coordinator = VictronEvseCoordinator(hass, entry)
    coordinator.config_entry = entry

    coordinator.hub.read_all = lambda: {"should_poll_fast": True}
    data = await coordinator._async_update_data()
    assert data["should_poll_fast"] is True
    assert coordinator.update_interval == timedelta(seconds=15)

    coordinator.hub.read_all = lambda: {"should_poll_fast": False}
    data = await coordinator._async_update_data()
    assert data["should_poll_fast"] is False
    assert coordinator.update_interval == timedelta(seconds=240)


@pytest.mark.asyncio
async def test_device_info_keeps_synthetic_identifier_when_serial_appears_later(hass):
    """A later serial discovery should not replace an existing synthetic device ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garage Charger",
        data={
            CONF_NAME: "Garage Charger",
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SLAVE: 1,
            CONF_DEVICE_UID: "synthetic-id",
        },
        options={CONF_TIMEOUT: DEFAULT_TIMEOUT},
        unique_id="victron_synthetic-id",
    )

    coordinator = VictronEvseCoordinator(hass, entry)
    coordinator.config_entry = entry
    coordinator.data = {CONF_DEVICE_SERIAL: "HQ123456"}

    assert coordinator.device_info["identifiers"] == {(DOMAIN, "synthetic-id")}
