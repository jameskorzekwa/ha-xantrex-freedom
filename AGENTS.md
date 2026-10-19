# ha-xantrex-freedom

## OVERVIEW
HA custom integration (domain `xantrex_freedom`) polling a Xantrex Freedom X Bluetooth Remote Panel (808-0817-02) over BLE GATT. Reverse-engineered from the Capacitor/Angular Xantrex app 1.6.1 (`com.xantrex.app`; it ships source maps, see `src/app/Protocol/FXC/` and `ble/central.service.ts`). Works for Freedom X inverters and XC / XC PRO inverter/chargers.

## STRUCTURE
```
custom_components/xantrex_freedom/
├── protocol.py      # ALL wire decoding/encoding; NO homeassistant imports (unit tested)
├── coordinator.py   # DataUpdateCoordinator: connect → read blocks → disconnect; write helpers; async_probe for config flow
├── config_flow.py   # bluetooth/user discovery, confirm step probes device; options flow (scan_interval)
├── entity.py        # XantrexEntity base + DeviceInfo (model/serial/firmware from snapshot)
├── sensor.py / binary_sensor.py / switch.py / select.py / number.py  # table-driven EntityDescriptions
├── diagnostics.py   # raw hex of every characteristic + all decoded blocks
├── const.py, manifest.json, strings.json, translations/en.json, brand/
tests/test_protocol.py
.github/scripts/build_release.sh   # zips integration → xantrex_freedom.zip (HACS zip_release)
```

## WHERE TO LOOK
| Task | Location |
|------|----------|
| Field offsets / scaling / enums | `protocol.py` (`Status1`, `Status2`, `Settings1`, `Settings2`, `Rating*`) |
| Model table (0x2A07 byte 4) | `protocol.MODELS` |
| Add a sensor | `sensor.SENSORS` tuple + `strings.json` + `translations/en.json` |
| Add a writable setting | encoder `with_*` on `Settings1/2` in `protocol.py`, then switch/select/number description |
| BLE connect/read/write | `coordinator.XantrexCoordinator` |
| Discovery matching | `manifest.json` `bluetooth` matchers + `config_flow._is_candidate` |

## CODE MAP
- `Snapshot` — holds `raw[uuid]` bytes plus decoded dataclasses; `update(uuid, data)` decodes via `_PARSERS`; derived `battery_current` (signed, charge wins when > discharge, mirroring the app), `battery_power`, `ac_input_power`.
- `Settings1.with_*` / `Settings2.with_*` — return a full new byte block (same length as read) with only the target bytes changed; coordinator always re-reads before encoding so stale snapshots are never written.
- `XantrexCoordinator._async_write` — lock, connect, read block, encode, write(response=True) only if changed, sleep 0.5 s, re-read dynamic blocks, `async_set_updated_data`.
- `async_probe` — one-shot connect used by the config flow; must find service 0x1910 and all static+dynamic characteristics, else `ProtocolError` → `not_supported`.
- Static blocks (firmware, serial, ratings, model) read on first poll and every `STATIC_REFRESH_SECONDS`; dynamic blocks (2A03, 2A04, 2A0D, 2A0E) every poll.
- `keep_connected` option (default on): `_connect` reuses `self._client`; `_release` only disconnects when the option is off; `_forget` drops the client after any error so the next poll reconnects; `async_shutdown` on unload. `_start_burst` after every write: `async_refresh()` every `BURST_POLL_INTERVAL` (3 s) for `BURST_POLL_SECONDS` (90 s) as a config-entry background task.

## CONVENTIONS
- Addresses uppercase; unique_id = `<ADDRESS>_<key>`; device identifier `(DOMAIN, ADDRESS)`.
- Entities with `enabled_fn` are only *created* when the predicate holds at setup (charger-only or non-LFP entities); `entity_registry_enabled_default=False` hides noisy ones.
- All enum states are snake_case translation keys (`working_mode`, `charging_status`, `battery_type`, ...).
- `protocol.py` stays HA-free; tests import it directly (`pythonpath=["."]`, `asyncio_mode=auto`).
- Ruff: line-length 88, py314, rules E,F,I,UP,B,ASYNC. Test deps track current HA (`pytest-homeassistant-custom-component`, Python 3.14).

## ANTI-PATTERNS / GOTCHAS
- Characteristic UUIDs 0x2A01–0x2A0E are SIG-assigned numbers; ALWAYS resolve them through service 0x1910 (`client.services.get_service(SERVICE_UUID).get_characteristic(uuid)`), never by bare UUID.
- The panel allows one central; the default held connection blocks the Xantrex phone app (documented in the option description). While connected the panel stops advertising, so the RSSI sensor goes stale.
- Output power limit (2A0D bytes 13-14) is stored in hundreds of watts (confirmed live: raw 20 = 2000 W). The Xantrex app writes plain watts there, which is an app bug; `with_output_power_limit(watts)` writes `watts // 100`.
- `Status2.heat_sink_temperature` is left RAW: the app says °C but a Freedom X 2000 idling at ~17 °C ambient reported 578, then fell to ~500 over an hour with ambient flat (a cooling heat sink). Candidates: `(raw-400)/10` °C (17.8), tenths of °F (14.3), `raw/2` K (15.9). Confirm with a cold-night or hot-load reading before adding a unit.
- `line_fail` (0x20) is set whenever there is no AC input; it is in `INFORMATIONAL_WARNINGS` and excluded from `active_faults` / the problem sensor.
- 2A0E byte 15 `inverter_on` is decoded by the app but not shown in its UI. VERIFIED live 2026-10-18 on a Freedom X 2000: writing 0 → device reports 0 at once, working mode `S` (standby) and 0 V output about 30 s later; writing 1 → mode `B` and 120 V output about 40 s later. Entities lag the switch by one or two polls; that is the inverter, not the integration.
- Write path verified live 2026-10-18 (power-limit timer 300→290→300, read back from the device each time, ~3.5 s per write).
- Flag 0x0100 is named "silence buzzer" in the app source but the app UI treats set = *audible alarm enabled*; we follow the UI.
- `battery_capacity` is a lead-acid voltage estimate; the app hides it for battery types 3 (custom) and 4 (LiFePO4); so do we.
- The Pi scanner on the trailer HA sees the 0x1910 advertisement but not the `ID…` scan-response name; the ESPHome proxy does. HA rejects `local_name` patterns in the first 3 chars (`ID*` broke the whole bluetooth component on a live install), so the manifest matches on service uuid only; `_is_candidate` also accepts the name and rejects `_is_candidate` rejecting anything with manufacturer/service data.

- The remote panel's power button also powers its BLE radio down. After it comes back, BlueZ/bleak-retry-connector may hand back a cached GATT table without service 0x1910 ("service 0x1910 not found" on every poll, reload does not help). `StaleServicesError` → `client.clear_cache()` → next poll rediscovers. Seen live 2026-10-18 when the owner cycled the display.

- Freedom X Power Save *Timer* (2A0D byte 7, setting 05) = hard auto-shutdown that also unpowers the remote panel → device vanishes from HA (seen 2026-10-18: timer 3 h → standby byte 0 at +3:01, adverts gone 2 min later). Owner guidance: keep it at 0/OFF and use the HA automation `inverter_idle_standby` on the trailer HA instead. Power Save *Mode* (flag 0x0040) is load sensing and harmless.

## COMMANDS
```sh
uv venv -p 3.14 .venv && uv pip install -p .venv/bin/python -r requirements-test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
bash .github/scripts/build_release.sh   # needs zip/unzip
```
