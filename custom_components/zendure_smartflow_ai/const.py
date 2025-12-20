from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# -------------------------
# ConfigFlow Keys
# -------------------------
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Export (attributes.data[])

CONF_AC_MODE_ENTITY = "ac_mode_entity"            # select.solarflow_*_ac_mode
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"    # number.* input limit
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"  # number.* output limit

CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"      # single sensor (+import/-export)
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"    # split import
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"    # split export

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# -------------------------
# Internal Settings (integration-owned)
# -------------------------
SETTING_MODE = "mode"
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"

# Betriebsmodi
MODE_MANUAL = "manual"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_AUTO = "auto"

MODES = [MODE_AUTO, MODE_SUMMER, MODE_WINTER, MODE_MANUAL]

# Defaults (V0.2.0)
DEFAULT_MODE = MODE_AUTO
DEFAULT_SOC_MIN = 15.0
DEFAULT_SOC_MAX = 100.0  # <<< wie von dir gewünscht (Hersteller/Anwender)
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0
DEFAULT_PRICE_THRESHOLD = 0.35

# kleine Totzonen / Schwellen
DEFAULT_EXPORT_CHARGE_MIN_W = 80.0
DEFAULT_IMPORT_DISCHARGE_MIN_W = 80.0
