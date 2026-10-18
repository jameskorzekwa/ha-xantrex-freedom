"""Select entities for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XantrexConfigEntry, XantrexCoordinator
from .entity import XantrexEntity
from .protocol import (
    BATTERY_TEMPERATURES,
    BATTERY_TYPES,
    CHARGER_IGNITION_CONTROL,
    FLAG_OVERLOAD_RESTART,
    INVERTER_IGNITION_CONTROL,
    TRANSFER_MODES,
    Snapshot,
)

SHUTDOWN_RECOVERY = {True: "auto_restart", False: "manual_restart"}


@dataclass(frozen=True, kw_only=True)
class XantrexSelectDescription(SelectEntityDescription):
    """Select description with getter and writer."""

    current_fn: Callable[[Snapshot], str | None]
    write_fn: Callable[[XantrexCoordinator, str], Any]
    options_fn: Callable[[Snapshot], list[str]] | None = None
    enabled_fn: Callable[[Snapshot], bool] | None = None


def _enum_select(
    key: str,
    mapping: dict[int, str],
    getter: Callable[[Snapshot], int | None],
    block: str,
    encoder_name: str,
    *,
    enabled_fn: Callable[[Snapshot], bool] | None = None,
    enabled_default: bool = True,
) -> XantrexSelectDescription:
    reverse = {v: k for k, v in mapping.items()}

    def current(s: Snapshot) -> str | None:
        raw = getter(s)
        return mapping.get(raw) if raw is not None else None

    async def write(coordinator: XantrexCoordinator, option: str) -> None:
        value = reverse[option]
        writer = getattr(coordinator, f"async_write_{block}")
        await writer(lambda cur: getattr(cur, encoder_name)(value))

    return XantrexSelectDescription(
        key=key,
        translation_key=key,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=enabled_default,
        options=list(mapping.values()),
        current_fn=current,
        write_fn=write,
        enabled_fn=enabled_fn,
    )


def _output_voltage_options(s: Snapshot) -> list[str]:
    return ["220", "230", "240"] if s.model.is_high_voltage else ["108", "110", "120"]


async def _write_output_voltage(coordinator: XantrexCoordinator, option: str) -> None:
    await coordinator.async_write_settings1(
        lambda cur: cur.with_output_voltage(int(option))
    )


async def _write_output_frequency(coordinator: XantrexCoordinator, option: str) -> None:
    await coordinator.async_write_settings1(
        lambda cur: cur.with_output_frequency(float(option))
    )


async def _write_shutdown_recovery(
    coordinator: XantrexCoordinator, option: str
) -> None:
    await coordinator.async_write_settings2(
        lambda cur: cur.with_flag(FLAG_OVERLOAD_RESTART, option == "auto_restart")
    )


SELECTS: tuple[XantrexSelectDescription, ...] = (
    _enum_select(
        "inverter_ignition_control",
        INVERTER_IGNITION_CONTROL,
        lambda s: s.settings1.inverter_ignition_control if s.settings1 else None,
        "settings1",
        "with_inverter_ignition_control",
    ),
    _enum_select(
        "transfer_mode",
        TRANSFER_MODES,
        lambda s: s.settings1.transfer_mode if s.settings1 else None,
        "settings1",
        "with_transfer_mode",
    ),
    XantrexSelectDescription(
        key="shutdown_recovery",
        translation_key="shutdown_recovery",
        entity_category=EntityCategory.CONFIG,
        options=list(SHUTDOWN_RECOVERY.values()),
        current_fn=lambda s: (
            SHUTDOWN_RECOVERY[s.settings2.auto_restart] if s.settings2 else None
        ),
        write_fn=_write_shutdown_recovery,
    ),
    XantrexSelectDescription(
        key="output_frequency",
        translation_key="output_frequency",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=["50", "60"],
        current_fn=lambda s: (
            str(int(s.settings1.output_frequency))
            if s.settings1 and s.settings1.output_frequency in (50.0, 60.0)
            else None
        ),
        write_fn=_write_output_frequency,
    ),
    XantrexSelectDescription(
        key="output_voltage",
        translation_key="output_voltage",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=["108", "110", "120", "220", "230", "240"],
        options_fn=_output_voltage_options,
        current_fn=lambda s: str(s.settings1.output_voltage) if s.settings1 else None,
        write_fn=_write_output_voltage,
    ),
    _enum_select(
        "battery_type",
        BATTERY_TYPES,
        lambda s: s.settings2.battery_type if s.settings2 else None,
        "settings2",
        "with_battery_type",
        enabled_fn=lambda s: s.model.is_charger,
    ),
    _enum_select(
        "battery_temperature",
        BATTERY_TEMPERATURES,
        lambda s: s.settings2.battery_temperature if s.settings2 else None,
        "settings2",
        "with_battery_temperature",
        enabled_fn=lambda s: s.model.is_charger,
    ),
    _enum_select(
        "charger_ignition_control",
        CHARGER_IGNITION_CONTROL,
        lambda s: s.settings2.charger_ignition_control if s.settings2 else None,
        "settings2",
        "with_charger_ignition_control",
        enabled_fn=lambda s: s.model.is_charger,
        enabled_default=False,
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
        XantrexSelect(coordinator, description)
        for description in SELECTS
        if description.enabled_fn is None or description.enabled_fn(snapshot)
    )


class XantrexSelect(XantrexEntity, SelectEntity):
    """A writable enumerated setting."""

    entity_description: XantrexSelectDescription

    def __init__(
        self, coordinator: XantrexCoordinator, description: XantrexSelectDescription
    ) -> None:
        super().__init__(coordinator, description)
        if description.options_fn is not None:
            self._attr_options = description.options_fn(coordinator.data)

    @property
    def current_option(self) -> str | None:
        current = self.entity_description.current_fn(self.snapshot)
        if current is not None and current not in self.options:
            return None
        return current

    async def async_select_option(self, option: str) -> None:
        await self.entity_description.write_fn(self.coordinator, option)
