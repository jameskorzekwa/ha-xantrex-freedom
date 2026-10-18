"""Number entities for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XantrexConfigEntry, XantrexCoordinator
from .entity import XantrexEntity
from .protocol import Snapshot

type Range = tuple[float, float]


@dataclass(frozen=True, kw_only=True)
class XantrexNumberDescription(NumberEntityDescription):
    """Number description with getter, writer and model-dependent range."""

    value_fn: Callable[[Snapshot], float | None]
    write_fn: Callable[[XantrexCoordinator, float], Any]
    range_fn: Callable[[Snapshot], Range]
    enabled_fn: Callable[[Snapshot], bool] | None = None


def _s1_writer(encoder: str) -> Callable[[XantrexCoordinator, float], Any]:
    async def write(coordinator: XantrexCoordinator, value: float) -> None:
        await coordinator.async_write_settings1(
            lambda cur: getattr(cur, encoder)(value)
        )

    return write


def _s2_writer(encoder: str) -> Callable[[XantrexCoordinator, float], Any]:
    async def write(coordinator: XantrexCoordinator, value: float) -> None:
        await coordinator.async_write_settings2(
            lambda cur: getattr(cur, encoder)(value)
        )

    return write


def _lbco_range(s: Snapshot) -> Range:
    return (20.0, 25.6) if s.model.is_24v else (10.0, 12.8)


def _lbco_recovery_range(s: Snapshot) -> Range:
    lbco = s.settings1.lbco_voltage if s.settings1 else None
    if s.model.is_24v:
        return ((lbco or 20.0) + 0.2, 32.2)
    return ((lbco or 10.0) + 0.2, 16.1)


def _utility_range(s: Snapshot) -> Range:
    return (170, 220) if s.model.is_high_voltage else (85, 110)


def _charge_voltage_range(s: Snapshot) -> Range:
    return (24.0, 32.0) if s.model.is_24v else (12.0, 17.0)


def _charger_current_range(s: Snapshot) -> Range:
    rated = s.rating2.max_ac_charging_current if s.rating2 else 0
    return (5, rated or 50)


NUMBERS: tuple[XantrexNumberDescription, ...] = (
    XantrexNumberDescription(
        key="lbco_voltage",
        translation_key="lbco_voltage",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings1.lbco_voltage if s.settings1 else None,
        write_fn=_s1_writer("with_lbco_voltage"),
        range_fn=_lbco_range,
    ),
    XantrexNumberDescription(
        key="lbco_delay_timer",
        translation_key="lbco_delay_timer",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings1.lbco_delay_timer if s.settings1 else None,
        write_fn=_s1_writer("with_lbco_delay_timer"),
        range_fn=lambda s: (1, 300),
    ),
    XantrexNumberDescription(
        key="lbco_recovery_voltage",
        translation_key="lbco_recovery_voltage",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings1.lbco_recovery_voltage if s.settings1 else None,
        write_fn=_s1_writer("with_lbco_recovery_voltage"),
        range_fn=_lbco_recovery_range,
    ),
    XantrexNumberDescription(
        key="power_save_time",
        translation_key="power_save_time",
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings1.power_save_time if s.settings1 else None,
        write_fn=_s1_writer("with_power_save_time"),
        range_fn=lambda s: (0, 25),
    ),
    XantrexNumberDescription(
        key="output_power_limit",
        translation_key="output_power_limit",
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_step=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings1.output_power_limit if s.settings1 else None,
        write_fn=_s1_writer("with_output_power_limit"),
        range_fn=lambda s: (100, s.model.rated_watts or 3000),
    ),
    XantrexNumberDescription(
        key="output_power_limit_timer",
        translation_key="output_power_limit_timer",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda s: (
            s.settings1.output_power_limit_timer if s.settings1 else None
        ),
        write_fn=_s1_writer("with_output_power_limit_timer"),
        range_fn=lambda s: (1, 300),
    ),
    XantrexNumberDescription(
        key="utility_under_voltage",
        translation_key="utility_under_voltage",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings1.utility_under_voltage if s.settings1 else None,
        write_fn=_s1_writer("with_utility_under_voltage"),
        range_fn=_utility_range,
    ),
    XantrexNumberDescription(
        key="charger_current",
        translation_key="charger_current",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_step=5,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings2.charger_current if s.settings2 else None,
        write_fn=_s2_writer("with_charger_current"),
        range_fn=_charger_current_range,
        enabled_fn=lambda s: s.model.is_charger,
    ),
    XantrexNumberDescription(
        key="custom_absorption_voltage",
        translation_key="custom_absorption_voltage",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda s: (
            s.settings2.custom_absorption_voltage if s.settings2 else None
        ),
        write_fn=_s2_writer("with_custom_absorption_voltage"),
        range_fn=_charge_voltage_range,
        enabled_fn=lambda s: s.model.is_charger,
    ),
    XantrexNumberDescription(
        key="custom_float_voltage",
        translation_key="custom_float_voltage",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.settings2.custom_float_voltage if s.settings2 else None,
        write_fn=_s2_writer("with_custom_float_voltage"),
        range_fn=_charge_voltage_range,
        enabled_fn=lambda s: s.model.is_charger,
    ),
    XantrexNumberDescription(
        key="breaker_rating",
        translation_key="breaker_rating",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.settings2.breaker_rating if s.settings2 else None,
        write_fn=_s2_writer("with_breaker_rating"),
        range_fn=lambda s: (5, 50 if s.model.rated_watts >= 3000 else 30),
        enabled_fn=lambda s: s.model.is_charger,
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
        XantrexNumber(coordinator, description)
        for description in NUMBERS
        if description.enabled_fn is None or description.enabled_fn(snapshot)
    )


class XantrexNumber(XantrexEntity, NumberEntity):
    """A writable numeric setting."""

    entity_description: XantrexNumberDescription

    @property
    def native_min_value(self) -> float:
        return self.entity_description.range_fn(self.snapshot)[0]

    @property
    def native_max_value(self) -> float:
        return self.entity_description.range_fn(self.snapshot)[1]

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.snapshot)

    async def async_set_native_value(self, value: float) -> None:
        if self.entity_description.native_step in (1, 5, 100):
            value = int(round(value))
        await self.entity_description.write_fn(self.coordinator, value)
