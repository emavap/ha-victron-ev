"""Tests for Victron EVSE register parsing."""

import pytest
from pymodbus.exceptions import ModbusException

from custom_components.victron_evse.const import (
    CONF_CHARGER_MODEL,
    CONF_DEVICE_SERIAL,
    PROFILE_AUTO,
    PROFILE_EVCS,
    PROFILE_EVSE,
    REGISTER_CHARGER_STATUS,
    REGISTER_CHARGER_POSITION,
    REGISTER_CUSTOM_NAME,
    REGISTER_DISPLAY_ENABLED,
    REGISTER_FIRMWARE_VERSION,
    REGISTER_PRODUCT_ID,
    REGISTER_SERIAL_NUMBER,
)
from custom_components.victron_evse.modbus import (
    EVCS_PROFILE,
    EVSE_PROFILE,
    KNOWN_EVCS_PRODUCT_IDS,
    VictronEvseModbusError,
    VictronEvseModbusHub,
    build_data_from_registers,
    decode_display_enabled,
    decode_uint32,
    format_seconds_as_hms,
)


def test_decode_uint32():
    """Two registers should decode into a single integer."""
    assert decode_uint32([0x0001, 0x0002]) == 65538


def test_decode_uint32_rejects_wrong_register_length():
    """The uint32 decoder should reject invalid register lengths."""
    with pytest.raises(ValueError, match="Expected exactly 2 registers"):
        decode_uint32([0x0001])


def test_format_seconds_as_hms():
    """Session time formatting should be stable."""
    assert format_seconds_as_hms(3661) == "01:01:01"


def test_build_data_from_registers():
    """Raw registers should map to the expected coordinator data."""
    main_block = [
        1,
        0,
        0,
        0,
        0,
        7250,
        2,
        16,
        32,
        157,
        0,
        3600,
        250,
        0,
        0,
        1234,
    ]

    data = build_data_from_registers(
        profile=EVSE_PROFILE,
        main_block=main_block,
        auto_start_register=1,
        min_current_register=6,
        detected_phases_register=3,
    )

    assert data["charge_mode"] == 1
    assert data["charge_mode_option"] == "GX Auto"
    assert data["charging_power"] == 7.2
    assert data["charger_status"] == 2
    assert data["charger_status_text"] == "Charging"
    assert data["manual_current"] == 16
    assert data["actual_current"] == 15.7
    assert data["session_time"] == 3600
    assert data["session_time_hms"] == "01:00:00"
    assert data["session_energy"] == 2.5
    assert data["total_energy"] == 12.3
    assert data["auto_start"] is True
    assert data["vehicle_connected"] is True
    assert data["charging_active"] is True


def test_build_data_from_registers_marks_optional_features_unavailable():
    """Missing optional registers should stay unavailable instead of false."""
    main_block = [
        1,
        0,
        0,
        0,
        0,
        7250,
        2,
        16,
        32,
        157,
        0,
        3600,
        250,
        0,
        0,
        1234,
    ]

    data = build_data_from_registers(
        profile=EVSE_PROFILE,
        main_block=main_block,
        auto_start_register=None,
        min_current_register=6,
        detected_phases_register=None,
        device_info={"display_enabled": None},
    )

    assert data["auto_start"] is None
    assert data["display_enabled"] is None


def test_decode_display_enabled_accepts_literal_boolean_values():
    """Only literal Modbus booleans should be mapped to a binary sensor state."""
    assert decode_display_enabled(0) is False
    assert decode_display_enabled(1) is True
    assert decode_display_enabled(65535) is None
    assert decode_display_enabled(None) is None


def test_known_product_id_maps_c026_to_evcs_ns():
    """The EVCS NS product ID should report the current model name."""
    assert KNOWN_EVCS_PRODUCT_IDS[0xC026] == "EVCS NS"


def test_build_data_marks_charging_complete_as_not_actively_charging():
    """Charging-complete status should not be treated as active charging."""
    main_block = [
        1,
        0,
        0,
        0,
        0,
        0,
        3,
        16,
        32,
        0,
        0,
        3600,
        250,
        0,
        0,
        1234,
    ]

    data = build_data_from_registers(
        profile=EVSE_PROFILE,
        main_block=main_block,
        auto_start_register=1,
        min_current_register=6,
        detected_phases_register=3,
    )

    assert data["charger_status_text"] == "Charging Complete"
    assert data["charging_active"] is False


def test_read_all_preserves_cached_device_info_on_partial_refresh(monkeypatch):
    """Refreshing EVCS metadata should not drop previously known optional values."""
    hub = VictronEvseModbusHub(
        host="10.0.0.2",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_EVCS,
    )
    cached_info = {
        REGISTER_PRODUCT_ID: 0xC023,
        REGISTER_SERIAL_NUMBER: "HQ123456",
        REGISTER_FIRMWARE_VERSION: "0.1.34.2",
        REGISTER_CHARGER_POSITION: "Output",
        REGISTER_CUSTOM_NAME: "Driveway",
        REGISTER_DISPLAY_ENABLED: True,
        CONF_CHARGER_MODEL: "EVCS 32A V2",
        CONF_DEVICE_SERIAL: "HQ123456",
    }
    main_block = [
        1,
        0,
        0,
        0,
        0,
        7250,
        2,
        16,
        32,
        157,
        0,
        3600,
        250,
        0,
        0,
        1234,
    ]

    hub._active_profile = EVCS_PROFILE
    hub._device_info = dict(cached_info)
    monkeypatch.setattr(
        hub,
        "_read_device_info",
        lambda profile, product_id=None: {
            REGISTER_PRODUCT_ID: product_id,
            REGISTER_SERIAL_NUMBER: None,
            REGISTER_FIRMWARE_VERSION: None,
            REGISTER_CHARGER_POSITION: None,
            REGISTER_CUSTOM_NAME: None,
            REGISTER_DISPLAY_ENABLED: None,
            CONF_CHARGER_MODEL: "EVCS 32A V2",
            CONF_DEVICE_SERIAL: None,
        },
    )
    monkeypatch.setattr(hub, "_read_holding_registers", lambda address, count: main_block)
    monkeypatch.setattr(
        hub,
        "_read_optional_holding_register",
        lambda address: {5049: 1, 5062: 6, 5109: 3}.get(address),
    )

    data = hub.read_all()

    assert data[REGISTER_SERIAL_NUMBER] == "HQ123456"
    assert data[REGISTER_FIRMWARE_VERSION] == "0.1.34.2"
    assert data[REGISTER_CUSTOM_NAME] == "Driveway"
    assert data[REGISTER_DISPLAY_ENABLED] is True
    assert hub._device_info[REGISTER_SERIAL_NUMBER] == "HQ123456"


def test_build_data_from_evcs_registers():
    """EVCS registers should map to EVCS-specific state semantics."""
    main_block = [
        1,
        0,
        1000,
        2000,
        3000,
        6000,
        2,
        16,
        32,
        157,
        0,
        3600,
        250,
        0,
        0,
        0,
    ]

    data = build_data_from_registers(
        profile=EVCS_PROFILE,
        main_block=main_block,
        auto_start_register=1,
        min_current_register=6,
        detected_phases_register=None,
        device_info={
            "product_id": 0xC023,
            "serial_number": "HQ123456",
            "firmware_version": "0.1.34.2",
            "custom_name": "Driveway",
            "charger_position": "Output",
            "display_enabled": True,
            "charger_model": "EVCS 32A V2",
        },
    )

    assert data["charge_mode_option"] == "GX Auto"
    assert data["session_energy"] == 2.5
    assert data["total_energy"] == 0.0
    assert data["serial_number"] == "HQ123456"
    assert data["product_id"] == 0xC023
    assert data["register_profile"] == "evcs"


def test_build_data_from_evcs_registers_uses_evcs_status_labels():
    """EVCS profile should expose EVCS-specific status text."""
    main_block = [
        1,
        0,
        0,
        0,
        0,
        6000,
        13,
        16,
        32,
        157,
        0,
        3600,
        250,
        0,
        0,
        0,
    ]

    data = build_data_from_registers(
        profile=EVCS_PROFILE,
        main_block=main_block,
        auto_start_register=1,
        min_current_register=6,
        detected_phases_register=None,
    )

    assert data[REGISTER_CHARGER_STATUS] == 13
    assert data["charger_status_text"] == "Overvoltage Detected"


def test_detect_profile_auto_selects_evcs_and_reads_device_info(monkeypatch):
    """Auto-detect should select EVCS when the product register matches."""
    hub = VictronEvseModbusHub(
        host="10.0.0.2",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    def fake_read_holding_registers(address: int, count: int) -> list[int]:
        responses: dict[tuple[int, int], list[int]] = {
            (5000, 1): [0xC023],
            (5001, 6): [0x5148, 0x3231, 0x3433, 0x3635, 0x0000, 0x0000],
            (5007, 2): [0x0001, 0x2202],
            (5027, 22): [0x7244, 0x7669, 0x7765, 0x7961] + [0] * 18,
        }
        try:
            return responses[(address, count)]
        except KeyError as err:
            raise AssertionError(f"Unexpected read {address}:{count}") from err

    monkeypatch.setattr(hub, "_read_holding_registers", fake_read_holding_registers)
    monkeypatch.setattr(hub, "_read_optional_holding_register", lambda address: {5026: 0, 5050: 1}.get(address))

    profile, device_info = hub.detect_profile()

    assert profile.key == PROFILE_EVCS
    assert device_info[CONF_CHARGER_MODEL] == KNOWN_EVCS_PRODUCT_IDS[0xC023]
    assert device_info[CONF_DEVICE_SERIAL] == "HQ123456"


def test_detect_profile_keeps_raw_display_register_when_not_boolean(monkeypatch):
    """Non-boolean display register values should stay diagnostic-only."""
    hub = VictronEvseModbusHub(
        host="10.0.0.2",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    def fake_read_holding_registers(address: int, count: int) -> list[int]:
        responses: dict[tuple[int, int], list[int]] = {
            (5000, 1): [0xC026],
            (5001, 6): [0x5148, 0x3231, 0x3433, 0x3635, 0x0000, 0x0000],
            (5007, 2): [0x0001, 0x2202],
            (5027, 22): [0] * 22,
        }
        return responses[(address, count)]

    monkeypatch.setattr(hub, "_read_holding_registers", fake_read_holding_registers)
    monkeypatch.setattr(
        hub,
        "_read_optional_holding_register",
        lambda address: {5026: 0, 5050: 65535}.get(address),
    )

    _, device_info = hub.detect_profile()

    assert device_info["display_enabled"] is None
    assert device_info["display_enabled_raw"] == 65535


def test_detect_profile_reuses_cached_evcs_device_info(monkeypatch):
    """Repeated detection should preserve the original EVCS device metadata."""
    hub = VictronEvseModbusHub(
        host="10.0.0.2",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )
    calls = 0

    def fake_read_holding_registers(address: int, count: int) -> list[int]:
        nonlocal calls
        calls += 1
        responses: dict[tuple[int, int], list[int]] = {
            (5000, 1): [0xC023],
            (5001, 6): [0x5148, 0x3231, 0x3433, 0x3635, 0x0000, 0x0000],
            (5007, 2): [0x0001, 0x2202],
            (5027, 22): [0x7244, 0x7669, 0x7765, 0x7961] + [0] * 18,
        }
        return responses[(address, count)]

    monkeypatch.setattr(hub, "_read_holding_registers", fake_read_holding_registers)
    monkeypatch.setattr(
        hub,
        "_read_optional_holding_register",
        lambda address: {5026: 0, 5050: 1}.get(address),
    )

    first_profile, first_info = hub.detect_profile()
    second_profile, second_info = hub.detect_profile()

    assert first_profile is second_profile
    assert second_info == first_info
    assert second_info["product_id"] == 0xC023
    assert calls == 4


def test_detect_profile_auto_treats_unknown_nonzero_product_as_evcs(monkeypatch):
    """Auto-detect should keep unknown EVCS product IDs on the EVCS profile."""
    hub = VictronEvseModbusHub(
        host="10.0.0.2",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    def fake_read_holding_registers(address: int, count: int) -> list[int]:
        responses: dict[tuple[int, int], list[int]] = {
            (5000, 1): [0xC099],
            (5001, 6): [0x5148, 0x3231, 0x3433, 0x3635, 0x0000, 0x0000],
            (5007, 2): [0x0001, 0x2202],
            (5027, 22): [0] * 22,
        }
        return responses[(address, count)]

    monkeypatch.setattr(hub, "_read_holding_registers", fake_read_holding_registers)
    monkeypatch.setattr(
        hub,
        "_read_optional_holding_register",
        lambda address: {5026: 2, 5050: 1}.get(address),
    )

    profile, device_info = hub.detect_profile()

    assert profile.key == PROFILE_EVCS
    assert device_info[CONF_CHARGER_MODEL] == "EVCS (0xC099)"
    assert device_info["charger_position"] is None


def test_handle_transport_error_includes_operation_and_exception_details():
    """Transport errors should preserve the failing operation and root exception."""
    hub = VictronEvseModbusHub(
        host="192.168.5.48",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    class DummyClient:
        socket = None

        def close(self):
            return None

    hub._client = DummyClient()

    with pytest.raises(
        VictronEvseModbusError,
        match=(
            "Unexpected Modbus error during read holding registers 5000:1 "
            "while talking to 192.168.5.48:502: RuntimeError: boom"
        ),
    ):
        hub._handle_transport_error(RuntimeError("boom"), "read holding registers 5000:1")


def test_handle_transport_error_preserves_modbus_exception_text():
    """Pymodbus exceptions should keep the original library error message."""
    hub = VictronEvseModbusHub(
        host="192.168.5.48",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    class DummyClient:
        socket = None

        def close(self):
            return None

    hub._client = DummyClient()

    with pytest.raises(
        VictronEvseModbusError,
        match=(
            "Modbus error during open TCP connection while talking to "
            "192.168.5.48:502: Modbus Error: failure"
        ),
    ):
        hub._handle_transport_error(ModbusException("failure"), "open TCP connection")


def test_device_id_kwargs_prefers_device_id_when_supported():
    """The hub should adapt to pymodbus versions that renamed slave to device_id."""
    hub = VictronEvseModbusHub(
        host="192.168.5.48",
        port=502,
        slave=7,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    def fake_method(*, device_id=1):
        return None

    assert hub._device_id_kwargs(fake_method) == {"device_id": 7}


def test_device_id_kwargs_falls_back_to_slave():
    """The hub should keep using slave on pymodbus versions that expect it."""
    hub = VictronEvseModbusHub(
        host="192.168.5.48",
        port=502,
        slave=7,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    def fake_method(*, slave=1):
        return None

    assert hub._device_id_kwargs(fake_method) == {"slave": 7}


def test_read_retries_with_device_id_when_slave_keyword_is_rejected(monkeypatch):
    """A slave/device_id keyword mismatch should retry with the alternate keyword."""
    hub = VictronEvseModbusHub(
        host="192.168.5.48",
        port=502,
        slave=7,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    class Response:
        registers = [0xC026]

        @staticmethod
        def isError():
            return False

    class DummyClient:
        def connect(self):
            return True

        def close(self):
            return None

        @staticmethod
        def read_holding_registers(address: int, count: int, *, device_id: int):
            assert address == 5000
            assert count == 1
            assert device_id == 7
            return Response()

    monkeypatch.setattr(hub, "_device_id_kwargs", lambda method: {"slave": 7})
    hub._client = DummyClient()

    assert hub._read_holding_registers(5000, 1) == [0xC026]


def test_write_retries_with_slave_when_device_id_keyword_is_rejected(monkeypatch):
    """The write path should also retry when pymodbus expects the other keyword."""
    hub = VictronEvseModbusHub(
        host="192.168.5.48",
        port=502,
        slave=7,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    class Response:
        @staticmethod
        def isError():
            return False

    class DummyClient:
        def connect(self):
            return True

        def close(self):
            return None

        @staticmethod
        def write_register(address: int, value: int, *, slave: int):
            assert address == 5050
            assert value == 1
            assert slave == 7
            return Response()

    monkeypatch.setattr(hub, "_device_id_kwargs", lambda method: {"device_id": 7})
    hub._client = DummyClient()

    hub.write_register(5050, 1)


def test_detect_profile_auto_falls_back_to_evse(monkeypatch):
    """Auto-detect should fall back to the legacy profile on unknown product IDs."""
    hub = VictronEvseModbusHub(
        host="10.0.0.2",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_AUTO,
    )

    def fake_read_holding_registers(address: int, count: int) -> list[int]:
        if (address, count) == (5000, 1):
            return [0x0000]
        if (address, count) == (5009, 1):
            return [1]
        raise AssertionError(f"Unexpected read {address}:{count}")

    monkeypatch.setattr(hub, "_read_holding_registers", fake_read_holding_registers)

    profile, device_info = hub.detect_profile()

    assert profile.key == PROFILE_EVSE
    assert device_info[CONF_CHARGER_MODEL] == "EVSE"
    assert device_info[CONF_DEVICE_SERIAL] is None


def test_detect_profile_forced_evcs_raises_on_product_probe_error(monkeypatch):
    """Forced EVCS profile should not silently fall back to EVSE."""
    hub = VictronEvseModbusHub(
        host="10.0.0.2",
        port=502,
        slave=1,
        timeout=5,
        register_profile=PROFILE_EVCS,
    )

    def fake_read_holding_registers(address: int, count: int) -> list[int]:
        raise VictronEvseModbusError("boom")

    monkeypatch.setattr(hub, "_read_holding_registers", fake_read_holding_registers)

    with pytest.raises(VictronEvseModbusError, match="boom"):
        hub.detect_profile()
