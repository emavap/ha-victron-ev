"""Tests for Victron EVSE register parsing."""

import pytest

from custom_components.victron_evse.const import (
    CONF_CHARGER_MODEL,
    CONF_DEVICE_SERIAL,
    PROFILE_AUTO,
    PROFILE_EVCS,
    PROFILE_EVSE,
    REGISTER_CHARGER_STATUS,
)
from custom_components.victron_evse.modbus import (
    EVCS_PROFILE,
    EVSE_PROFILE,
    KNOWN_EVCS_PRODUCT_IDS,
    VictronEvseModbusError,
    VictronEvseModbusHub,
    build_data_from_registers,
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
    assert device_info["charger_position"] == "AC Input 2"


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
