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

CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Datenexport (attributes.data), optional

CONF_AC_MODE_ENTITY = "ac_mode_entity"            # Zendure AC Mode select (input/output)
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"    # Zendure Input limit number (W)
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"  # Zendure Output limit number (W)

# (für später / optional – bleibt im Flow drin)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# -------------------------
# AI Operation Modes (Integration-Select)
# -------------------------
MODE_AUTOMATIC = "Automatik"
MODE_SUMMER = "Sommer"
MODE_WINTER = "Winter"
MODE_MANUAL = "Manuell"

AI_MODES = [MODE_AUTOMATIC, MODE_SUMMER, MODE_WINTER, MODE_MANUAL]

# -------------------------
# Default Settings (Integration-eigene Number-Entities)
# -------------------------
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Hersteller-/Anwenderempfehlung ✔

DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_THRESHOLD = 0.35  # €/kWh

# Verhalten
DEFAULT_UPDATE_INTERVAL = 10  # Sekunden
DEFAULT_FREEZE_SECONDS = 120  # nur Anzeige (Status/Recom), nicht Hardware

# kleine Totzonen (verhindert Flattern & Service-Spam)
MODE_CHANGE_MIN_SECONDS = 15
LIMIT_CHANGE_TOL_W = 25
