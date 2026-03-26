"""Tests for Victron EVSE register parsing."""

from custom_components.victron_evse.modbus import (
    build_data_from_registers,
    decode_uint32,
    format_seconds_as_hms,
)


def test_decode_uint32():
    """Two registers should decode into a single integer."""
    assert decode_uint32([0x0001, 0x0002]) == 65538


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
