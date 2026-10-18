"""Binary sensors for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import AC_PRESENT_THRESHOLD_V
from .coordinator import XantrexConfigEntry
from .entity import XantrexEntity
from .protocol import Snapshot


def _warning(name: str) -> Callable[[Snapshot], bool | None]:
    return lambda s: s.status2.warning(name) if s.status2 else None


@dataclass(frozen=True, kw_only=True)
class XantrexBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with a state getter."""

    is_on_fn: Callable[[Snapshot], bool | None]
    attributes_fn: Callable[[Snapshot], dict[str, Any]] | None = None


BINARY_SENSORS: tuple[XantrexBinarySensorDescription, ...] = (
    XantrexBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda s: bool(s.status2.active_warnings) if s.status2 else None,
        attributes_fn=lambda s: (
            {"faults": list(s.status2.active_warnings)} if s.status2 else {}
        ),
    ),
    XantrexBinarySensorDescription(
        key="ac_input_present",
        translation_key="ac_input_present",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn=lambda s: (
            s.status1.ac_input_voltage > AC_PRESENT_THRESHOLD_V if s.status1 else None
        ),
    ),
    XantrexBinarySensorDescription(
        key="inverting",
        translation_key="inverting",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda s: s.status2.working_mode == "B" if s.status2 else None,
    ),
    XantrexBinarySensorDescription(
        key="overload",
        translation_key="overload",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_warning("overload"),
    ),
    XantrexBinarySensorDescription(
        key="over_temperature",
        translation_key="over_temperature",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_warning("over_temperature"),
    ),
    XantrexBinarySensorDescription(
        key="battery_low",
        translation_key="battery_low",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_warning("battery_low_alarm"),
    ),
    XantrexBinarySensorDescription(
        key="battery_voltage_high",
        translation_key="battery_voltage_high",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        is_on_fn=_warning("battery_voltage_high"),
    ),
    XantrexBinarySensorDescription(
        key="fan_locked",
        translation_key="fan_locked",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        is_on_fn=_warning("fan_locked"),
    ),
    XantrexBinarySensorDescription(
        key="output_short",
        translation_key="output_short",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        is_on_fn=_warning("output_short"),
    ),
    XantrexBinarySensorDescription(
        key="load_connected",
        translation_key="load_connected",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda s: s.status2.load_connected if s.status2 else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XantrexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        XantrexBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class XantrexBinarySensor(XantrexEntity, BinarySensorEntity):
    """A flag decoded from the remote panel."""

    entity_description: XantrexBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.snapshot)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.snapshot)
