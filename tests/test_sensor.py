"""Tests for Victron EVSE sensor metadata."""

from custom_components.victron_evse.const import (
    NUMERIC_SENSOR_DEFAULTS,
    REGISTER_SESSION_ENERGY,
    REGISTER_TOTAL_ENERGY,
)
from homeassistant.components.sensor import SensorStateClass


def test_session_energy_sensor_has_no_invalid_state_class() -> None:
    """Session energy should not advertise an invalid energy state class."""
    assert "state_class" not in NUMERIC_SENSOR_DEFAULTS[REGISTER_SESSION_ENERGY]


def test_total_energy_sensor_keeps_total_increasing_state_class() -> None:
    """Total energy should still support statistics as a monotonically increasing value."""
    assert (
        NUMERIC_SENSOR_DEFAULTS[REGISTER_TOTAL_ENERGY]["state_class"]
        is SensorStateClass.TOTAL_INCREASING
    )
