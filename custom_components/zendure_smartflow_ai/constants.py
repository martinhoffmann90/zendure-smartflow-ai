from __future__ import annotations

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[str] = ["sensor", "number", "select"]

# Betriebsmodi (intern)
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

MODES = [MODE_AUTOMATIC, MODE_SUMMER, MODE_WINTER, MODE_MANUAL]

# Option-Keys (ConfigEntry.options)
OPT_MODE = "mode"
OPT_SOC_MIN = "soc_min"
OPT_SOC_MAX = "soc_max"

# Defaultwerte (falls weder Options noch Helper existieren)
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 95.0
