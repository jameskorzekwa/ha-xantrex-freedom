"""Switches for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XantrexConfigEntry, XantrexCoordinator
from .entity import XantrexEntity
from .protocol import (
    FLAG_AUDIBLE_ALARM,
    FLAG_BATTERY_EQUALIZATION,
    FLAG_POWER_SAVING,
    Settings2,
    Snapshot,
)


def _flag_switch(
    mask: int,
) -> tuple[
    Callable[[Snapshot], bool | None],
    Callable[[XantrexCoordinator, bool], Any],
]:
    def is_on(s: Snapshot) -> bool | None:
        return s.settings2.flag(mask) if s.settings2 else None

    async def write(coordinator: XantrexCoordinator, on: bool) -> None:
        await coordinator.async_write_settings2(lambda cur: cur.with_flag(mask, on))

    return is_on, write


async def _write_inverter(coordinator: XantrexCoordinator, on: bool) -> None:
    await coordinator.async_write_settings2(
        lambda cur: Settings2.with_inverter_on(cur, on)
    )


@dataclass(frozen=True, kw_only=True)
class XantrexSwitchDescription(SwitchEntityDescription):
    """Switch description with state getter and writer."""

    is_on_fn: Callable[[Snapshot], bool | None]
    write_fn: Callable[[XantrexCoordinator, bool], Any]
    enabled_fn: Callable[[Snapshot], bool] | None = None


_power_saving_on, _power_saving_write = _flag_switch(FLAG_POWER_SAVING)
_alarm_on, _alarm_write = _flag_switch(FLAG_AUDIBLE_ALARM)
_equalize_on, _equalize_write = _flag_switch(FLAG_BATTERY_EQUALIZATION)

SWITCHES: tuple[XantrexSwitchDescription, ...] = (
    XantrexSwitchDescription(
        key="inverter",
        translation_key="inverter",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda s: s.settings2.inverter_on if s.settings2 else None,
        write_fn=_write_inverter,
    ),
    XantrexSwitchDescription(
        key="power_saving",
        translation_key="power_saving",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=_power_saving_on,
        write_fn=_power_saving_write,
    ),
    XantrexSwitchDescription(
        key="audible_alarm",
        translation_key="audible_alarm",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=_alarm_on,
        write_fn=_alarm_write,
    ),
    XantrexSwitchDescription(
        key="equalize_charging",
        translation_key="equalize_charging",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=_equalize_on,
        write_fn=_equalize_write,
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
        XantrexSwitch(coordinator, description)
        for description in SWITCHES
        if description.enabled_fn is None or description.enabled_fn(snapshot)
    )


class XantrexSwitch(XantrexEntity, SwitchEntity):
    """A writable on/off setting."""

    entity_description: XantrexSwitchDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.snapshot)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.write_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.write_fn(self.coordinator, False)
