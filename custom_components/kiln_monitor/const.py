"""Constants for the Kiln Monitor integration."""
from __future__ import annotations

from typing import Any

DOMAIN = "kiln_monitor"


def dig(data: Any, path: list[str]) -> Any:
    """Walk ``path`` through nested dicts, returning ``None`` if anything is missing.

    Bails out the moment a level isn't a dict or a key is absent so callers never
    end up coercing ``{}`` to a number.
    """
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data

# API URLs
LOGIN_URL = "https://bartinst-user-service-prod.herokuapp.com/login"
SETTINGS_URL = "https://kiln.bartinst.com/kilns/settings"
DATA_URL = "https://kiln.bartinst.com/kilns/data"
# Firing status used by the web client; supplies estimated time remaining and
# the current program segment. Takes the external id (kiln_id) as a string.
STATUS_URL = "https://kiln.bartinst.com/kilnaid-data/status"

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_ACTIVE_UPDATE_INTERVAL = "active_update_interval"
CONF_IDLE_UPDATE_INTERVAL = "idle_update_interval"

# Default values
DEFAULT_ACTIVE_UPDATE_INTERVAL = 5   # minutes, used while a kiln is firing
DEFAULT_IDLE_UPDATE_INTERVAL = 15    # minutes, used when the kiln is idle

# kilnStatus strings that should trigger fast polling (case-insensitive)
ACTIVE_KILN_STATUSES = frozenset({"firing"})

# Path to the kiln's lifetime firing counter in the API response. Shared by the
# numFirings sensor and the element-tracking logic so the two never drift.
NUMFIRINGS_DATA_PATH = ["settings", "numFirings"]

# Sensor definitions
SENSORS = {
    "temperature": {
        "name": "Temperature",
        "unit": "°F",
        "device_class": "temperature",
        "state_class": "measurement",
        "data_path": ["list", "temperature"],
        "value_type": float,
    },
    "kilnStatus": {
        "name": "Status",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "data_path": ["list", "kilnStatus"],
        "value_type": str,
    },
    "firmwareVersion": {
        "name": "Firmware Version",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "data_path": ["settings", "firmwareVersion"],
        "value_type": str,
    },
    "numFirings": {
        "name": "Number of Firings",
        "unit": "firings",
        "device_class": None,
        "state_class": "total_increasing",
        "data_path": NUMFIRINGS_DATA_PATH,
        "value_type": int,
    },
    "numZones": {
        "name": "Zone Count",
        "unit": "zones",
        "device_class": None,
        "state_class": None,
        "data_path": ["settings", "numZones"],
        "value_type": int,
    },
    # Firing details from the /kilnaid-data/status endpoint. These are only
    # meaningful while a firing is in progress; the API leaves stale values when
    # the kiln is idle.
    "estimatedTimeRemaining": {
        "name": "Estimated Time Remaining",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "data_path": ["status", "estimatedTimeRemaining"],
        "value_type": str,
    },
    "firingTime": {
        "name": "Firing Time",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "data_path": ["status", "firingTime"],
        "value_type": str,
    },
    "holdRemainingTime": {
        "name": "Hold Remaining Time",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "data_path": ["status", "holdRemainingTime"],
        "value_type": str,
    },
    "segment": {
        "name": "Current Segment",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "data_path": ["status", "segment"],
        "value_type": str,
    },
    "setPoint": {
        "name": "Set Point",
        "unit": "°F",
        "device_class": "temperature",
        "state_class": "measurement",
        "data_path": ["status", "setPoint"],
        "value_type": float,
    },
    "programName": {
        "name": "Program Name",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "data_path": ["status", "programName"],
        "value_type": str,
    },
}