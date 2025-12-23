from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import *

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([
        SimpleNumber(entry, "SoC Minimum", DEFAULT_SOC_MIN, 0, 50, 1),
        SimpleNumber(entry, "SoC Maximum", DEFAULT_SOC_MAX, 50, 100, 1),
        SimpleNumber(entry, "Max Ladeleistung", DEFAULT_MAX_CHARGE, 0, 3000, 50),
        SimpleNumber(entry, "Max Entladeleistung", DEFAULT_MAX_DISCHARGE, 0, 3000, 50),
        SimpleNumber(entry, "Teuer-Schwelle", DEFAULT_EXPENSIVE, 0.1, 1.0, 0.01),
        SimpleNumber(entry, "Sehr teuer-Schwelle", DEFAULT_VERY_EXPENSIVE, 0.1, 1.0, 0.01),
    ])


class SimpleNumber(NumberEntity):
    def __init__(self, entry, name, value, min_v, max_v, step):
        self._attr_unique_id = f"{entry.entry_id}_{name}"
        self._attr_name = f"Zendure {name}"
        self._attr_native_value = value
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_native_step = step

    async def async_set_native_value(self, value: float):
        self._attr_native_value = value
        self.async_write_ha_state()
