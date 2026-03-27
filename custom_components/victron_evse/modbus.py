"""Modbus transport for the Victron EV charger integration."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import logging
from threading import Lock

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    CHARGE_MODE_MAP,
    CHARGER_STATUS_MAP_EVCS,
    CHARGER_STATUS_MAP_EVSE,
    CHARGING_ACTIVE_STATUSES,
    CONF_CHARGER_MODEL,
    CONF_DEVICE_SERIAL,
    CONF_REGISTER_PROFILE,
    FAST_POLL_STATUSES,
    MIN_CURRENT,
    PROFILE_AUTO,
    PROFILE_EVCS,
    PROFILE_EVSE,
    REGISTER_ACTUAL_CURRENT,
    REGISTER_AUTO_START,
    REGISTER_CHARGE_MODE,
    REGISTER_CHARGER_POSITION,
    REGISTER_CHARGER_STATUS,
    REGISTER_CHARGING_POWER,
    REGISTER_CUSTOM_NAME,
    REGISTER_DETECTED_PHASES,
    REGISTER_DISPLAY_ENABLED,
    REGISTER_DISPLAY_ENABLED_RAW,
    REGISTER_FIRMWARE_VERSION,
    REGISTER_MANUAL_CURRENT,
    REGISTER_MAX_CURRENT,
    REGISTER_MIN_CURRENT,
    REGISTER_PRODUCT_ID,
    REGISTER_SERIAL_NUMBER,
    REGISTER_SESSION_ENERGY,
    REGISTER_SESSION_TIME,
    REGISTER_TOTAL_ENERGY,
    START_STOP_AVAILABLE_STATUSES,
)

_LOGGER = logging.getLogger(__name__)


class VictronEvseModbusError(Exception):
    """Raised when the charger cannot be reached over Modbus."""


@dataclass(frozen=True)
class VictronRegisterProfile:
    """Register profile for a Victron charger family."""

    key: str
    name: str
    main_start: int
    main_count: int
    status_map: dict[int, str]
    supports_device_info: bool = False


EVSE_PROFILE = VictronRegisterProfile(
    key=PROFILE_EVSE,
    name="EVSE",
    main_start=5009,
    main_count=16,
    status_map=CHARGER_STATUS_MAP_EVSE,
)

EVCS_PROFILE = VictronRegisterProfile(
    key=PROFILE_EVCS,
    name="EVCS",
    main_start=5009,
    main_count=16,
    status_map=CHARGER_STATUS_MAP_EVCS,
    supports_device_info=True,
)

KNOWN_EVCS_PRODUCT_IDS: dict[int, str] = {
    0xC023: "EVCS 32A V2",
    0xC024: "AC22",
    0xC025: "AC22E",
    0xC026: "EVCS NS",
    0xC027: "EVCS 32A NS V2",
}


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


def decode_text(registers: list[int], little_word_order: bool = False) -> str:
    """Decode a text value from 16-bit registers."""
    raw = bytearray()
    for register in registers:
        raw.extend(register.to_bytes(2, "little" if little_word_order else "big"))
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()


def format_firmware_version(registers: list[int] | None) -> str | None:
    """Format Victron firmware registers as a dotted version."""
    if not registers or len(registers) < 2:
        return None
    value = (registers[0] << 16) | registers[1]
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def decode_display_enabled(register_value: int | None) -> bool | None:
    """Decode the display-enabled flag when the charger returns a literal boolean."""
    if register_value in (0, 1):
        return bool(register_value)
    return None


def build_data_from_registers(
    profile: VictronRegisterProfile,
    main_block: list[int],
    auto_start_register: int | None,
    min_current_register: int | None,
    detected_phases_register: int | None,
    device_info: dict[str, int | str | bool | None] | None = None,
) -> dict[str, int | float | bool | str | None]:
    """Transform raw registers into coordinator data."""
    charge_mode = main_block[0]
    charger_status = main_block[6]
    session_time = decode_uint32(main_block[10:12])
    session_energy = round(main_block[12] * 0.01, 2)
    total_energy = round(decode_uint32(main_block[14:16]) * 0.01, 1)

    info = device_info or {}

    return {
        REGISTER_CHARGE_MODE: charge_mode,
        REGISTER_CHARGING_POWER: round(main_block[5] * 0.001, 1),
        REGISTER_CHARGER_STATUS: charger_status,
        REGISTER_MANUAL_CURRENT: main_block[7],
        REGISTER_MAX_CURRENT: main_block[8],
        REGISTER_MIN_CURRENT: (
            min_current_register if min_current_register is not None else MIN_CURRENT
        ),
        REGISTER_ACTUAL_CURRENT: round(main_block[9] * 0.1, 1),
        REGISTER_SESSION_TIME: session_time,
        REGISTER_SESSION_ENERGY: session_energy,
        REGISTER_TOTAL_ENERGY: total_energy,
        REGISTER_AUTO_START: (
            bool(auto_start_register) if auto_start_register is not None else None
        ),
        REGISTER_DETECTED_PHASES: detected_phases_register,
        REGISTER_PRODUCT_ID: info.get(REGISTER_PRODUCT_ID),
        REGISTER_SERIAL_NUMBER: info.get(REGISTER_SERIAL_NUMBER),
        REGISTER_FIRMWARE_VERSION: info.get(REGISTER_FIRMWARE_VERSION),
        REGISTER_CUSTOM_NAME: info.get(REGISTER_CUSTOM_NAME),
        REGISTER_CHARGER_POSITION: info.get(REGISTER_CHARGER_POSITION),
        REGISTER_DISPLAY_ENABLED: info.get(REGISTER_DISPLAY_ENABLED),
        REGISTER_DISPLAY_ENABLED_RAW: info.get(REGISTER_DISPLAY_ENABLED_RAW),
        "charge_mode_option": CHARGE_MODE_MAP.get(charge_mode),
        "charger_status_text": profile.status_map.get(
            charger_status, f"Unknown ({charger_status})"
        ),
        "session_time_hms": format_seconds_as_hms(session_time),
        "vehicle_connected": charger_status != 0,
        "charging_active": charger_status in CHARGING_ACTIVE_STATUSES,
        "start_stop_available": charger_status in START_STOP_AVAILABLE_STATUSES
        or charger_status in CHARGING_ACTIVE_STATUSES,
        "should_poll_fast": charger_status in FAST_POLL_STATUSES,
        CONF_REGISTER_PROFILE: profile.key,
        CONF_CHARGER_MODEL: info.get(CONF_CHARGER_MODEL, profile.name),
        CONF_DEVICE_SERIAL: info.get(CONF_DEVICE_SERIAL),
    }


class VictronEvseModbusHub:
    """Thin wrapper around pymodbus for Victron EV charger registers."""

    def __init__(
        self,
        host: str,
        port: int,
        slave: int,
        timeout: int,
        register_profile: str = PROFILE_AUTO,
    ) -> None:
        """Initialize the hub."""
        self._host = host
        self._port = port
        self._slave = slave
        self._timeout = timeout
        self._register_profile_preference = register_profile
        self._active_profile: VictronRegisterProfile | None = None
        self._device_info: dict[str, int | str | bool | None] | None = None
        self._client: ModbusTcpClient | None = None
        self._lock = Lock()

    def close(self) -> None:
        """Close the underlying client."""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    def read_all(self) -> dict[str, int | float | bool | str | None]:
        """Read all supported charger registers."""
        profile, device_info = self.detect_profile()
        if profile.supports_device_info:
            device_info = self._merge_device_info(
                self._read_device_info(
                    profile,
                    product_id=device_info.get(REGISTER_PRODUCT_ID),
                )
            )
            self._device_info = device_info
        main_block = self._read_holding_registers(profile.main_start, profile.main_count)
        auto_start_register = self._read_optional_holding_register(5049)
        min_current_register = self._read_optional_holding_register(5062)
        detected_phases_register = self._read_optional_holding_register(5109)

        return build_data_from_registers(
            profile=profile,
            main_block=main_block,
            auto_start_register=auto_start_register,
            min_current_register=min_current_register,
            detected_phases_register=detected_phases_register,
            device_info=device_info,
        )

    def validate_connection(self) -> None:
        """Validate that the charger responds over Modbus."""
        self.detect_profile()

    def detect_profile(self) -> tuple[VictronRegisterProfile, dict[str, int | str | bool | None]]:
        """Determine which Victron charger register map is active."""
        if self._active_profile is not None and self._device_info is not None:
            return self._active_profile, self._device_info

        if self._register_profile_preference in (PROFILE_AUTO, PROFILE_EVCS):
            try:
                product_id = self._read_holding_registers(5000, 1)[0]
                if (
                    product_id not in (0, 0xFFFF)
                    or self._register_profile_preference == PROFILE_EVCS
                ):
                    self._active_profile = EVCS_PROFILE
                    self._device_info = self._read_device_info(
                        self._active_profile, product_id
                    )
                    return self._active_profile, self._device_info
            except VictronEvseModbusError as err:
                if self._register_profile_preference == PROFILE_EVCS:
                    raise
                _LOGGER.debug(
                    "EVCS auto-detect probe failed for %s:%s unit %s, falling back to EVSE: %s",
                    self._host,
                    self._port,
                    self._slave,
                    err,
                )

        self._read_holding_registers(EVSE_PROFILE.main_start, 1)
        self._active_profile = EVSE_PROFILE
        self._device_info = self._read_device_info(self._active_profile)
        return self._active_profile, self._device_info

    def write_register(self, address: int, value: int) -> None:
        """Write a single register."""
        with self._lock:
            client = self._ensure_client()
            try:
                response = self._call_with_device_id_fallback(
                    client.write_register,
                    operation=f"write register {address}",
                    address=address,
                    value=value,
                )
            except Exception as err:
                self._handle_transport_error(err, f"write register {address}")
            if response.isError():
                self._reset_client()
                raise VictronEvseModbusError(
                    f"Modbus write failed at address {address}: {response}"
                )

    def _read_holding_registers(self, address: int, count: int) -> list[int]:
        """Read holding registers from the charger."""
        with self._lock:
            client = self._ensure_client()
            try:
                response = self._call_with_device_id_fallback(
                    client.read_holding_registers,
                    operation=f"read holding registers {address}:{count}",
                    address=address,
                    count=count,
                )
            except Exception as err:
                self._handle_transport_error(
                    err, f"read holding registers {address}:{count}"
                )

            if response.isError():
                self._reset_client()
                raise VictronEvseModbusError(
                    f"Modbus read failed at address {address}: {response}"
                )

            return list(response.registers)

    def _read_optional_holding_register(self, address: int) -> int | None:
        """Read an optional single holding register."""
        try:
            return self._read_holding_registers(address, 1)[0]
        except VictronEvseModbusError:
            return None

    def _read_optional_holding_registers(self, address: int, count: int) -> list[int] | None:
        """Read an optional range of holding registers."""
        try:
            return self._read_holding_registers(address, count)
        except VictronEvseModbusError:
            return None

    def _read_device_info(
        self,
        profile: VictronRegisterProfile,
        product_id: int | None = None,
    ) -> dict[str, int | str | bool | None]:
        """Read optional device information registers."""
        if not profile.supports_device_info:
            return {
                CONF_CHARGER_MODEL: profile.name,
                CONF_DEVICE_SERIAL: None,
            }

        serial_registers = self._read_optional_holding_registers(5001, 6)
        firmware_registers = self._read_optional_holding_registers(5007, 2)
        position_register = self._read_optional_holding_register(5026)
        custom_name_registers = self._read_optional_holding_registers(5027, 22)
        display_enabled = self._read_optional_holding_register(5050)
        serial = decode_text(serial_registers, little_word_order=True) if serial_registers else None

        return {
            REGISTER_PRODUCT_ID: product_id,
            REGISTER_SERIAL_NUMBER: serial,
            REGISTER_FIRMWARE_VERSION: format_firmware_version(firmware_registers),
            REGISTER_CHARGER_POSITION: (
                "Output"
                if position_register == 0
                else "Input"
                if position_register == 1
                else "AC Input 2"
                if position_register == 2
                else None
            ),
            REGISTER_CUSTOM_NAME: (
                decode_text(custom_name_registers, little_word_order=True)
                if custom_name_registers
                else None
            ),
            REGISTER_DISPLAY_ENABLED: decode_display_enabled(display_enabled),
            REGISTER_DISPLAY_ENABLED_RAW: display_enabled,
            CONF_CHARGER_MODEL: KNOWN_EVCS_PRODUCT_IDS.get(
                product_id,
                f"{profile.name} (0x{product_id:04X})"
                if product_id is not None
                else profile.name,
            ),
            CONF_DEVICE_SERIAL: serial,
        }

    def _merge_device_info(
        self,
        fresh_info: dict[str, int | str | bool | None],
    ) -> dict[str, int | str | bool | None]:
        """Preserve previously discovered metadata when an optional refresh is partial."""
        if self._device_info is None:
            return fresh_info

        merged = dict(self._device_info)
        for key, value in fresh_info.items():
            if value is not None or key not in merged:
                merged[key] = value
        return merged

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
            self._handle_transport_error(err, "open TCP connection")

        if not connected:
            self._reset_client()
            raise VictronEvseModbusError(
                f"Unable to connect to {self._host}:{self._port} over Modbus TCP"
            )

        return self._client

    def _device_id_kwargs(self, method) -> dict[str, int]:
        """Return the correct slave/device_id keyword for the active pymodbus client."""
        try:
            parameters = inspect.signature(method).parameters
        except (TypeError, ValueError):
            parameters = {}

        if "device_id" in parameters:
            return {"device_id": self._slave}
        return {"slave": self._slave}

    def _call_with_device_id_fallback(self, method, operation: str, **kwargs):
        """Call a pymodbus method, retrying with the alternate unit keyword when needed."""
        unit_kwargs = self._device_id_kwargs(method)
        try:
            return method(**kwargs, **unit_kwargs)
        except TypeError as err:
            fallback_kwargs = self._alternate_device_id_kwargs(unit_kwargs)
            if (
                fallback_kwargs is None
                or not self._is_unexpected_unit_keyword_error(err, unit_kwargs)
            ):
                raise
            _LOGGER.debug(
                "Retrying %s for %s:%s unit %s with %s after keyword mismatch: %s",
                operation,
                self._host,
                self._port,
                self._slave,
                next(iter(fallback_kwargs)),
                err,
            )
            return method(**kwargs, **fallback_kwargs)

    def _alternate_device_id_kwargs(
        self, unit_kwargs: dict[str, int]
    ) -> dict[str, int] | None:
        """Return the alternate unit keyword mapping."""
        if "slave" in unit_kwargs:
            return {"device_id": unit_kwargs["slave"]}
        if "device_id" in unit_kwargs:
            return {"slave": unit_kwargs["device_id"]}
        return None

    def _is_unexpected_unit_keyword_error(
        self, err: TypeError, unit_kwargs: dict[str, int]
    ) -> bool:
        """Return true when pymodbus rejected the unit keyword name."""
        message = str(err)
        keyword = next(iter(unit_kwargs), None)
        return keyword is not None and (
            f"unexpected keyword argument '{keyword}'" in message
            or f"got an unexpected keyword argument '{keyword}'" in message
        )

    def _handle_transport_error(self, err: Exception, operation: str) -> None:
        """Reset the client and raise a normalized exception."""
        details = f"during {operation} " if operation else ""
        socket_info = self._socket_endpoints()
        self._reset_client()
        if isinstance(err, ModbusException):
            raise VictronEvseModbusError(
                f"Modbus error {details}while talking to {self._host}:{self._port}{socket_info}: {err}"
            ) from err
        raise VictronEvseModbusError(
            f"Unexpected Modbus error {details}while talking to {self._host}:{self._port}{socket_info}: "
            f"{type(err).__name__}: {err}"
        ) from err

    def _socket_endpoints(self) -> str:
        """Describe the local and remote socket endpoints when available."""
        if self._client is None or self._client.socket is None:
            return ""

        parts: list[str] = []
        try:
            local = self._client.socket.getsockname()
        except OSError:
            local = None
        if local is not None:
            parts.append(f" local={local[0]}:{local[1]}")

        try:
            remote = self._client.socket.getpeername()
        except OSError:
            remote = None
        if remote is not None:
            parts.append(f" peer={remote[0]}:{remote[1]}")

        if not parts:
            return ""
        return f" ({', '.join(parts)})"

    def _reset_client(self) -> None:
        """Reset the client after a failed request."""
        if self._client is None:
            return
        try:
            self._client.close()
        except Exception:
            _LOGGER.debug("Ignoring Modbus client close failure", exc_info=True)
        self._client = None
