"""Constants for the Kiln Monitor integration."""
from datetime import timedelta

DOMAIN = "kiln_monitor"

# API URLs
LOGIN_URL = "https://bartinst-user-service-prod.herokuapp.com/login"
SETTINGS_URL = "https://kiln.bartinst.com/kilns/settings"
DATA_URL = "https://kiln.bartinst.com/kilns/data"

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"

# Default values
DEFAULT_UPDATE_INTERVAL = 5  # minutes
SCAN_INTERVAL = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)

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
        "data_path": ["settings", "numFirings"],
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
}