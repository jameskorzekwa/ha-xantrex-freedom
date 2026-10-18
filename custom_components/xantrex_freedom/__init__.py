"""The Xantrex Freedom X/XC integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import XantrexConfigEntry, XantrexCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: XantrexConfigEntry) -> bool:
    """Set up a Freedom X/XC remote panel from a config entry."""
    coordinator = XantrexCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: XantrexConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: XantrexConfigEntry
) -> None:
    """Reload when the poll interval changes."""
    await hass.config_entries.async_reload(entry.entry_id)
