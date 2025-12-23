from __future__ import annotations
from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# =============================
# Config Flow Keys
# =============================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# =============================
# AI Select
# =============================
AI_MODE_ENTITY = "ai_mode"

AI_MODE_AUTO = "auto"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

AI_MODES = [
    AI_MODE_AUTO,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
]

# =============================
# Defaults
# =============================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0

DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_EXPENSIVE = 0.35
DEFAULT_VERY_EXPENSIVE = 0.49

UPDATE_INTERVAL = 10
