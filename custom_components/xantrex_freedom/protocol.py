"""Xantrex Freedom X / XC Bluetooth remote panel GATT protocol.

The Freedom X Bluetooth Remote Panel (Xantrex 808-0817-02) exposes one
primary service, 16-bit UUID ``0x1910``, with characteristics ``0x2A01`` to
``0x2A0E``.  Those characteristic UUIDs collide with Bluetooth SIG assigned
numbers (Appearance, Peripheral Privacy Flag, ...) but carry Xantrex data.
Every characteristic is a plain GATT read; the two settings blocks
(``0x2A0D`` and ``0x2A0E``) are written back in full after modifying the
bytes of interest.  There is no pairing, bonding or authentication.

Numeric fields are little-endian unsigned integers.  Scaling factors and
offsets follow the official Xantrex app (``com.xantrex.app`` 1.6.1).

This module must stay free of Home Assistant imports so it can be unit
tested in isolation.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum

SERVICE_UUID = "00001910-0000-1000-8000-00805f9b34fb"


def char_uuid(short: int) -> str:
    """Return the 128-bit UUID for a 16-bit characteristic id."""
    return f"0000{short:04x}-0000-1000-8000-00805f9b34fb"


CHAR_FIRMWARE = char_uuid(0x2A01)  # protocol id + firmware versions
CHAR_SERIAL = char_uuid(0x2A02)  # serial number (ASCII)
CHAR_STATUS_1 = char_uuid(0x2A03)  # working status part 1
CHAR_STATUS_2 = char_uuid(0x2A04)  # working status part 2
CHAR_RATING_1 = char_uuid(0x2A05)  # rating information 1
CHAR_RATING_2 = char_uuid(0x2A06)  # rating information 2
CHAR_RATING_3 = char_uuid(0x2A07)  # rating information 3 (model id)
CHAR_CHARGE_CURRENTS_1 = char_uuid(0x2A08)
CHAR_CHARGE_CURRENTS_2 = char_uuid(0x2A09)
CHAR_DEFAULTS_1 = char_uuid(0x2A0A)
CHAR_DEFAULTS_2 = char_uuid(0x2A0B)
CHAR_DEFAULTS_3 = char_uuid(0x2A0C)
CHAR_SETTINGS_1 = char_uuid(0x2A0D)  # settings block 1 (writable)
CHAR_SETTINGS_2 = char_uuid(0x2A0E)  # settings block 2 (writable)

ALL_CHARACTERISTICS: tuple[str, ...] = (
    CHAR_FIRMWARE,
    CHAR_SERIAL,
    CHAR_STATUS_1,
    CHAR_STATUS_2,
    CHAR_RATING_1,
    CHAR_RATING_2,
    CHAR_RATING_3,
    CHAR_CHARGE_CURRENTS_1,
    CHAR_CHARGE_CURRENTS_2,
    CHAR_DEFAULTS_1,
    CHAR_DEFAULTS_2,
    CHAR_DEFAULTS_3,
    CHAR_SETTINGS_1,
    CHAR_SETTINGS_2,
)

#: Characteristics that only change when the firmware or hardware changes.
STATIC_CHARACTERISTICS: tuple[str, ...] = (
    CHAR_FIRMWARE,
    CHAR_SERIAL,
    CHAR_RATING_1,
    CHAR_RATING_2,
    CHAR_RATING_3,
)

#: Characteristics read on every poll.
DYNAMIC_CHARACTERISTICS: tuple[str, ...] = (
    CHAR_STATUS_1,
    CHAR_STATUS_2,
    CHAR_SETTINGS_1,
    CHAR_SETTINGS_2,
)

#: Advertised local name prefix ("ID" + serial number).
LOCAL_NAME_PREFIX = "ID"


class ProtocolError(ValueError):
    """Raised when a payload cannot be decoded."""


def _u8(data: bytes, offset: int) -> int:
    try:
        return data[offset]
    except IndexError as err:
        raise ProtocolError(f"payload too short for byte {offset}") from err


def _u16(data: bytes, offset: int) -> int:
    if len(data) < offset + 2:
        raise ProtocolError(f"payload too short for uint16 at {offset}")
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if len(data) < offset + 4:
        raise ProtocolError(f"payload too short for uint32 at {offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _put_u16(buf: bytearray, offset: int, value: int) -> None:
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"{value} does not fit in uint16")
    struct.pack_into("<H", buf, offset, value)


def _ascii(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="replace").strip()


def _firmware_string(raw: bytes) -> str:
    """Decode an 8-byte firmware field.

    The app drops the first four characters (a fixed prefix) and prefixes the
    remainder with ``v``.
    """
    text = _ascii(raw)
    version = text[4:].strip()
    return f"v{version}" if version else ""


# ---------------------------------------------------------------------------
# Model table (0x2A07 byte 4)
# ---------------------------------------------------------------------------


class ModelFamily(IntEnum):
    """Product family; the X is an inverter, XC and XC PRO are inverter/chargers."""

    FX = 0
    FXC = 1
    FXC_PRO = 2


@dataclass(frozen=True)
class ModelInfo:
    """Catalogue data for one model id."""

    part_number: str
    name: str
    rated_watts: int
    specs: str
    family: ModelFamily

    @property
    def is_24v(self) -> bool:
        return "24VDC" in self.specs

    @property
    def is_high_voltage(self) -> bool:
        return "230VAC" in self.specs

    @property
    def is_charger(self) -> bool:
        return self.family is not ModelFamily.FX


_FX = ModelFamily.FX
_FXC = ModelFamily.FXC
_PRO = ModelFamily.FXC_PRO

MODELS: dict[int, ModelInfo] = {
    0x00: ModelInfo("806-1212", "Freedom X 1200", 1200, "12VDC 120VAC", _FX),
    0x01: ModelInfo("817-1000", "Freedom X 1000", 1000, "12VDC 120VAC", _FX),
    0x02: ModelInfo("817-1001", "Freedom X 1000", 1000, "12VDC 120VAC (GFCI 20A)", _FX),
    0x03: ModelInfo("817-2000", "Freedom X 2000", 2000, "12VDC 120VAC", _FX),
    0x04: ModelInfo("817-2001", "Freedom X 2000", 2000, "12VDC 120VAC (GFCI 20A)", _FX),
    0x05: ModelInfo("817-3000", "Freedom X 3000", 3000, "12VDC 120VAC", _FX),
    0x06: ModelInfo("817-3001", "Freedom X 3000", 3000, "12VDC 120VAC", _FX),
    0x07: ModelInfo("817-1050", "Freedom XC 1000", 1000, "12VDC 120VAC 50ADC", _FXC),
    0x08: ModelInfo(
        "817-1051", "Freedom XC 1000", 1000, "12VDC 120VAC 50ADC (GFCI 20A)", _FXC
    ),
    0x09: ModelInfo("817-1060", "Freedom XC+ 1000", 1000, "12VDC 120VAC 60ADC", _FXC),
    0x0A: ModelInfo(
        "817-1061", "Freedom XC+ 1000", 1000, "12VDC 120VAC 60ADC (GFCI 20A)", _FXC
    ),
    0x0B: ModelInfo("817-2080", "Freedom XC 2000", 2000, "12VDC 120VAC 80ADC", _FXC),
    0x0C: ModelInfo(
        "817-2081", "Freedom XC 2000", 2000, "12VDC 120VAC 80ADC (GFCI 20A)", _FXC
    ),
    0x0D: ModelInfo("817-2010", "Freedom XC+ 2000", 2000, "12VDC 120VAC 100ADC", _FXC),
    0x0E: ModelInfo(
        "817-2011", "Freedom XC+ 2000", 2000, "12VDC 120VAC 100ADC (GFCI 20A)", _FXC
    ),
    0x0F: ModelInfo(
        "817-1880", "Freedom XC 1800", 1800, "12VDC 120VAC 80ADC (GFCI 20A)", _FXC
    ),
    0x10: ModelInfo(
        "818-2010", "Freedom XC PRO 2000", 2000, "12VDC 120VAC 100ADC", _PRO
    ),
    0x11: ModelInfo(
        "818-2011", "Freedom XC PRO 2000", 2000, "12VDC 120VAC 100ADC (GFCI 20A)", _PRO
    ),
    0x12: ModelInfo("817-2000-21", "Freedom X 2000", 2000, "24VDC 120VAC", _FX),
    0x13: ModelInfo(
        "817-2001-21", "Freedom X 2000", 2000, "24VDC 120VAC (GFCI 20A)", _FX
    ),
    0x14: ModelInfo(
        "818-3010", "Freedom XC PRO 3000", 3000, "12VDC 120VAC 150ADC (GFCI 20A)", _PRO
    ),
    0x15: ModelInfo("817-2080-12", "Freedom XC 2000", 2000, "12VDC 230VAC 80ADC", _FXC),
    0x16: ModelInfo("817-2000-12", "Freedom X 2000", 2000, "12VDC 230VAC", _FX),
    0x17: ModelInfo(
        "817-1861-21", "Freedom XC 1800", 1800, "24VDC 120VAC 60ADC (GFCI 20A)", _FXC
    ),
    0x18: ModelInfo(
        "817-1841-21", "Freedom XC 1800", 1800, "24VDC 120VAC 40ADC (Volvo)", _FXC
    ),
    0x19: ModelInfo("817-2040-21", "Freedom XC 2000", 2000, "24VDC 120VAC 40ADC", _FXC),
    0x1A: ModelInfo(
        "817-2041-21-01", "Freedom XC 1800", 1800, "24VDC 120VAC 40ADC (Prevost)", _FXC
    ),
}

UNKNOWN_MODEL = ModelInfo("unknown", "Freedom X/XC", 0, "", ModelFamily.FX)


def model_info(model_id: int) -> ModelInfo:
    """Look up a model id, falling back to a generic entry."""
    return MODELS.get(model_id, UNKNOWN_MODEL)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class WorkingMode(str):
    """Working mode letter from 0x2A04 byte 19."""


WORKING_MODES: dict[str, str] = {
    "P": "power_on",
    "S": "standby",
    "L": "line",
    "B": "battery",
    "F": "fault",
    "H": "power_saving",
}

CHARGING_STATUS: dict[int, str] = {
    0: "not_charging",
    1: "constant_current",
    2: "constant_voltage",
    3: "float",
    4: "equalize",
    5: "rest",
}

BATTERY_TYPES: dict[int, str] = {
    0: "agm",
    1: "flooded",
    2: "gel",
    3: "custom",
    4: "lifepo4",
    5: "884",
}

BATTERY_TEMPERATURES: dict[int, str] = {0: "cold", 1: "warm", 2: "hot"}

INVERTER_IGNITION_CONTROL: dict[int, str] = {0: "off", 1: "lock_out", 2: "auto_on"}

CHARGER_IGNITION_CONTROL: dict[int, str] = {0: "off", 1: "auto_on"}

TRANSFER_MODES: dict[int, str] = {0: "appliance", 1: "ups"}

#: Warning / fault bits in 0x2A04 bytes 15-18 (uint32 little-endian).
WARNING_FLAGS: dict[str, int] = {
    "inverter_fault": 0x00000002,
    "bus_over": 0x00000004,
    "bus_under": 0x00000008,
    "bus_soft_fail": 0x00000010,
    "line_fail": 0x00000020,
    "output_short": 0x00000040,
    "inverter_voltage_low": 0x00000080,
    "inverter_voltage_high": 0x00000100,
    "over_temperature": 0x00000200,
    "fan_locked": 0x00000400,
    "battery_voltage_high": 0x00000800,
    "battery_low_alarm": 0x00001000,
    "battery_under_shutdown": 0x00004000,
    "overload": 0x00010000,
    "eeprom_fault": 0x00020000,
    "inverter_over_current": 0x00040000,
    "inverter_soft_fail": 0x00080000,
    "output_wave_fail": 0x00100000,
    "output_dc_voltage_over": 0x00200000,
    "battery_open": 0x00400000,
    "current_sensor_fail": 0x00800000,
    "battery_short": 0x01000000,
    "power_limit": 0x02000000,
    "bts_temperature": 0x04000000,
    "ntc_not_connected": 0x80000000,
}

#: Warning bits that describe a normal condition rather than a fault.
#: ``line_fail`` is simply "no AC input" and is set whenever the trailer is
#: unplugged, so it must not raise the problem sensor.
INFORMATIONAL_WARNINGS: frozenset[str] = frozenset({"line_fail"})

#: Device flag bits in 0x2A0E bytes 13-14 (and 0x2A0A bytes 12-13).
FLAG_FAULT_CODE_RECORD = 0x0001
FLAG_ALARM_ON_SOURCE_INTERRUPT = 0x0002
FLAG_BACKLIGHT = 0x0004
FLAG_OVER_TEMPERATURE_RESTART = 0x0008
FLAG_OVERLOAD_RESTART = 0x0010
FLAG_LCD_ESCAPE_TIMEOUT = 0x0020
FLAG_POWER_SAVING = 0x0040
FLAG_OVERLOAD_BYPASS = 0x0080
FLAG_AUDIBLE_ALARM = 0x0100  # named "silence buzzer" in the app; set = alarm on
FLAG_BATTERY_EQUALIZATION = 0x0200

#: 0x2A0D LBCO recovery values meaning "off" (one step past the range).
LBCO_RECOVERY_OFF_12V = 16.1
LBCO_RECOVERY_OFF_24V = 32.2


# ---------------------------------------------------------------------------
# Decoded blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Firmware:
    """0x2A01: protocol id and firmware versions."""

    protocol_id: str
    main_board: str
    remote_panel: str

    @classmethod
    def parse(cls, data: bytes) -> Firmware:
        if len(data) < 20:
            raise ProtocolError("firmware block shorter than 20 bytes")
        return cls(
            protocol_id=_ascii(data[0:2]),
            main_board=_firmware_string(data[3:11]),
            remote_panel=_firmware_string(data[12:20]),
        )


@dataclass(frozen=True)
class Identity:
    """0x2A02: serial number."""

    serial_number: str

    @classmethod
    def parse(cls, data: bytes) -> Identity:
        if not data:
            raise ProtocolError("empty serial block")
        return cls(serial_number=_ascii(data[:20]))

    @property
    def manufacturing_date(self) -> str | None:
        """YYYY-MM derived from serial characters 4-7, as the app does."""
        serial = self.serial_number
        if len(serial) >= 8 and serial[4:8].isdigit():
            return f"20{serial[4:6]}-{serial[6:8]}"
        return None


@dataclass(frozen=True)
class Status1:
    """0x2A03: working status part 1."""

    ac_input_voltage: float
    ac_input_frequency: float
    ac_output_voltage: float
    ac_output_frequency: float
    ac_output_apparent_power: int
    ac_output_power: int
    ac_output_load: int
    bus_voltage: int
    battery_voltage: float
    battery_charging_current: int

    @classmethod
    def parse(cls, data: bytes) -> Status1:
        if len(data) < 20:
            raise ProtocolError("status block 1 shorter than 20 bytes")
        return cls(
            ac_input_voltage=_u16(data, 0) / 10,
            ac_input_frequency=_u16(data, 2) / 10,
            ac_output_voltage=_u16(data, 4) / 10,
            ac_output_frequency=_u16(data, 6) / 10,
            ac_output_apparent_power=_u16(data, 8),
            ac_output_power=_u16(data, 10),
            ac_output_load=_u16(data, 12),
            bus_voltage=_u16(data, 14),
            battery_voltage=_u16(data, 16) / 100,
            battery_charging_current=_u16(data, 18),
        )


@dataclass(frozen=True)
class Status2:
    """0x2A04: working status part 2."""

    battery_capacity: int
    #: Raw temperature word.  The app labels it "heat sink temperature, C" but
    #: a Freedom X 2000 idling at ~17 C reported 578, so it is scaled and/or
    #: offset (likely ``(raw - 400) / 10`` C); left raw until confirmed.
    heat_sink_temperature: int
    ac_input_current: float
    scc_battery_voltage: int
    battery_discharge_current: int
    eeprom_version: int
    charging_status: int
    device_status: int
    warnings: int
    working_mode: str

    @classmethod
    def parse(cls, data: bytes) -> Status2:
        if len(data) < 20:
            raise ProtocolError("status block 2 shorter than 20 bytes")
        return cls(
            battery_capacity=_u16(data, 0),
            heat_sink_temperature=_u16(data, 2),
            ac_input_current=_u16(data, 4) / 10,
            scc_battery_voltage=_u16(data, 6),
            battery_discharge_current=_u16(data, 8),
            eeprom_version=_u16(data, 10),
            charging_status=_u8(data, 12),
            device_status=_u16(data, 13),
            warnings=_u32(data, 15),
            working_mode=chr(_u8(data, 19)),
        )

    @property
    def working_mode_key(self) -> str | None:
        return WORKING_MODES.get(self.working_mode)

    @property
    def charging_status_key(self) -> str | None:
        return CHARGING_STATUS.get(self.charging_status)

    @property
    def active_warnings(self) -> tuple[str, ...]:
        """Every set warning bit, including informational ones."""
        return tuple(
            name for name, mask in WARNING_FLAGS.items() if self.warnings & mask
        )

    @property
    def active_faults(self) -> tuple[str, ...]:
        """Set warning bits that indicate a real problem."""
        return tuple(
            name for name in self.active_warnings if name not in INFORMATIONAL_WARNINGS
        )

    def warning(self, name: str) -> bool:
        return bool(self.warnings & WARNING_FLAGS[name])

    @property
    def load_connected(self) -> bool:
        return bool(self.device_status & 0x0010)


@dataclass(frozen=True)
class Rating1:
    """0x2A05: rating information 1."""

    ac_input_rating_voltage: float
    ac_input_rating_current: float
    ac_output_rating_voltage: float
    ac_output_rating_frequency: float
    ac_output_rating_current: float
    ac_output_rating_apparent_power: int
    ac_output_rating_power: int
    battery_rating_voltage: float
    battery_under_voltage: float
    battery_bulk_voltage: float

    @classmethod
    def parse(cls, data: bytes) -> Rating1:
        if len(data) < 20:
            raise ProtocolError("rating block 1 shorter than 20 bytes")
        return cls(
            ac_input_rating_voltage=_u16(data, 0) / 10,
            ac_input_rating_current=_u16(data, 2) / 10,
            ac_output_rating_voltage=_u16(data, 4) / 10,
            ac_output_rating_frequency=_u16(data, 6) / 10,
            ac_output_rating_current=_u16(data, 8) / 10,
            ac_output_rating_apparent_power=_u16(data, 10),
            ac_output_rating_power=_u16(data, 12),
            battery_rating_voltage=_u16(data, 14) / 10,
            battery_under_voltage=_u16(data, 16) / 10,
            battery_bulk_voltage=_u16(data, 18) / 10,
        )


@dataclass(frozen=True)
class Rating2:
    """0x2A06: rating information 2."""

    battery_float_voltage: float
    battery_type: int
    max_ac_charging_current: int
    input_voltage_range: int
    power_save_time: int
    lbco_delay_time: int
    ignition_setting: int
    lbco_recovery_voltage: float
    power_limit: int
    power_limit_timer: int
    utility_low_loss_voltage: float
    battery_temperature: int
    charger_stage: int

    @classmethod
    def parse(cls, data: bytes) -> Rating2:
        if len(data) < 20:
            raise ProtocolError("rating block 2 shorter than 20 bytes")
        return cls(
            battery_float_voltage=_u16(data, 0) / 10,
            battery_type=_u8(data, 2),
            max_ac_charging_current=_u16(data, 3),
            input_voltage_range=_u8(data, 5),
            power_save_time=_u8(data, 6),
            lbco_delay_time=_u16(data, 7),
            ignition_setting=_u8(data, 9),
            lbco_recovery_voltage=_u16(data, 10) / 10,
            power_limit=_u16(data, 12) * 100,
            power_limit_timer=_u16(data, 14),
            utility_low_loss_voltage=_u16(data, 16) / 10,
            battery_temperature=_u8(data, 18),
            charger_stage=_u8(data, 19),
        )


@dataclass(frozen=True)
class Rating3:
    """0x2A07: rating information 3 (model id, comm-board firmware)."""

    charger_ignition_control: int
    equalize_charge: int
    electronic_breaker_current: int
    model_id: int
    comm_firmware: str

    @classmethod
    def parse(cls, data: bytes) -> Rating3:
        if len(data) < 5:
            raise ProtocolError("rating block 3 shorter than 5 bytes")
        comm = _firmware_string(data[5:13]) if len(data) >= 13 else ""
        return cls(
            charger_ignition_control=_u8(data, 0),
            equalize_charge=_u8(data, 1),
            electronic_breaker_current=_u8(data, 2),
            model_id=_u8(data, 4),
            comm_firmware=comm,
        )

    @property
    def model(self) -> ModelInfo:
        return model_info(self.model_id)


@dataclass(frozen=True)
class Settings1:
    """0x2A0D: settings block 1."""

    raw: bytes
    inverter_ignition_control: int
    lbco_voltage: float
    lbco_delay_timer: int
    lbco_recovery_voltage: float
    power_save_time: int
    power_save_mode: int
    output_frequency: float
    output_voltage: int
    output_power_limit_raw: int
    output_power_limit_timer: int
    transfer_mode: int
    utility_under_voltage: int

    @classmethod
    def parse(cls, data: bytes) -> Settings1:
        if len(data) < 20:
            raise ProtocolError("settings block 1 shorter than 20 bytes")
        return cls(
            raw=bytes(data),
            inverter_ignition_control=_u8(data, 0),
            lbco_voltage=_u16(data, 1) / 10,
            lbco_delay_timer=_u16(data, 3),
            lbco_recovery_voltage=_u16(data, 5) / 10,
            power_save_time=_u8(data, 7),
            power_save_mode=_u8(data, 8),
            output_frequency=_u16(data, 9) / 10,
            output_voltage=_u16(data, 11),
            output_power_limit_raw=_u16(data, 13),
            output_power_limit_timer=_u16(data, 15),
            transfer_mode=_u8(data, 17),
            utility_under_voltage=_u16(data, 18),
        )

    @property
    def output_power_limit(self) -> int:
        """Output power limit in watts (the device stores hundreds of watts).

        Confirmed on a Freedom X 2000: raw 20 with the limit at 2000 W.  The
        Xantrex app writes plain watts here, which the device clamps.
        """
        return self.output_power_limit_raw * 100

    @property
    def lbco_recovery_off(self) -> bool:
        return self.lbco_recovery_voltage in (
            LBCO_RECOVERY_OFF_12V,
            LBCO_RECOVERY_OFF_24V,
        )

    # -- encoders -----------------------------------------------------------

    def _buffer(self) -> bytearray:
        return bytearray(self.raw)

    def with_inverter_ignition_control(self, value: int) -> bytes:
        if value not in INVERTER_IGNITION_CONTROL:
            raise ValueError("invalid ignition control")
        buf = self._buffer()
        buf[0] = value
        return bytes(buf)

    def with_lbco_voltage(self, volts: float) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 1, round(volts * 10))
        return bytes(buf)

    def with_lbco_delay_timer(self, seconds: int) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 3, int(seconds))
        return bytes(buf)

    def with_lbco_recovery_voltage(self, volts: float) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 5, round(volts * 10))
        return bytes(buf)

    def with_power_save_time(self, hours: int) -> bytes:
        if not 0 <= hours <= 255:
            raise ValueError("power save time out of range")
        buf = self._buffer()
        buf[7] = hours
        return bytes(buf)

    def with_output_frequency(self, hertz: float) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 9, round(hertz * 10))
        return bytes(buf)

    def with_output_voltage(self, volts: int) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 11, int(volts))
        return bytes(buf)

    def with_output_power_limit(self, watts: int) -> bytes:
        if watts <= 0 or watts % 100:
            raise ValueError("power limit must be a positive multiple of 100 W")
        buf = self._buffer()
        _put_u16(buf, 13, watts // 100)
        return bytes(buf)

    def with_output_power_limit_timer(self, seconds: int) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 15, int(seconds))
        return bytes(buf)

    def with_transfer_mode(self, value: int) -> bytes:
        if value not in TRANSFER_MODES:
            raise ValueError("invalid transfer mode")
        buf = self._buffer()
        buf[17] = value
        return bytes(buf)

    def with_utility_under_voltage(self, volts: int) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 18, int(volts))
        return bytes(buf)


@dataclass(frozen=True)
class Settings2:
    """0x2A0E: settings block 2."""

    raw: bytes
    battery_type: int
    battery_temperature: int
    custom_absorption_voltage: float
    custom_float_voltage: float
    charger_current: int
    charger_ignition_control: int
    breaker_rating: int
    flags: int
    inverter_on: bool

    @classmethod
    def parse(cls, data: bytes) -> Settings2:
        if len(data) < 16:
            raise ProtocolError("settings block 2 shorter than 16 bytes")
        return cls(
            raw=bytes(data),
            battery_type=_u8(data, 2),
            battery_temperature=_u8(data, 3),
            custom_absorption_voltage=_u16(data, 4) / 10,
            custom_float_voltage=_u16(data, 6) / 10,
            charger_current=_u8(data, 8),
            charger_ignition_control=_u8(data, 9),
            breaker_rating=_u8(data, 11),
            flags=_u16(data, 13),
            inverter_on=_u8(data, 15) == 1,
        )

    def flag(self, mask: int) -> bool:
        return bool(self.flags & mask)

    @property
    def power_saving(self) -> bool:
        return self.flag(FLAG_POWER_SAVING)

    @property
    def audible_alarm(self) -> bool:
        return self.flag(FLAG_AUDIBLE_ALARM)

    @property
    def auto_restart(self) -> bool:
        """True when the inverter restarts itself after a shutdown."""
        return self.flag(FLAG_OVERLOAD_RESTART)

    @property
    def equalize_charging(self) -> bool:
        return self.flag(FLAG_BATTERY_EQUALIZATION)

    # -- encoders -----------------------------------------------------------

    def _buffer(self) -> bytearray:
        return bytearray(self.raw)

    def with_flag(self, mask: int, enabled: bool) -> bytes:
        buf = self._buffer()
        flags = self.flags | mask if enabled else self.flags & ~mask
        _put_u16(buf, 13, flags & 0xFFFF)
        return bytes(buf)

    def with_battery_type(self, value: int) -> bytes:
        if value not in BATTERY_TYPES:
            raise ValueError("invalid battery type")
        buf = self._buffer()
        buf[2] = value
        return bytes(buf)

    def with_battery_temperature(self, value: int) -> bytes:
        if value not in BATTERY_TEMPERATURES:
            raise ValueError("invalid battery temperature")
        buf = self._buffer()
        buf[3] = value
        return bytes(buf)

    def with_custom_absorption_voltage(self, volts: float) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 4, round(volts * 10))
        return bytes(buf)

    def with_custom_float_voltage(self, volts: float) -> bytes:
        buf = self._buffer()
        _put_u16(buf, 6, round(volts * 10))
        return bytes(buf)

    def with_charger_current(self, amps: int) -> bytes:
        if not 0 <= amps <= 255:
            raise ValueError("charger current out of range")
        buf = self._buffer()
        buf[8] = amps
        return bytes(buf)

    def with_charger_ignition_control(self, value: int) -> bytes:
        if value not in CHARGER_IGNITION_CONTROL:
            raise ValueError("invalid charger ignition control")
        buf = self._buffer()
        buf[9] = value
        return bytes(buf)

    def with_breaker_rating(self, amps: int) -> bytes:
        if not 0 <= amps <= 255:
            raise ValueError("breaker rating out of range")
        buf = self._buffer()
        buf[11] = amps
        return bytes(buf)

    def with_factory_reset(self) -> bytes:
        buf = self._buffer()
        buf[12] = 1
        return bytes(buf)

    def with_inverter_on(self, on: bool) -> bytes:
        buf = self._buffer()
        buf[15] = 1 if on else 0
        return bytes(buf)


# ---------------------------------------------------------------------------
# Aggregate snapshot
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    """Everything decoded from one device, plus the raw bytes for diagnostics."""

    raw: dict[str, bytes] = field(default_factory=dict)
    firmware: Firmware | None = None
    identity: Identity | None = None
    status1: Status1 | None = None
    status2: Status2 | None = None
    rating1: Rating1 | None = None
    rating2: Rating2 | None = None
    rating3: Rating3 | None = None
    settings1: Settings1 | None = None
    settings2: Settings2 | None = None

    _PARSERS = {
        CHAR_FIRMWARE: ("firmware", Firmware),
        CHAR_SERIAL: ("identity", Identity),
        CHAR_STATUS_1: ("status1", Status1),
        CHAR_STATUS_2: ("status2", Status2),
        CHAR_RATING_1: ("rating1", Rating1),
        CHAR_RATING_2: ("rating2", Rating2),
        CHAR_RATING_3: ("rating3", Rating3),
        CHAR_SETTINGS_1: ("settings1", Settings1),
        CHAR_SETTINGS_2: ("settings2", Settings2),
    }

    def update(self, uuid: str, data: bytes) -> None:
        """Store raw bytes and decode them if a parser exists."""
        uuid = uuid.lower()
        self.raw[uuid] = bytes(data)
        if (entry := self._PARSERS.get(uuid)) is None:
            return
        attr, parser = entry
        setattr(self, attr, parser.parse(bytes(data)))

    def copy(self) -> Snapshot:
        new = Snapshot(raw=dict(self.raw))
        for attr, _ in self._PARSERS.values():
            setattr(new, attr, getattr(self, attr))
        return new

    @property
    def model(self) -> ModelInfo:
        return self.rating3.model if self.rating3 else UNKNOWN_MODEL

    @property
    def battery_current(self) -> float | None:
        """Signed battery current: positive when charging, negative when inverting."""
        if self.status1 is None or self.status2 is None:
            return None
        charge = self.status1.battery_charging_current
        discharge = self.status2.battery_discharge_current
        if charge > discharge:
            return float(charge)
        return -float(discharge)

    @property
    def battery_power(self) -> float | None:
        """Signed battery power in watts (positive when charging)."""
        current = self.battery_current
        if current is None or self.status1 is None:
            return None
        return round(self.status1.battery_voltage * current)

    @property
    def ac_input_power(self) -> float | None:
        """Approximate AC input power (V * A) as shown by the app."""
        if self.status1 is None or self.status2 is None:
            return None
        return round(self.status1.ac_input_voltage * self.status2.ac_input_current)
