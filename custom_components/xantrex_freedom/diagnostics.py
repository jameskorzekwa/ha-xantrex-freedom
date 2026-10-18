"""Diagnostics support for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import XantrexConfigEntry


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        data = asdict(value)
        if "raw" in data and isinstance(data["raw"], bytes):
            data["raw"] = data["raw"].hex()
        return data
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: XantrexConfigEntry
) -> dict[str, Any]:
    """Return raw characteristic bytes and every decoded block."""
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "rssi": coordinator.rssi,
        "last_update_success": coordinator.last_update_success,
        "raw": {uuid[4:8]: data.hex() for uuid, data in sorted(snapshot.raw.items())},
        "model": _plain(snapshot.model),
        "firmware": _plain(snapshot.firmware),
        "identity": _plain(snapshot.identity),
        "status1": _plain(snapshot.status1),
        "status2": _plain(snapshot.status2),
        "active_warnings": list(snapshot.status2.active_warnings)
        if snapshot.status2
        else None,
        "rating1": _plain(snapshot.rating1),
        "rating2": _plain(snapshot.rating2),
        "rating3": _plain(snapshot.rating3),
        "settings1": _plain(snapshot.settings1),
        "settings2": _plain(snapshot.settings2),
        "derived": {
            "battery_current": snapshot.battery_current,
            "battery_power": snapshot.battery_power,
            "ac_input_power": snapshot.ac_input_power,
        },
    }
