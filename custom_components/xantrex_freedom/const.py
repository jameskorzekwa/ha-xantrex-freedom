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

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
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

#: AC input is considered present above this voltage.
AC_PRESENT_THRESHOLD_V = 60.0
