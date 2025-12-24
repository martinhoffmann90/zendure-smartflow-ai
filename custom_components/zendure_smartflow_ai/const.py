from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Domain / Platforms
# ==================================================
DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# ==================================================
# Config Flow – Entity Auswahl
# ==================================================
CONF_SOC_ENTITY = "soc_entity"                      # % SoC
CONF_PV_ENTITY = "pv_entity"                        # W PV-Leistung
CONF_LOAD_ENTITY = "load_entity"                    # W Hausverbrauch
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"    # Tibber-Export (Attr: data[]), optional

CONF_AC_MODE_ENTITY = "ac_mode_entity"              # select.* input/output
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"      # number.* W
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"    # number.* W

# Optional (für später / kompatibel, nicht zwingend genutzt in 0.7.0)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Settings (Entry Options) – intern, keine Helper nötig
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"
SETTING_FREEZE_SECONDS = "freeze_seconds"
SETTING_AI_MODE = "ai_mode"
SETTING_MANUAL_ACTION = "manual_action"

# ==================================================
# Defaults (Vorgaben)
# ==================================================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Herstellerempfehlung
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

DEFAULT_FREEZE_SECONDS = 120
DEFAULT_UPDATE_INTERVAL = 10

# Backward compatibility aliases (falls irgendwo alte Namen genutzt wurden)
DEFAULT_EXPENSIVE_THRESHOLD = DEFAULT_PRICE_THRESHOLD

# ==================================================
# Select Options (intern)
# ==================================================
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

# ==================================================
# Recommendation states
# ==================================================
REC_STANDBY = "standby"
REC_CHARGE = "charge"
REC_DISCHARGE = "discharge"
REC_HOLD = "hold"

# ==================================================
# Status states
# ==================================================
STATUS_INIT = "init"
STATUS_OK = "ok"
STATUS_SENSOR_INVALID = "sensor_invalid"
STATUS_PRICE_INVALID = "price_invalid"
STATUS_MANUAL_ACTIVE = "manual_mode_active"
