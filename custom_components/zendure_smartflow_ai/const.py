from __future__ import annotations
from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

INTEGRATION_NAME = "Zendure SmartFlow AI"
INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "Smart Energy Controller"
INTEGRATION_VERSION = "0.11.0"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# --------------------
# Defaults
# --------------------
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0
DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

# ==================================================
# Update / Timing
# ==================================================
UPDATE_INTERVAL = 10  # Sekunden

# --------------------
# Runtime Modes
# --------------------
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

AI_MODES = [
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
]

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS = [
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
]
