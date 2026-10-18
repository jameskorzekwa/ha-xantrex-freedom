"""Constants for the Xantrex Freedom X/XC integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "xantrex_freedom"
MANUFACTURER = "Xantrex"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_ADDRESS = "address"
CONF_NAME = "name"
CONF_MODEL_ID = "model_id"
CONF_SERIAL_NUMBER = "serial_number"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_KEEP_CONNECTED = "keep_connected"

DEFAULT_SCAN_INTERVAL = 15
DEFAULT_KEEP_CONNECTED = True
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 600

#: Re-read the static blocks (firmware, serial, ratings) this often.
STATIC_REFRESH_SECONDS = 6 * 3600

#: Seconds to wait for a BLE connection before giving up on one poll.
CONNECT_TIMEOUT = 20.0
#: Maximum connection attempts per poll (bleak-retry-connector).
CONNECT_ATTEMPTS = 3

#: Consecutive failed polls tolerated (keeping the last data) before entities
#: go unavailable, e.g. while the Xantrex phone app holds the connection.
FAILURE_GRACE_POLLS = 2

#: After a setting is written, poll this often for this long so the inverter's
#: reaction (standby <-> inverting takes it tens of seconds) shows up quickly.
BURST_POLL_INTERVAL = 3.0
BURST_POLL_SECONDS = 90.0

#: AC input is considered present above this voltage.
AC_PRESENT_THRESHOLD_V = 60.0
