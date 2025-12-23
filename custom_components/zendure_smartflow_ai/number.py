from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DOMAIN,
    DEVICE_NAME,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
)


@dataclass
class _NumDef:
    key: str
    name: str
    icon: str
    min_v: float
    max_v: float
    step: float
    default: float
    unit: str | None = None


NUMBERS: list[_NumDef] = [
    _NumDef("soc_min", "SoC Min", "mdi:battery-10", 0, 100, 1, float(DEFAULT_SOC_MIN), "%"),
    _NumDef("soc_max", "SoC Max", "mdi:battery-90", 0, 100, 1, float(DEFAULT_SOC_MAX), "%"),
    _NumDef("max_charge", "Max. Ladeleistung", "mdi:flash", 0, 5000, 1, float(DEFAULT_MAX_CHARGE), "W"),
    _NumDef("max_discharge", "Max. Entladeleistung", "mdi:flash-outline", 0, 5000, 1, float(DEFAULT_MAX_DISCHARGE), "W"),
    _NumDef("price_threshold", "Teuer-Schwelle", "mdi:currency-eur", 0, 2.0, 0.01, float(DEFAULT_PRICE_THRESHOLD), "€/kWh"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities([ZendureSettingNumber(entry, nd) for nd in NUMBERS])


class ZendureSettingNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, nd: _NumDef) -> None:
        self._entry = entry
        self._def = nd
        self._attr_name = nd.name
        self._attr_icon = nd.icon
        self._attr_native_min_value = nd.min_v
        self._attr_native_max_value = nd.max_v
        self._attr_native_step = nd.step
        self._attr_native_unit_of_measurement = nd.unit

        # Stable entity_id suggestions (so coordinator can read them)
        # -> number.zendure_smartflow_ai_soc_min etc.
        self._attr_suggested_object_id = f"{DOMAIN}_{nd.key}"

        self._value = nd.default

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_{self._def.key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": DEVICE_NAME,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        # Round to step (no crazy decimals on iPad UI)
        if self._def.step >= 1:
            self._value = float(int(round(value, 0)))
        else:
            self._value = float(round(value, 2))
        self.async_write_ha_state()
