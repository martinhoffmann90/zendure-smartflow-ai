from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Domain / Meta
# ==================================================
DOMAIN = "zendure_smartflow_ai"

INTEGRATION_NAME = "Zendure SmartFlow AI"
INTEGRATION_MANUFACTURER = "TK-Multimedia"
INTEGRATION_MODEL = "SmartFlow AI"
INTEGRATION_VERSION = "0.11.1"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# ==================================================
# Update
# ==================================================
UPDATE_INTERVAL = 10  # Sekunden

# ==================================================
# Config Flow – Entity Auswahl
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"

# Grid ist optional, aber empfohlen (für Load-Berechnung)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"     # signed (+import / -export)
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"   # import only
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"   # export only

# Preis ist optional
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Datenexport (attributes.data)
CONF_PRICE_NOW_ENTITY = "price_now_entity"        # optionaler Sensor mit €/kWh als state

# Zendure Steuer-Entitäten (SolarFlow AC)
CONF_AC_MODE_ENTITY = "ac_mode_entity"            # select input/output
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"    # number W
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"  # number W

# ==================================================
# Grid Modes
# ==================================================
GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

GRID_MODES = [GRID_MODE_NONE, GRID_MODE_SINGLE, GRID_MODE_SPLIT]

# ==================================================
# Integration Settings (Number Entities Keys)
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"

# ==================================================
# Defaults
# ==================================================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Herstellerempfehlung
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

# Backwards compatibility alias (falls irgendwo noch alter Name verwendet wird)
DEFAULT_EXPENSIVE_THRESHOLD = DEFAULT_PRICE_THRESHOLD

# ==================================================
# Status / Debug
# ==================================================
STATUS_INIT = "init"
STATUS_READY = "ready"
STATUS_ERROR = "error"

DEBUG_OK = "OK"
DEBUG_SENSOR_INVALID = "SENSOR_INVALID"
DEBUG_PRICE_INVALID = "PRICE_INVALID"

# ==================================================
# AI Modes / Manual Actions (interne Werte bleiben EN)
# ==================================================
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"
AI_MODES = [AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL]

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"
MANUAL_ACTIONS = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE]

# Zendure AC Mode Optionen (aus Zendure Select)
ZENDURE_MODE_INPUT = "input"
ZENDURE_MODE_OUTPUT = "output"
