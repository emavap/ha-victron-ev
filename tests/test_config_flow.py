"""Tests for the Victron EVSE config flow."""

import asyncio

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.victron_evse import (
    async_setup_entry as integration_async_setup_entry,
    async_unload_entry as integration_async_unload_entry,
)
from custom_components.victron_evse.const import (
    CONF_CHARGER_MODEL,
    CONF_DEVICE_UID,
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
    PROFILE_EVSE,
)
from custom_components.victron_evse.config_flow import ConfigFlow, validate_input
from custom_components.victron_evse.modbus import EVCS_PROFILE, VictronEvseModbusError


@pytest.mark.asyncio
async def test_user_flow_creates_entry(hass):
    """Test the user step creates a config entry."""
    with patch(
        "custom_components.victron_evse.config_flow.validate_input",
        AsyncMock(
            return_value={
                "title": "Garage Charger",
                "unique_id": "victron_hq123456",
                CONF_REGISTER_PROFILE: PROFILE_EVCS,
                CONF_CHARGER_MODEL: "EVCS 32A V2",
                CONF_DEVICE_SERIAL: "HQ123456",
                CONF_DEVICE_UID: None,
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
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
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
        CONF_DEVICE_UID: None,
    }
    assert result["options"] == {
        CONF_REGISTER_PROFILE: PROFILE_EVCS,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_IDLE_SCAN_INTERVAL: DEFAULT_IDLE_SCAN_INTERVAL,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
    }


@pytest.mark.asyncio
async def test_options_flow_updates_intervals(hass):
    """Test options flow stores polling settings and persists profile changes."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
            CONF_SLAVE: 1,
        },
        options={
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_IDLE_SCAN_INTERVAL: DEFAULT_IDLE_SCAN_INTERVAL,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
        unique_id="victron_existing",
    )
    existing_entry.add_to_hass(hass)

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
        CONF_REGISTER_PROFILE: PROFILE_EVCS,
        CONF_SCAN_INTERVAL: 15,
        CONF_IDLE_SCAN_INTERVAL: 240,
        CONF_TIMEOUT: 7,
    }
    assert existing_entry.options[CONF_REGISTER_PROFILE] == PROFILE_EVCS


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
async def test_validate_input_logs_modbus_validation_failures(hass, caplog):
    """Validation failures should log actionable Modbus connection details."""
    caplog.set_level("WARNING")

    with patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.detect_profile",
        side_effect=Exception("boom"),
    ), patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.close",
        return_value=None,
    ):
        with pytest.raises(Exception, match="boom"):
            await validate_input(
                hass,
                {
                    CONF_NAME: "Garage Charger",
                    CONF_HOST: "192.168.5.48",
                    CONF_PORT: 502,
                    CONF_REGISTER_PROFILE: PROFILE_EVCS,
                    CONF_SLAVE: 1,
                },
            )

    # Sanity guard: only VictronEvseModbusError should hit the warning path.
    assert "Modbus validation failed" not in caplog.text


@pytest.mark.asyncio
async def test_validate_input_logs_victron_modbus_errors(hass, caplog):
    """Known Modbus errors should be logged with host, port, slave, and profile."""
    caplog.set_level("WARNING")

    with patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.detect_profile",
        side_effect=VictronEvseModbusError("read timeout"),
    ), patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub.close",
        return_value=None,
    ):
        with pytest.raises(Exception):
            await validate_input(
                hass,
                {
                    CONF_NAME: "Garage Charger",
                    CONF_HOST: "192.168.5.48",
                    CONF_PORT: 502,
                    CONF_REGISTER_PROFILE: PROFILE_EVCS,
                    CONF_SLAVE: 1,
                },
            )

    assert (
        "Modbus validation failed for 192.168.5.48:502 unit 1 profile evcs: read timeout"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_validate_input_falls_back_to_host_identity_without_serial(hass):
    """Validation should generate a stable synthetic identity without a serial."""
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

    assert result["unique_id"].startswith("victron_")
    assert result[CONF_DEVICE_UID] == result["unique_id"].removeprefix("victron_")


@pytest.mark.asyncio
async def test_validate_input_reuses_existing_identity_without_serial(hass):
    """Validation should preserve the existing stable identity during reconfigure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garage Charger",
        data={
            CONF_NAME: "Garage Charger",
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SLAVE: 1,
            CONF_DEVICE_UID: "existing-device-id",
        },
        unique_id="victron_existing-device-id",
    )

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
                CONF_HOST: "10.0.0.50",
                CONF_PORT: 1502,
                CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
                CONF_SLAVE: 1,
            },
            existing_entry=entry,
        )

    assert result["unique_id"] == "victron_existing-device-id"
    assert result[CONF_DEVICE_UID] == "existing-device-id"


@pytest.mark.asyncio
async def test_validate_input_uses_existing_timeout_during_reconfigure(hass):
    """Reconfigure validation should honor the entry timeout override."""
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
        options={CONF_TIMEOUT: 17},
        unique_id="victron_existing",
    )

    hub = Mock()
    hub.detect_profile.return_value = (
        EVCS_PROFILE,
        {
            CONF_CHARGER_MODEL: "EVCS 32A V2",
            CONF_DEVICE_SERIAL: "HQ123456",
        },
    )

    with patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub",
        return_value=hub,
    ) as hub_class:
        await validate_input(
            hass,
            {
                CONF_NAME: DEFAULT_NAME,
                CONF_HOST: "10.0.0.50",
                CONF_PORT: 1502,
                CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
                CONF_SLAVE: 1,
            },
            existing_entry=entry,
        )

    hub_class.assert_called_once_with(
        host="10.0.0.50",
        port=1502,
        slave=1,
        timeout=17,
        register_profile=DEFAULT_REGISTER_PROFILE,
    )


@pytest.mark.asyncio
async def test_validate_input_normalizes_selector_number_values(hass):
    """Validation should coerce selector number-box values to ints."""
    hub = Mock()
    hub.detect_profile.return_value = (
        EVCS_PROFILE,
        {
            CONF_CHARGER_MODEL: "EVCS 32A NS V2",
            CONF_DEVICE_SERIAL: "HQ123456",
        },
    )

    with patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub",
        return_value=hub,
    ) as hub_class:
        await validate_input(
            hass,
            {
                CONF_NAME: "Garage Charger",
                CONF_HOST: "192.168.5.48",
                CONF_PORT: 502,
                CONF_REGISTER_PROFILE: PROFILE_EVCS,
                CONF_SLAVE: 1.0,
                CONF_TIMEOUT: 7.0,
            },
        )

    hub_class.assert_called_once_with(
        host="192.168.5.48",
        port=502,
        slave=1,
        timeout=7,
        register_profile=PROFILE_EVCS,
    )


@pytest.mark.asyncio
async def test_validate_input_trims_host_before_connecting(hass):
    """Validation should trim pasted whitespace around the host value."""
    hub = Mock()
    hub.detect_profile.return_value = (
        EVCS_PROFILE,
        {
            CONF_CHARGER_MODEL: "EVCS NS",
            CONF_DEVICE_SERIAL: "HQ123456",
        },
    )

    with patch(
        "custom_components.victron_evse.config_flow.VictronEvseModbusHub",
        return_value=hub,
    ) as hub_class:
        result = await validate_input(
            hass,
            {
                CONF_NAME: "Garage Charger",
                CONF_HOST: " 192.168.5.48 ",
                CONF_PORT: 502,
                CONF_REGISTER_PROFILE: PROFILE_EVCS,
                CONF_SLAVE: 1,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        )

    hub_class.assert_called_once_with(
        host="192.168.5.48",
        port=502,
        slave=1,
        timeout=DEFAULT_TIMEOUT,
        register_profile=PROFILE_EVCS,
    )
    assert result["title"] == "Garage Charger"


@pytest.mark.asyncio
async def test_reconfigure_flow_updates_host_and_port(hass):
    """Reconfigure should allow changing network settings from the UI."""
    with patch(
        "custom_components.victron_evse.config_flow.validate_input",
        AsyncMock(
            return_value={
                "title": "Garage Charger",
                "unique_id": "victron_hq123456",
                CONF_REGISTER_PROFILE: PROFILE_EVSE,
                CONF_CHARGER_MODEL: "EVCS 32A V2",
                CONF_DEVICE_SERIAL: "HQ123456",
                CONF_DEVICE_UID: None,
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
                CONF_NAME: "Garage Charger",
                CONF_HOST: "10.0.0.2",
                CONF_PORT: 502,
                CONF_REGISTER_PROFILE: DEFAULT_REGISTER_PROFILE,
                CONF_SLAVE: 1,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
            },
        )

    entry = created["result"]

    with patch(
        "custom_components.victron_evse.config_flow.validate_input",
        AsyncMock(
            return_value={
                "title": "Garage Charger",
                "unique_id": "victron_hq123456",
                CONF_REGISTER_PROFILE: PROFILE_EVSE,
                CONF_CHARGER_MODEL: "EVCS 32A V2",
                CONF_DEVICE_SERIAL: "HQ123456",
                CONF_DEVICE_UID: None,
            }
        ),
    ), patch.object(
        hass.config_entries,
        "async_reload",
        AsyncMock(return_value=True),
    ), patch.object(
        ConfigFlow,
        "_get_entry_from_context",
        return_value=entry,
    ):
        flow = ConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": entry.entry_id}
        result = await flow.async_step_reconfigure()
        assert result["type"] is FlowResultType.FORM

        result = await flow.async_step_reconfigure(
            {
                CONF_NAME: "Garage Charger",
                CONF_HOST: "10.0.0.50",
                CONF_PORT: 1502,
                CONF_REGISTER_PROFILE: PROFILE_EVSE,
                CONF_SLAVE: 1,
                CONF_TIMEOUT: 11,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "10.0.0.50"
    assert entry.data[CONF_PORT] == 1502
    assert entry.data[CONF_SLAVE] == 1
    assert entry.options[CONF_REGISTER_PROFILE] == PROFILE_EVSE
    assert entry.options[CONF_TIMEOUT] == 11


@pytest.mark.asyncio
async def test_user_flow_aborts_on_duplicate_network_target(hass):
    """A duplicate host/port/slave target should be rejected before setup."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing Charger",
        data={
            CONF_NAME: "Existing Charger",
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SLAVE: 1,
        },
        unique_id="victron_existing",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Duplicate Charger",
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SLAVE: 1,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_reconfigure_flow_aborts_on_duplicate_network_target(hass):
    """Reconfigure should reject moving onto another entry's network target."""
    primary_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Primary Charger",
        data={
            CONF_NAME: "Primary Charger",
            CONF_HOST: "10.0.0.2",
            CONF_PORT: 502,
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SLAVE: 1,
        },
        unique_id="victron_primary",
    )
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other Charger",
        data={
            CONF_NAME: "Other Charger",
            CONF_HOST: "10.0.0.3",
            CONF_PORT: 1502,
            CONF_REGISTER_PROFILE: PROFILE_EVCS,
            CONF_SLAVE: 2,
        },
        unique_id="victron_other",
    )
    primary_entry.add_to_hass(hass)
    other_entry.add_to_hass(hass)

    with patch.object(
        ConfigFlow,
        "_get_entry_from_context",
        return_value=primary_entry,
    ):
        flow = ConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": primary_entry.entry_id}

        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_reconfigure(
                {
                    CONF_NAME: "Primary Charger",
                    CONF_HOST: "10.0.0.3",
                    CONF_PORT: 1502,
                    CONF_REGISTER_PROFILE: PROFILE_EVCS,
                    CONF_SLAVE: 2,
                },
            )


@pytest.mark.asyncio
async def test_async_setup_entry_cleans_up_on_platform_forward_failure(hass):
    """Coordinator resources should be cleaned up if platform forwarding fails."""
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
        unique_id="victron_test",
    )
    entry.add_to_hass(hass)

    coordinator = AsyncMock()

    with patch(
        "custom_components.victron_evse.VictronEvseCoordinator",
        return_value=coordinator,
    ), patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await integration_async_setup_entry(hass, entry)

    coordinator.async_setup.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    coordinator.async_close.assert_awaited_once()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_async_setup_entry_cleans_up_on_initial_refresh_failure(hass):
    """Coordinator resources should be cleaned up if the first refresh fails."""
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
        unique_id="victron_test",
    )
    entry.add_to_hass(hass)

    coordinator = AsyncMock()
    coordinator.async_config_entry_first_refresh.side_effect = RuntimeError("refresh failed")

    with patch(
        "custom_components.victron_evse.VictronEvseCoordinator",
        return_value=coordinator,
    ):
        with pytest.raises(RuntimeError, match="refresh failed"):
            await integration_async_setup_entry(hass, entry)

    coordinator.async_setup.assert_awaited_once()
    coordinator.async_close.assert_awaited_once()
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_async_unload_entry_cancels_retry_task_when_last_entry_is_removed(hass):
    """Background Lovelace retry tasks should be cancelled when the last entry unloads."""
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
        unique_id="victron_test",
    )
    entry.add_to_hass(hass)

    coordinator = AsyncMock()
    blocker = asyncio.Event()

    async def wait_forever():
        await blocker.wait()

    retry_task = hass.async_create_task(wait_forever())
    hass.data[DOMAIN] = {
        entry.entry_id: coordinator,
        "_resource_retry_task": retry_task,
    }

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        unload_ok = await integration_async_unload_entry(hass, entry)

    assert unload_ok is True
    await asyncio.sleep(0)
    assert retry_task.cancelled()
