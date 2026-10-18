# Xantrex Freedom X/XC for Home Assistant

Home Assistant custom integration for Xantrex **Freedom X** inverters and
**Freedom XC / XC PRO** inverter/chargers, read through the
**Freedom X Bluetooth Remote Panel** (Xantrex part 808-0817-02).

The panel is polled over Bluetooth Low Energy by any adapter Home Assistant
can use, including ESPHome Bluetooth proxies. No cloud, no Xantrex account,
and nothing is installed on the inverter.

## What you get

**Sensors**

- AC input (shore/utility): voltage, frequency, current, power
- AC output (loads): voltage, frequency, power, apparent power, load %
- Battery: voltage, current (signed: + charging, - inverting), power,
  lead-acid capacity estimate (hidden for LiFePO4/custom battery types)
- Heat sink temperature, bus voltage, working mode (standby / line /
  battery / fault / power saving), charging stage (XC only)
- Active fault count with the decoded fault list as attributes

**Binary sensors**

- Problem (any fault bit), overload, over temperature, battery low,
  battery voltage high, fan locked, output short circuit
- AC input present, inverting, load detected

**Controls** (the same settings the Xantrex app exposes)

- Inverter on/off switch
- Power saving mode, audible alarm, equalize charging (XC)
- Inverter ignition control, transfer mode (appliance/UPS), shutdown
  recovery (auto/manual restart), output voltage and frequency
- Low battery cut-off voltage, delay and recovery voltage, power save time,
  utility AC under-voltage level, output power limit timer
- XC only: battery type, battery temperature, charger current, custom
  absorption/float voltages, breaker rating, charger ignition control

Settings are written exactly the way the official app does it: the
settings block is read, the bytes for one setting are changed, and the
whole block is written back, then re-read to confirm.

## Installation

1. Add this repository to HACS as a custom repository (category
   *Integration*) and install **Xantrex Freedom X/XC**, or copy
   `custom_components/xantrex_freedom` into your `config/custom_components`.
2. Restart Home Assistant.
3. With the inverter powered and the Xantrex phone app **not** connected,
   Home Assistant will discover the panel (it advertises as `ID` followed by
   the serial number). Otherwise add it under *Settings → Devices & services
   → Add integration → Xantrex Freedom X/XC*.

The default poll interval is 30 s and can be changed in the integration's
options. Each poll holds the BLE connection for about a second; the Xantrex
app can connect in between. If the app is connected, polls fail until it
disconnects.

## Protocol

The panel exposes GATT service `0x1910` with characteristics `0x2A01` to
`0x2A0E`. Those UUIDs collide with Bluetooth SIG assigned numbers
(Appearance, Reconnection Address, ...), which is why generic scanners
mislabel them; the payloads are Xantrex's own. Everything is a plain read,
with `0x2A0D` and `0x2A0E` also writable. The field layout and scaling in
`protocol.py` were derived from the official Xantrex app (1.6.1) and are
summarised in that file's docstrings.

| Characteristic | Content |
| --- | --- |
| 2A01 | Protocol id, main-board and remote-panel firmware versions |
| 2A02 | Serial number |
| 2A03 | Live status 1: AC in/out V, Hz, VA, W, load %, bus V, battery V, charge A |
| 2A04 | Live status 2: capacity %, heat sink °C, AC in A, discharge A, charging stage, 32 fault bits, working mode |
| 2A05–2A07 | Ratings, model id, communication-board firmware |
| 2A0A–2A0C | Factory defaults and setting ranges |
| 2A0D | Settings 1 (ignition, LBCO, power save, output V/Hz, power limit, transfer mode, utility under-voltage) |
| 2A0E | Settings 2 (battery type/temperature, charger, breaker, flags, inverter on/off) |

## Development

```sh
uv venv -p 3.14 .venv && uv pip install -p .venv/bin/python -r requirements-test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
```

`protocol.py` has no Home Assistant imports and is covered by
`tests/test_protocol.py`. The config entry diagnostics download includes the
raw bytes of every characteristic, which is the first thing to attach to a
bug report for an unsupported model.

## Disclaimer

Not affiliated with Xantrex / Mission Critical Electronics. Changing
inverter settings can damage batteries or connected equipment; the controls
are provided as-is.
