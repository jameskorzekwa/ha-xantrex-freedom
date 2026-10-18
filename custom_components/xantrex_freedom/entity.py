"""Shared entity base for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import XantrexCoordinator
from .protocol import Snapshot


class XantrexEntity(CoordinatorEntity[XantrexCoordinator]):
    """Base entity bound to one remote panel."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: XantrexCoordinator, description: EntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def snapshot(self) -> Snapshot:
        return self.coordinator.data


def _device_info(coordinator: XantrexCoordinator) -> DeviceInfo:
    snapshot = coordinator.data
    model = snapshot.model
    versions = []
    if snapshot.firmware:
        if snapshot.firmware.main_board:
            versions.append(f"main {snapshot.firmware.main_board}")
        if snapshot.firmware.remote_panel:
            versions.append(f"panel {snapshot.firmware.remote_panel}")
    if snapshot.rating3 and snapshot.rating3.comm_firmware:
        versions.append(f"comm {snapshot.rating3.comm_firmware}")
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.address)},
        connections={(CONNECTION_BLUETOOTH, coordinator.address)},
        manufacturer=MANUFACTURER,
        model=model.name,
        model_id=model.part_number if model.rated_watts else None,
        name=coordinator.config_entry.title,
        serial_number=snapshot.identity.serial_number if snapshot.identity else None,
        sw_version=", ".join(versions) or None,
    )
