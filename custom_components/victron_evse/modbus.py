"""Modbus transport for the Victron EVSE integration."""

from __future__ import annotations

import logging
from threading import Lock

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    CHARGE_MODE_MAP,
    CHARGER_STATUS_MAP,
    CHARGING_ACTIVE_STATUSES,
    FAST_POLL_STATUSES,
    REGISTER_ACTUAL_CURRENT,
    REGISTER_AUTO_START,
    REGISTER_CHARGE_MODE,
    REGISTER_CHARGER_STATUS,
    REGISTER_CHARGING_POWER,
    REGISTER_DETECTED_PHASES,
    REGISTER_MANUAL_CURRENT,
    REGISTER_MAX_CURRENT,
    REGISTER_MIN_CURRENT,
    REGISTER_SESSION_ENERGY,
    REGISTER_SESSION_TIME,
    REGISTER_TOTAL_ENERGY,
    START_STOP_AVAILABLE_STATUSES,
)

_LOGGER = logging.getLogger(__name__)


class VictronEvseModbusError(Exception):
    """Raised when the EVSE cannot be reached over Modbus."""


def decode_uint32(registers: list[int]) -> int:
    """Decode a 32-bit integer from two 16-bit registers."""
    if len(registers) != 2:
        raise ValueError("Expected exactly 2 registers for uint32 decoding")
    return (registers[0] << 16) | registers[1]


def format_seconds_as_hms(total_seconds: int | float | None) -> str:
    """Format seconds as HH:MM:SS."""
    seconds = max(0, int(total_seconds or 0))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


def build_data_from_registers(
    main_block: list[int],
    auto_start_register: int,
    min_current_register: int,
    detected_phases_register: int,
) -> dict[str, int | float | bool | str]:
    """Transform raw registers into coordinator data."""
    charge_mode = main_block[0]
    charger_status = main_block[6]
    session_time = decode_uint32(main_block[10:12])
    total_energy = decode_uint32(main_block[14:16]) * 0.01

    return {
        REGISTER_CHARGE_MODE: charge_mode,
        REGISTER_CHARGING_POWER: round(main_block[5] * 0.001, 1),
        REGISTER_CHARGER_STATUS: charger_status,
        REGISTER_MANUAL_CURRENT: main_block[7],
        REGISTER_MAX_CURRENT: main_block[8],
        REGISTER_MIN_CURRENT: min_current_register,
        REGISTER_ACTUAL_CURRENT: round(main_block[9] * 0.1, 1),
        REGISTER_SESSION_TIME: session_time,
        REGISTER_SESSION_ENERGY: round(main_block[12] * 0.01, 2),
        REGISTER_TOTAL_ENERGY: round(total_energy, 1),
        REGISTER_AUTO_START: bool(auto_start_register),
        REGISTER_DETECTED_PHASES: detected_phases_register,
        "charge_mode_option": CHARGE_MODE_MAP.get(charge_mode, f"Unknown ({charge_mode})"),
        "charger_status_text": CHARGER_STATUS_MAP.get(
            charger_status, f"Unknown ({charger_status})"
        ),
        "session_time_hms": format_seconds_as_hms(session_time),
        "vehicle_connected": charger_status != 0,
        "charging_active": charger_status in CHARGING_ACTIVE_STATUSES,
        "start_stop_available": charger_status in START_STOP_AVAILABLE_STATUSES
        or charger_status in CHARGING_ACTIVE_STATUSES,
        "should_poll_fast": charger_status in FAST_POLL_STATUSES,
    }


class VictronEvseModbusHub:
    """Thin wrapper around pymodbus for the EVSE registers."""

    def __init__(self, host: str, port: int, slave: int, timeout: int) -> None:
        """Initialize the hub."""
        self._host = host
        self._port = port
        self._slave = slave
        self._timeout = timeout
        self._client: ModbusTcpClient | None = None
        self._lock = Lock()

    def close(self) -> None:
        """Close the underlying client."""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    def read_all(self) -> dict[str, int | float | bool | str]:
        """Read all supported EVSE registers."""
        main_block = self._read_holding_registers(5009, 16)
        auto_start_register = self._read_holding_registers(5049, 1)[0]
        min_current_register = self._read_holding_registers(5062, 1)[0]
        detected_phases_register = self._read_holding_registers(5109, 1)[0]

        return build_data_from_registers(
            main_block,
            auto_start_register,
            min_current_register,
            detected_phases_register,
        )

    def validate_connection(self) -> None:
        """Validate that the EVSE responds over Modbus."""
        self._read_holding_registers(5009, 1)

    def write_register(self, address: int, value: int) -> None:
        """Write a single register."""
        with self._lock:
            client = self._ensure_client()
            try:
                response = client.write_register(address=address, value=value, slave=self._slave)
            except Exception as err:
                self._handle_transport_error(err)
            if response.isError():
                self._reset_client()
                raise VictronEvseModbusError(
                    f"Modbus write failed at address {address}: {response}"
                )

    def _read_holding_registers(self, address: int, count: int) -> list[int]:
        """Read holding registers from the EVSE."""
        with self._lock:
            client = self._ensure_client()
            try:
                response = client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=self._slave,
                )
            except Exception as err:
                self._handle_transport_error(err)

            if response.isError():
                self._reset_client()
                raise VictronEvseModbusError(
                    f"Modbus read failed at address {address}: {response}"
                )

            return list(response.registers)

    def _ensure_client(self) -> ModbusTcpClient:
        """Return a connected pymodbus client."""
        if self._client is None:
            self._client = ModbusTcpClient(
                host=self._host,
                port=self._port,
                timeout=self._timeout,
            )

        try:
            connected = self._client.connect()
        except Exception as err:
            self._handle_transport_error(err)

        if not connected:
            self._reset_client()
            raise VictronEvseModbusError(
                f"Unable to connect to {self._host}:{self._port} over Modbus TCP"
            )

        return self._client

    def _handle_transport_error(self, err: Exception) -> None:
        """Reset the client and raise a normalized exception."""
        self._reset_client()
        if isinstance(err, ModbusException):
            raise VictronEvseModbusError(str(err)) from err
        raise VictronEvseModbusError(
            f"Unexpected Modbus error while talking to {self._host}:{self._port}"
        ) from err

    def _reset_client(self) -> None:
        """Reset the client after a failed request."""
        if self._client is None:
            return
        try:
            self._client.close()
        except Exception:
            _LOGGER.debug("Ignoring Modbus client close failure", exc_info=True)
        self._client = None
