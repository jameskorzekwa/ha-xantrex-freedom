"""Polling coordinator for a Xantrex Freedom X/XC remote panel."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakNotFoundError,
    establish_connection,
)
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONNECT_ATTEMPTS,
    CONNECT_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FAILURE_GRACE_POLLS,
    STATIC_REFRESH_SECONDS,
)
from .protocol import (
    CHAR_SETTINGS_1,
    CHAR_SETTINGS_2,
    DYNAMIC_CHARACTERISTICS,
    SERVICE_UUID,
    STATIC_CHARACTERISTICS,
    ProtocolError,
    Settings1,
    Settings2,
    Snapshot,
)

_LOGGER = logging.getLogger(__name__)

type XantrexConfigEntry = ConfigEntry[XantrexCoordinator]


class DeviceUnavailable(HomeAssistantError):
    """The panel is not advertising or cannot be connected."""


class XantrexCoordinator(DataUpdateCoordinator[Snapshot]):
    """Connect, read every block, disconnect.

    The remote panel accepts a single BLE central, so the connection is held
    only for the duration of a poll.  That leaves the official phone app able
    to connect between polls.
    """

    config_entry: XantrexConfigEntry

    def __init__(self, hass: HomeAssistant, entry: XantrexConfigEntry) -> None:
        self.address: str = entry.data[CONF_ADDRESS].upper()
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.address}",
            update_interval=timedelta(seconds=interval),
        )
        self._lock = asyncio.Lock()
        self._snapshot = Snapshot()
        self._static_read_at: float = 0.0
        self._last_rssi: int | None = None
        self._failures = 0

    # ------------------------------------------------------------------
    # Bluetooth helpers
    # ------------------------------------------------------------------

    def _ble_device(self) -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

    @property
    def rssi(self) -> int | None:
        info = bluetooth.async_last_service_info(
            self.hass, self.address, connectable=True
        )
        return info.rssi if info else self._last_rssi

    async def _connect(self) -> BleakClient:
        device = self._ble_device()
        if device is None:
            raise DeviceUnavailable(f"{self.address} is not advertising")
        try:
            return await establish_connection(
                BleakClientWithServiceCache,
                device,
                self.address,
                max_attempts=CONNECT_ATTEMPTS,
                timeout=CONNECT_TIMEOUT,
                ble_device_callback=self._ble_device,
            )
        except BleakNotFoundError as err:
            raise DeviceUnavailable(str(err)) from err

    @staticmethod
    def _characteristic(client: BleakClient, uuid: str) -> BleakGATTCharacteristic:
        """Resolve a characteristic inside the Xantrex service.

        The 0x2Axx UUIDs are also Bluetooth SIG assigned numbers, so always
        look them up through the 0x1910 service rather than globally.
        """
        service = client.services.get_service(SERVICE_UUID)
        if service is None:
            raise ProtocolError("Xantrex service 0x1910 not found on device")
        char = service.get_characteristic(uuid)
        if char is None:
            raise ProtocolError(f"characteristic {uuid} missing from service 0x1910")
        return char

    async def _read_into(
        self, client: BleakClient, snapshot: Snapshot, uuids: tuple[str, ...]
    ) -> None:
        for uuid in uuids:
            char = self._characteristic(client, uuid)
            data = bytes(await client.read_gatt_char(char))
            _LOGGER.debug("%s read %s: %s", self.address, uuid[4:8], data.hex())
            try:
                snapshot.update(uuid, data)
            except ProtocolError as err:
                _LOGGER.warning(
                    "%s: cannot decode %s (%s): %s",
                    self.address,
                    uuid[4:8],
                    data.hex(),
                    err,
                )

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> Snapshot:
        try:
            snapshot = await self._poll()
        except UpdateFailed as err:
            self._failures += 1
            if self._failures <= FAILURE_GRACE_POLLS and self._snapshot.status1:
                _LOGGER.debug(
                    "%s: poll %d failed (%s); keeping last data",
                    self.address,
                    self._failures,
                    err,
                )
                return self._snapshot
            raise
        self._failures = 0
        return snapshot

    async def _poll(self) -> Snapshot:
        async with self._lock:
            snapshot = self._snapshot.copy()
            try:
                client = await self._connect()
            except DeviceUnavailable as err:
                raise UpdateFailed(str(err)) from err
            except (BleakError, TimeoutError) as err:
                raise UpdateFailed(f"connection failed: {err}") from err
            try:
                now = time.monotonic()
                if (
                    snapshot.rating3 is None
                    or now - self._static_read_at > STATIC_REFRESH_SECONDS
                ):
                    await self._read_into(client, snapshot, STATIC_CHARACTERISTICS)
                    self._static_read_at = now
                await self._read_into(client, snapshot, DYNAMIC_CHARACTERISTICS)
            except (BleakError, TimeoutError, ProtocolError) as err:
                raise UpdateFailed(f"read failed: {err}") from err
            finally:
                await _disconnect(client)
            self._snapshot = snapshot
            return snapshot

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def async_write_settings1(
        self, encoder: Callable[[Settings1], bytes]
    ) -> None:
        """Read settings block 1, apply ``encoder`` and write it back."""
        await self._async_write(CHAR_SETTINGS_1, Settings1, encoder)

    async def async_write_settings2(
        self, encoder: Callable[[Settings2], bytes]
    ) -> None:
        """Read settings block 2, apply ``encoder`` and write it back."""
        await self._async_write(CHAR_SETTINGS_2, Settings2, encoder)

    async def _async_write(
        self,
        uuid: str,
        parser: type[Settings1] | type[Settings2],
        encoder: Callable[[Any], bytes],
    ) -> None:
        async with self._lock:
            snapshot = self._snapshot.copy()
            try:
                client = await self._connect()
            except (DeviceUnavailable, BleakError, TimeoutError) as err:
                raise HomeAssistantError(
                    f"Cannot connect to Xantrex panel {self.address}: {err}"
                ) from err
            try:
                char = self._characteristic(client, uuid)
                current = bytes(await client.read_gatt_char(char))
                payload = encoder(parser.parse(current))
                if len(payload) != len(current):
                    raise ProtocolError(
                        f"encoded {len(payload)} bytes, device block is {len(current)}"
                    )
                _LOGGER.debug(
                    "%s write %s: %s -> %s",
                    self.address,
                    uuid[4:8],
                    current.hex(),
                    payload.hex(),
                )
                if payload != current:
                    await client.write_gatt_char(char, payload, response=True)
                    await asyncio.sleep(0.5)
                await self._read_into(client, snapshot, DYNAMIC_CHARACTERISTICS)
            except (BleakError, TimeoutError, ProtocolError) as err:
                raise HomeAssistantError(
                    f"Writing to Xantrex panel {self.address} failed: {err}"
                ) from err
            finally:
                await _disconnect(client)
            self._snapshot = snapshot
        self.async_set_updated_data(snapshot)


async def _disconnect(client: BleakClient) -> None:
    try:
        await client.disconnect()
    except BleakError as err:  # pragma: no cover - best effort
        _LOGGER.debug("disconnect error: %s", err)


async def async_probe(
    hass: HomeAssistant, device: BLEDevice
) -> tuple[Snapshot, int | None]:
    """Connect once and read the static blocks (used by the config flow)."""
    client = await establish_connection(
        BleakClientWithServiceCache,
        device,
        device.address,
        max_attempts=CONNECT_ATTEMPTS,
        timeout=CONNECT_TIMEOUT,
    )
    snapshot = Snapshot()
    try:
        service = client.services.get_service(SERVICE_UUID)
        if service is None:
            raise ProtocolError("Xantrex service 0x1910 not found")
        for uuid in STATIC_CHARACTERISTICS + DYNAMIC_CHARACTERISTICS:
            char = service.get_characteristic(uuid)
            if char is None:
                raise ProtocolError(f"characteristic {uuid} missing")
            snapshot.update(uuid, bytes(await client.read_gatt_char(char)))
    finally:
        await _disconnect(client)
    info = bluetooth.async_last_service_info(hass, device.address, connectable=True)
    return snapshot, info.rssi if info else None
