from __future__ import annotations
from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# =========================
# Config Flow Keys
# =========================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"

CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# =========================
# Defaults
# =========================
UPDATE_INTERVAL = 10

DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0

DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_EXPENSIVE = 0.35
DEFAULT_PRICE_VERY_EXPENSIVE = 0.49

# =========================
# AI Modes (internal)
# =========================
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

MANUAL_ACTION_STANDBY = "standby"
MANUAL_ACTION_CHARGE = "charge"
MANUAL_ACTION_DISCHARGE = "discharge"

MANUAL_ACTIONS = [
    MANUAL_ACTION_STANDBY,
    MANUAL_ACTION_CHARGE,
    MANUAL_ACTION_DISCHARGE,
]
