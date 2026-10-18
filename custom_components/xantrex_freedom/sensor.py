"""Sensors for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XantrexConfigEntry
from .entity import XantrexEntity
from .protocol import (
    BATTERY_TYPES,
    CHARGING_STATUS,
    INVERTER_IGNITION_CONTROL,
    TRANSFER_MODES,
    WORKING_MODES,
    Snapshot,
)

type ValueFn = Callable[[Snapshot], Any]
type EnabledFn = Callable[[Snapshot], bool]


def _s1(attr: str) -> ValueFn:
    return lambda s: getattr(s.status1, attr) if s.status1 else None


def _s2(attr: str) -> ValueFn:
    return lambda s: getattr(s.status2, attr) if s.status2 else None


def _charger(s: Snapshot) -> bool:
    return s.model.is_charger


def _soc_meaningful(s: Snapshot) -> bool:
    """The capacity figure is a lead-acid voltage estimate; hide it for LFP/custom."""
    return s.settings2 is not None and s.settings2.battery_type not in (3, 4)


@dataclass(frozen=True, kw_only=True)
class XantrexSensorDescription(SensorEntityDescription):
    """Sensor description with a value getter."""

    value_fn: ValueFn
    enabled_fn: EnabledFn | None = None
    attributes_fn: Callable[[Snapshot], dict[str, Any]] | None = None


SENSORS: tuple[XantrexSensorDescription, ...] = (
    # --- AC input (shore / utility) -------------------------------------
    XantrexSensorDescription(
        key="ac_input_voltage",
        translation_key="ac_input_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_s1("ac_input_voltage"),
    ),
    XantrexSensorDescription(
        key="ac_input_frequency",
        translation_key="ac_input_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_s1("ac_input_frequency"),
    ),
    XantrexSensorDescription(
        key="ac_input_current",
        translation_key="ac_input_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_s2("ac_input_current"),
    ),
    XantrexSensorDescription(
        key="ac_input_power",
        translation_key="ac_input_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda s: s.ac_input_power,
    ),
    # --- AC output (loads) ------------------------------------------------
    XantrexSensorDescription(
        key="ac_output_voltage",
        translation_key="ac_output_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_s1("ac_output_voltage"),
    ),
    XantrexSensorDescription(
        key="ac_output_frequency",
        translation_key="ac_output_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_s1("ac_output_frequency"),
    ),
    XantrexSensorDescription(
        key="ac_output_power",
        translation_key="ac_output_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_s1("ac_output_power"),
    ),
    XantrexSensorDescription(
        key="ac_output_apparent_power",
        translation_key="ac_output_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=_s1("ac_output_apparent_power"),
    ),
    XantrexSensorDescription(
        key="ac_output_load",
        translation_key="ac_output_load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_s1("ac_output_load"),
    ),
    # --- Battery ----------------------------------------------------------
    XantrexSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_s1("battery_voltage"),
    ),
    XantrexSensorDescription(
        key="battery_current",
        translation_key="battery_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda s: s.battery_current,
    ),
    XantrexSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda s: s.battery_power,
    ),
    XantrexSensorDescription(
        key="battery_charging_current",
        translation_key="battery_charging_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=_s1("battery_charging_current"),
        enabled_fn=_charger,
    ),
    XantrexSensorDescription(
        key="battery_discharge_current",
        translation_key="battery_discharge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=_s2("battery_discharge_current"),
    ),
    XantrexSensorDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_s2("battery_capacity"),
        enabled_fn=_soc_meaningful,
    ),
    # --- Inverter ---------------------------------------------------------
    XantrexSensorDescription(
        key="heat_sink_temperature",
        translation_key="heat_sink_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_s2("heat_sink_temperature"),
    ),
    XantrexSensorDescription(
        key="bus_voltage",
        translation_key="bus_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_s1("bus_voltage"),
    ),
    XantrexSensorDescription(
        key="working_mode",
        translation_key="working_mode",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(WORKING_MODES.values()) | {"unknown"}),
        value_fn=lambda s: (
            (s.status2.working_mode_key or "unknown") if s.status2 else None
        ),
        attributes_fn=lambda s: {"raw": s.status2.working_mode} if s.status2 else {},
    ),
    XantrexSensorDescription(
        key="charging_status",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(CHARGING_STATUS.values()) | {"unknown"}),
        value_fn=lambda s: (
            (s.status2.charging_status_key or "unknown") if s.status2 else None
        ),
        enabled_fn=_charger,
    ),
    XantrexSensorDescription(
        key="active_faults",
        translation_key="active_faults",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: len(s.status2.active_warnings) if s.status2 else None,
        attributes_fn=lambda s: (
            {
                "faults": list(s.status2.active_warnings),
                "raw": f"0x{s.status2.warnings:08x}",
            }
            if s.status2
            else {}
        ),
    ),
    # --- Settings exposed read-only (diagnostic) ---------------------------
    XantrexSensorDescription(
        key="output_power_limit",
        translation_key="output_power_limit",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.settings1.output_power_limit if s.settings1 else None,
        attributes_fn=lambda s: (
            {"raw": s.settings1.output_power_limit_raw} if s.settings1 else {}
        ),
    ),
    XantrexSensorDescription(
        key="output_power_limit_timer",
        translation_key="output_power_limit_timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: (
            s.settings1.output_power_limit_timer if s.settings1 else None
        ),
    ),
    XantrexSensorDescription(
        key="battery_type",
        translation_key="battery_type",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(BATTERY_TYPES.values()) | {"unknown"}),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: (
            BATTERY_TYPES.get(s.settings2.battery_type, "unknown")
            if s.settings2
            else None
        ),
    ),
    XantrexSensorDescription(
        key="ignition_control_state",
        translation_key="ignition_control_state",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(INVERTER_IGNITION_CONTROL.values()) | {"unknown"}),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: (
            INVERTER_IGNITION_CONTROL.get(
                s.settings1.inverter_ignition_control, "unknown"
            )
            if s.settings1
            else None
        ),
    ),
    XantrexSensorDescription(
        key="transfer_mode_state",
        translation_key="transfer_mode_state",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(TRANSFER_MODES.values()) | {"unknown"}),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: (
            TRANSFER_MODES.get(s.settings1.transfer_mode, "unknown")
            if s.settings1
            else None
        ),
    ),
    XantrexSensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: None,  # replaced by the coordinator value
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XantrexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    async_add_entities(
        XantrexSensor(coordinator, description)
        for description in SENSORS
        if description.enabled_fn is None or description.enabled_fn(snapshot)
    )


class XantrexSensor(XantrexEntity, SensorEntity):
    """A decoded value from the remote panel."""

    entity_description: XantrexSensorDescription

    @property
    def native_value(self) -> Any:
        if self.entity_description.key == "rssi":
            return self.coordinator.rssi
        return self.entity_description.value_fn(self.snapshot)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.snapshot)
