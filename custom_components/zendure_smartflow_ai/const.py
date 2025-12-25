from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# -------------------------
# Config Flow Keys
# -------------------------
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

# Preisquelle optional (Tibber Datenexport mit attributes.data)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

# Zendure Steuer-Entitäten (aus Zendure/SolarFlow Integration)
CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# Optional (für spätere Ausbaustufen / Kompatibilität)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# -------------------------
# Integration Settings (Numbers)
# -------------------------
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE = "very_expensive_threshold"

# -------------------------
# Defaults (Hersteller/Best Practice)
# -------------------------
DEFAULT_SOC_MIN = 12
DEFAULT_SOC_MAX = 100  # Herstellerempfehlung ✔
DEFAULT_MAX_CHARGE = 2400
DEFAULT_MAX_DISCHARGE = 2400
DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE = 0.49

# -------------------------
# Update
# -------------------------
UPDATE_INTERVAL = 10  # Sekunden

# -------------------------
# Modes / Selects
# -------------------------
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
