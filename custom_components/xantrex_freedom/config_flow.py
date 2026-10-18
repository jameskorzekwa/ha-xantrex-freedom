"""Config flow for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak.exc import BleakError
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_ADDRESS,
    CONF_MODEL_ID,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_NUMBER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import async_probe
from .protocol import LOCAL_NAME_PREFIX, MODELS, SERVICE_UUID, ProtocolError

_LOGGER = logging.getLogger(__name__)


def _is_candidate(info: BluetoothServiceInfoBleak) -> bool:
    """True for advertisements that look like a Freedom X remote panel.

    The panel advertises exactly one 16-bit service (0x1910) with no
    manufacturer or service data, and its scan response carries a local name
    of ``ID`` followed by the inverter serial number.  0x1910 is also used by
    generic BLE serial modules, so anything with extra payload is rejected.
    """
    if not info.connectable or info.manufacturer_data or info.service_data:
        return False
    uuids = {uuid.lower() for uuid in info.service_uuids}
    if info.name.startswith(LOCAL_NAME_PREFIX) and (not uuids or SERVICE_UUID in uuids):
        return True
    return uuids == {SERVICE_UUID}


def _display_name(info: BluetoothServiceInfoBleak) -> str:
    name = info.name.strip()
    if name and name != info.address:
        return f"{name} ({info.address})"
    return info.address


class XantrexConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover a remote panel and verify it speaks the Freedom protocol."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._candidates: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a matched Bluetooth advertisement."""
        if not _is_candidate(discovery_info):
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": _display_name(discovery_info)}
        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick from the panels currently in range."""
        if user_input is not None:
            self._discovery = self._candidates[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(
                self._discovery.address.upper(), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return await self.async_step_confirm()

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            address = info.address.upper()
            if address not in configured and _is_candidate(info):
                self._candidates[address] = info
        if not self._candidates:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: _display_name(info)
                            for address, info in self._candidates.items()
                        }
                    )
                }
            ),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect once, read the identity blocks and create the entry."""
        assert self._discovery is not None
        errors: dict[str, str] = {}
        placeholders = {"name": _display_name(self._discovery)}
        if user_input is not None:
            address = self._discovery.address
            device = async_ble_device_from_address(self.hass, address, connectable=True)
            if device is None:
                errors["base"] = "not_in_range"
            else:
                try:
                    snapshot, _ = await async_probe(self.hass, device)
                except (BleakError, TimeoutError) as err:
                    _LOGGER.warning("Cannot connect to %s: %s", address, err)
                    errors["base"] = "cannot_connect"
                except ProtocolError as err:
                    _LOGGER.warning("%s is not a Freedom X panel: %s", address, err)
                    errors["base"] = "not_supported"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error probing %s", address)
                    errors["base"] = "unknown"
                else:
                    rating3 = snapshot.rating3
                    if rating3 is None or (
                        rating3.model_id not in MODELS and snapshot.status1 is None
                    ):
                        errors["base"] = "not_supported"
                    else:
                        model = snapshot.model
                        serial = (
                            snapshot.identity.serial_number if snapshot.identity else ""
                        )
                        title = model.name if model.rated_watts else "Xantrex Freedom"
                        return self.async_create_entry(
                            title=title,
                            data={
                                CONF_ADDRESS: address.upper(),
                                CONF_NAME: self._discovery.name,
                                CONF_MODEL_ID: rating3.model_id,
                                CONF_SERIAL_NUMBER: serial,
                            },
                        )
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=placeholders,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return XantrexOptionsFlow()


class XantrexOptionsFlow(OptionsFlow):
    """Poll interval option."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
