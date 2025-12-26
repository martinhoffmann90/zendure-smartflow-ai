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

# Preis optional (entweder Export-Daten oder Current-Price)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"
CONF_PRICE_NOW_ENTITY = "price_now_entity"

# Zendure AC Steuerung (remember: das sind ENTITÄTEN aus der Zendure Integration)
CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# Grid optional (für Load-Berechnung)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# -------------------------
# Options / Settings (werden in entry.options gespeichert)
# -------------------------
OPT_AI_MODE = "ai_mode"
OPT_MANUAL_ACTION = "manual_action"

OPT_SOC_MIN = "soc_min"
OPT_SOC_MAX = "soc_max"
OPT_MAX_CHARGE = "max_charge"
OPT_MAX_DISCHARGE = "max_discharge"
OPT_PRICE_THRESHOLD = "price_threshold"
OPT_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"

# -------------------------
# Defaults
# -------------------------
UPDATE_INTERVAL = 10  # Sekunden

DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Hersteller/Anwender-Empfehlung ✔
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0
DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

# -------------------------
# Select Options (intern, stable keys)
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

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS = [
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
]

# -------------------------
# Internal Sensor Keys (translation_key / entity_description key)
# -------------------------
SENSOR_STATUS = "status"
SENSOR_AI_STATUS = "ai_status"
SENSOR_AI_DEBUG = "ai_debug"
