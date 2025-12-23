from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# =========================
# Timing
# =========================
UPDATE_INTERVAL = 10          # Sekunden
FREEZE_SECONDS = 120          # Nur Anzeige (Status/Empfehlung), NICHT Steuerung

# =========================
# Config Flow – Entity Auswahl
# =========================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Datenexport (attributes.data) optional

CONF_AC_MODE_ENTITY = "ac_mode_entity"            # Zendure Select: input/output
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"    # Zendure Number (W)
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"  # Zendure Number (W)

# Grid (optional, Reserve für spätere Versionen / andere Setups)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# =========================
# Settings Keys (Number/Select Entities der Integration)
# =========================
SETTING_OPERATION_MODE = "operation_mode"
SETTING_MANUAL_ACTION = "manual_action"

SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"

SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"

SETTING_PRICE_EXPENSIVE = "price_expensive"
SETTING_PRICE_VERY_EXPENSIVE = "price_very_expensive"
SETTING_PRICE_CHEAP = "price_cheap"

SETTING_SURPLUS_MIN = "surplus_min"

SETTING_MANUAL_CHARGE_W = "manual_charge_w"
SETTING_MANUAL_DISCHARGE_W = "manual_discharge_w"

# =========================
# Operation Modes (Integration)
# =========================
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

OPERATION_MODES = [MODE_AUTOMATIC, MODE_SUMMER, MODE_WINTER, MODE_MANUAL]

# =========================
# Manual Actions
# =========================
MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE]

# =========================
# Defaults (wichtig: SoC max default 100%)
# =========================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0

DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_EXPENSIVE = 0.35
DEFAULT_PRICE_VERY_EXPENSIVE = 0.49
DEFAULT_PRICE_CHEAP = 0.25

DEFAULT_SURPLUS_MIN = 80.0

DEFAULT_MANUAL_CHARGE_W = 300.0
DEFAULT_MANUAL_DISCHARGE_W = 300.0

DEFAULT_OPERATION_MODE = MODE_AUTOMATIC
DEFAULT_MANUAL_ACTION = MANUAL_STANDBY

# =========================
# Internal keys
# =========================
DATA_COORDINATOR = "coordinator"
