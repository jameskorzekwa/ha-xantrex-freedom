"""Unit tests for the Freedom X/XC GATT protocol decoder."""

from __future__ import annotations

import struct

import pytest

from custom_components.xantrex_freedom import protocol as p


def _u16s(*values: int) -> bytes:
    return struct.pack("<" + "H" * len(values), *values)


def test_char_uuid() -> None:
    assert p.CHAR_STATUS_1 == "00002a03-0000-1000-8000-00805f9b34fb"
    assert p.SERVICE_UUID == "00001910-0000-1000-8000-00805f9b34fb"


def test_firmware() -> None:
    data = b"XF" + b"\0" + b"MBFW1.23" + b"\0" + b"BLE 1.36" + b"\0"
    fw = p.Firmware.parse(data)
    assert fw.protocol_id == "XF"
    assert fw.main_board == "v1.23"
    assert fw.remote_panel == "v1.36"


def test_firmware_too_short() -> None:
    with pytest.raises(p.ProtocolError):
        p.Firmware.parse(b"\0" * 10)


def test_identity() -> None:
    ident = p.Identity.parse(b"FXC12512A00627\0\0\0\0\0\0")
    assert ident.serial_number == "FXC12512A00627"
    assert ident.manufacturing_date == "2025-12"
    assert p.Identity.parse(b"ABC").manufacturing_date is None


def test_status1() -> None:
    data = _u16s(1203, 599, 1198, 600, 450, 400, 20, 350, 1312, 0)
    s = p.Status1.parse(data)
    assert s.ac_input_voltage == pytest.approx(120.3)
    assert s.ac_input_frequency == pytest.approx(59.9)
    assert s.ac_output_voltage == pytest.approx(119.8)
    assert s.ac_output_frequency == pytest.approx(60.0)
    assert s.ac_output_apparent_power == 450
    assert s.ac_output_power == 400
    assert s.ac_output_load == 20
    assert s.bus_voltage == 350
    assert s.battery_voltage == pytest.approx(13.12)
    assert s.battery_charging_current == 0


def test_status2() -> None:
    warnings = p.WARNING_FLAGS["overload"] | p.WARNING_FLAGS["battery_low_alarm"]
    data = (
        _u16s(85, 41, 123, 13, 32, 7)
        + bytes([3])
        + _u16s(0x0010)
        + struct.pack("<I", warnings)
        + b"B"
    )
    assert len(data) == 20
    s = p.Status2.parse(data)
    assert s.battery_capacity == 85
    assert s.heat_sink_temperature == 41
    assert s.ac_input_current == pytest.approx(12.3)
    assert s.battery_discharge_current == 32
    assert s.charging_status == 3
    assert s.charging_status_key == "float"
    assert s.load_connected is True
    assert s.working_mode == "B"
    assert s.working_mode_key == "battery"
    assert s.active_warnings == ("battery_low_alarm", "overload")
    assert s.warning("overload") and not s.warning("fan_locked")


def test_rating3_and_models() -> None:
    data = bytes([0, 0, 30, 0, 0x03]) + b"U3FW2.14" + b"\0" * 7
    r = p.Rating3.parse(data)
    assert r.model_id == 3
    assert r.model.part_number == "817-2000"
    assert r.model.family is p.ModelFamily.FX
    assert r.model.is_charger is False
    assert r.model.is_24v is False
    assert r.comm_firmware == "v2.14"
    assert p.model_info(0x14).family is p.ModelFamily.FXC_PRO
    assert p.model_info(0x12).is_24v
    assert p.model_info(0x16).is_high_voltage
    assert p.model_info(0xFF) is p.UNKNOWN_MODEL


def _settings1_bytes() -> bytes:
    return (
        bytes([2])  # ignition auto-on
        + _u16s(110)  # lbco 11.0 V
        + _u16s(300)  # lbco delay
        + _u16s(131)  # recovery 13.1 V
        + bytes([25, 0])  # power save time, power save mode
        + _u16s(600)  # 60.0 Hz
        + _u16s(120)  # 120 V
        + _u16s(20)  # power limit raw
        + _u16s(300)  # power limit timer
        + bytes([1])  # UPS
        + _u16s(95)  # utility under voltage
    )


def test_settings1_parse() -> None:
    s = p.Settings1.parse(_settings1_bytes())
    assert s.inverter_ignition_control == 2
    assert s.lbco_voltage == pytest.approx(11.0)
    assert s.lbco_delay_timer == 300
    assert s.lbco_recovery_voltage == pytest.approx(13.1)
    assert s.power_save_time == 25
    assert s.output_frequency == pytest.approx(60.0)
    assert s.output_voltage == 120
    assert s.output_power_limit == 2000
    assert s.output_power_limit_timer == 300
    assert s.transfer_mode == 1
    assert s.utility_under_voltage == 95
    assert s.lbco_recovery_off is False


def test_settings1_power_limit_in_watts() -> None:
    raw = bytearray(_settings1_bytes())
    struct.pack_into("<H", raw, 13, 1500)
    assert p.Settings1.parse(bytes(raw)).output_power_limit == 1500


def test_settings1_encoders_only_touch_their_bytes() -> None:
    original = _settings1_bytes()
    s = p.Settings1.parse(original)

    out = s.with_lbco_voltage(12.3)
    assert out[1:3] == _u16s(123)
    assert out[:1] == original[:1] and out[3:] == original[3:]

    out = s.with_inverter_ignition_control(0)
    assert out[0] == 0 and out[1:] == original[1:]

    out = s.with_transfer_mode(0)
    assert out[17] == 0 and out[:17] == original[:17] and out[18:] == original[18:]

    out = s.with_output_frequency(50)
    assert out[9:11] == _u16s(500)

    out = s.with_power_save_time(0)
    assert out[7] == 0

    out = s.with_utility_under_voltage(100)
    assert out[18:20] == _u16s(100)

    assert len(out) == len(original)
    with pytest.raises(ValueError):
        s.with_inverter_ignition_control(9)


def _settings2_bytes() -> bytes:
    return (
        bytes([0, 0, 4, 1])  # ?, ?, LiFePO4, warm
        + _u16s(144)  # absorption 14.4
        + _u16s(136)  # float 13.6
        + bytes([40, 0, 0, 30, 0])  # charger A, chg ign, ?, breaker, reset
        + _u16s(p.FLAG_OVERLOAD_RESTART | p.FLAG_AUDIBLE_ALARM)
        + bytes([1])  # inverter on
        + bytes([0, 0, 0, 0])
    )


def test_settings2_parse() -> None:
    s = p.Settings2.parse(_settings2_bytes())
    assert s.battery_type == 4
    assert p.BATTERY_TYPES[s.battery_type] == "lifepo4"
    assert s.battery_temperature == 1
    assert s.custom_absorption_voltage == pytest.approx(14.4)
    assert s.custom_float_voltage == pytest.approx(13.6)
    assert s.charger_current == 40
    assert s.breaker_rating == 30
    assert s.auto_restart is True
    assert s.audible_alarm is True
    assert s.power_saving is False
    assert s.inverter_on is True


def test_settings2_encoders() -> None:
    original = _settings2_bytes()
    s = p.Settings2.parse(original)

    out = s.with_flag(p.FLAG_POWER_SAVING, True)
    flags = struct.unpack_from("<H", out, 13)[0]
    assert flags & p.FLAG_POWER_SAVING
    assert flags & p.FLAG_OVERLOAD_RESTART
    assert out[:13] == original[:13] and out[15:] == original[15:]

    out = s.with_flag(p.FLAG_OVERLOAD_RESTART, False)
    assert not struct.unpack_from("<H", out, 13)[0] & p.FLAG_OVERLOAD_RESTART

    out = s.with_inverter_on(False)
    assert out[15] == 0 and out[:15] == original[:15]

    out = s.with_battery_type(0)
    assert out[2] == 0

    out = s.with_charger_current(20)
    assert out[8] == 20

    assert s.with_factory_reset()[12] == 1
    assert len(out) == len(original)


def test_settings2_minimum_length() -> None:
    assert p.Settings2.parse(_settings2_bytes()[:16]).inverter_on is True
    with pytest.raises(p.ProtocolError):
        p.Settings2.parse(_settings2_bytes()[:15])


def test_snapshot_update_and_derived() -> None:
    snap = p.Snapshot()
    snap.update(p.CHAR_STATUS_1, _u16s(0, 0, 1200, 600, 500, 480, 24, 350, 1280, 0))
    snap.update(
        p.CHAR_STATUS_2,
        _u16s(80, 40, 0, 12, 40, 7) + bytes([0]) + _u16s(0) + _u16s(0, 0) + b"B",
    )
    assert snap.battery_current == -40
    assert snap.battery_power == round(12.8 * -40)
    assert snap.ac_input_power == 0
    assert snap.model is p.UNKNOWN_MODEL
    assert snap.raw[p.CHAR_STATUS_1].hex().startswith("0000")

    copy = snap.copy()
    assert copy.status1 == snap.status1
    copy.update(p.CHAR_STATUS_1, _u16s(0, 0, 0, 0, 0, 0, 0, 0, 1300, 50))
    assert snap.status1.battery_voltage == pytest.approx(12.8)
    assert snap.battery_current == -40
    assert copy.battery_current == 50  # charging beats the stale discharge figure
    assert copy.battery_power == round(13.0 * 50)


def test_snapshot_ignores_unparsed_characteristics() -> None:
    snap = p.Snapshot()
    snap.update(p.CHAR_CHARGE_CURRENTS_1, b"\x05\x32\x05")
    assert snap.raw[p.CHAR_CHARGE_CURRENTS_1] == b"\x05\x32\x05"
