"""Constants for the Victron EV charger integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, Platform

DOMAIN = "victron_evse"

MANUFACTURER = "Victron Energy"
MODEL = "EV Charging Station"
DEFAULT_NAME = "Victron EV Charger"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_IDLE_SCAN_INTERVAL = "idle_scan_interval"
CONF_REGISTER_PROFILE = "register_profile"
CONF_SLAVE = "slave"
CONF_TIMEOUT = "timeout"
CONF_CHARGER_MODEL = "charger_model"
CONF_DEVICE_SERIAL = "device_serial"
CONF_DEVICE_UID = "device_uid"

DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_IDLE_SCAN_INTERVAL = 180
DEFAULT_TIMEOUT = 5

PROFILE_AUTO = "auto"
PROFILE_EVCS = "evcs"
PROFILE_EVSE = "evse"
DEFAULT_REGISTER_PROFILE = PROFILE_AUTO

MIN_CURRENT = 6
MAX_CURRENT = 32

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

FAST_POLL_STATUSES = {
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    20,
    21,
    22,
    23,
    24,
}
START_STOP_AVAILABLE_STATUSES = {1, 2, 4, 5, 6, 7, 24}
CHARGING_ACTIVE_STATUSES = {2, 3}

CHARGE_MODE_MAP: dict[int, str] = {
    0: "Manual",
    1: "GX Auto",
    2: "Scheduled",
}
CHARGE_MODE_REVERSE_MAP = {value: key for key, value in CHARGE_MODE_MAP.items()}

CHARGER_STATUS_MAP_EVSE: dict[int, str] = {
    0: "Disconnected",
    1: "Connected",
    2: "Charging",
    3: "Charging Complete",
    4: "Waiting for Sun",
    5: "Waiting for RFID",
    6: "Waiting for Start",
    7: "Low SoC",
    8: "Ground Test Error",
    9: "Contactor Error",
    10: "CP Input Test Error / CP Shorted",
    11: "Residual Current Detected / Earth Leakage",
    12: "Undervoltage Detected",
    13: "Overheating Detected",
    20: "Charging Limit",
    21: "Start Charging",
    22: "Switching to 3 Phase",
    23: "Switching to 1 Phase",
    24: "Stop Charging",
}

CHARGER_STATUS_MAP_EVCS: dict[int, str] = {
    **CHARGER_STATUS_MAP_EVSE,
    10: "CP Input Test Error / CP Shorted",
    11: "Residual Current Detected / Earth Leakage",
    13: "Overvoltage Detected",
    14: "Overtemperature",
}

REGISTER_CHARGE_MODE = "charge_mode"
REGISTER_CHARGING_POWER = "charging_power"
REGISTER_CHARGER_STATUS = "charger_status"
REGISTER_MANUAL_CURRENT = "manual_current"
REGISTER_MAX_CURRENT = "max_current"
REGISTER_MIN_CURRENT = "min_current"
REGISTER_ACTUAL_CURRENT = "actual_current"
REGISTER_PRODUCT_ID = "product_id"
REGISTER_SESSION_TIME = "session_time"
REGISTER_SESSION_ENERGY = "session_energy"
REGISTER_TOTAL_ENERGY = "total_energy"
REGISTER_AUTO_START = "auto_start"
REGISTER_DETECTED_PHASES = "detected_phases"
REGISTER_SERIAL_NUMBER = "serial_number"
REGISTER_FIRMWARE_VERSION = "firmware_version"
REGISTER_CUSTOM_NAME = "custom_name"
REGISTER_CHARGER_POSITION = "charger_position"
REGISTER_DISPLAY_ENABLED = "display_enabled"

NUMERIC_SENSOR_DEFAULTS = {
    REGISTER_CHARGING_POWER: {
        "translation_key": "charging_power",
        "icon": "mdi:flash",
        "native_unit_of_measurement": "kW",
        "device_class": SensorDeviceClass.POWER,
        "suggested_display_precision": 1,
    },
    REGISTER_CHARGER_STATUS: {
        "translation_key": "charger_status_code",
        "icon": "mdi:numeric",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    REGISTER_MAX_CURRENT: {
        "translation_key": "max_charging_current",
        "icon": "mdi:current-ac",
        "native_unit_of_measurement": "A",
        "suggested_display_precision": 0,
    },
    REGISTER_MIN_CURRENT: {
        "translation_key": "min_charging_current",
        "icon": "mdi:current-ac",
        "native_unit_of_measurement": "A",
        "suggested_display_precision": 0,
    },
    REGISTER_ACTUAL_CURRENT: {
        "translation_key": "actual_charging_current",
        "icon": "mdi:current-ac",
        "native_unit_of_measurement": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "suggested_display_precision": 1,
    },
    REGISTER_SESSION_TIME: {
        "translation_key": "session_time",
        "icon": "mdi:timer-outline",
        "native_unit_of_measurement": "s",
        "device_class": SensorDeviceClass.DURATION,
        "suggested_display_precision": 0,
    },
    REGISTER_SESSION_ENERGY: {
        "translation_key": "session_energy",
        "icon": "mdi:battery-charging",
        "native_unit_of_measurement": "kWh",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 2,
    },
    REGISTER_TOTAL_ENERGY: {
        "translation_key": "total_energy",
        "icon": "mdi:counter",
        "native_unit_of_measurement": "kWh",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "suggested_display_precision": 1,
    },
    REGISTER_DETECTED_PHASES: {
        "translation_key": "detected_phases",
        "icon": "mdi:sine-wave",
        "entity_category": EntityCategory.DIAGNOSTIC,
        "suggested_display_precision": 0,
    },
    REGISTER_PRODUCT_ID: {
        "translation_key": "product_id",
        "icon": "mdi:identifier",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}

TEXT_SENSOR_DEFAULTS = {
    "charger_status_text": {
        "translation_key": "charger_status",
        "icon": "mdi:ev-station",
    },
    "session_time_hms": {
        "translation_key": "session_time_hms",
        "icon": "mdi:clock-outline",
    },
    REGISTER_SERIAL_NUMBER: {
        "translation_key": "serial_number",
        "icon": "mdi:barcode",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    REGISTER_FIRMWARE_VERSION: {
        "translation_key": "firmware_version",
        "icon": "mdi:chip",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    REGISTER_CUSTOM_NAME: {
        "translation_key": "device_custom_name",
        "icon": "mdi:rename-box",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    REGISTER_CHARGER_POSITION: {
        "translation_key": "charger_position",
        "icon": "mdi:swap-horizontal",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    CONF_REGISTER_PROFILE: {
        "translation_key": "register_profile",
        "icon": "mdi:tune-variant",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}

BINARY_SENSOR_DEFAULTS = {
    "vehicle_connected": {
        "translation_key": "vehicle_connected",
        "icon": "mdi:ev-plug-type2",
        "device_class": BinarySensorDeviceClass.PLUG,
    },
    "charging_active": {
        "translation_key": "charging_active",
        "icon": "mdi:ev-station",
        "device_class": BinarySensorDeviceClass.RUNNING,
    },
    "start_stop_available": {
        "translation_key": "start_stop_available",
        "icon": "mdi:play-circle-outline",
    },
    REGISTER_DISPLAY_ENABLED: {
        "translation_key": "display_enabled",
        "icon": "mdi:monitor",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
}
