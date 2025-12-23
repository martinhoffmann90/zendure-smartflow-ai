from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    DATA_COORDINATOR,
    # keys
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_EXPENSIVE,
    SETTING_PRICE_VERY_EXPENSIVE,
    SETTING_PRICE_CHEAP,
    SETTING_SURPLUS_MIN,
    SETTING_MANUAL_CHARGE_W,
    SETTING_MANUAL_DISCHARGE_W,
    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_EXPENSIVE,
    DEFAULT_PRICE_VERY_EXPENSIVE,
    DEFAULT_PRICE_CHEAP,
    DEFAULT_SURPLUS_MIN,
    DEFAULT_MANUAL_CHARGE_W,
    DEFAULT_MANUAL_DISCHARGE_W,
)


@dataclass
class _NumDef:
    key: str
    name: str
    icon: str
    unit: str | None
    min_value: float
    max_value: float
    step: float
    default: float


NUMBERS: list[_NumDef] = [
    _NumDef(SETTING_SOC_MIN, "Zendure SoC Minimum", "mdi:battery-low", "%", 5, 50, 1, DEFAULT_SOC_MIN),
    _NumDef(SETTING_SOC_MAX, "Zendure SoC Maximum", "mdi:battery-high", "%", 50, 100, 1, DEFAULT_SOC_MAX),

    _NumDef(SETTING_MAX_CHARGE, "Zendure Max Ladeleistung", "mdi:flash", "W", 0, 5000, 50, DEFAULT_MAX_CHARGE),
    _NumDef(SETTING_MAX_DISCHARGE, "Zendure Max Entladeleistung", "mdi:flash-outline", "W", 0, 5000, 50, DEFAULT_MAX_DISCHARGE),

    _NumDef(SETTING_PRICE_EXPENSIVE, "Preis-Schwelle Teuer", "mdi:currency-eur", "€/kWh", 0.0, 2.0, 0.01, DEFAULT_PRICE_EXPENSIVE),
    _NumDef(SETTING_PRICE_VERY_EXPENSIVE, "Preis-Schwelle Sehr teuer", "mdi:currency-eur", "€/kWh", 0.0, 2.0, 0.01, DEFAULT_PRICE_VERY_EXPENSIVE),
    _NumDef(SETTING_PRICE_CHEAP, "Preis-Schwelle Günstig", "mdi:currency-eur", "€/kWh", 0.0, 2.0, 0.01, DEFAULT_PRICE_CHEAP),

    _NumDef(SETTING_SURPLUS_MIN, "PV-Überschuss Mindestwert", "mdi:solar-power", "W", 0, 2000, 10, DEFAULT_SURPLUS_MIN),

    _NumDef(SETTING_MANUAL_CHARGE_W, "Manuell Laden (W)", "mdi:hand-extended", "W", 0, 5000, 50, DEFAULT_MANUAL_CHARGE_W),
    _NumDef(SETTING_MANUAL_DISCHARGE_W, "Manuell Entladen (W)", "mdi:hand-extended", "W", 0, 5000, 50, DEFAULT_MANUAL_DISCHARGE_W),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([ZendureSettingNumber(hass, entry, coordinator, d) for d in NUMBERS], True)


class ZendureSettingNumber(NumberEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator, d: _NumDef) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.defn = d

        self._attr_name = d.name
        self._attr_icon = d.icon
        self._attr_native_unit_of_measurement = d.unit
        self._attr_native_min_value = d.min_value
        self._attr_native_max_value = d.max_value
        self._attr_native_step = d.step

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "TK-Multimedia / Community",
            "model": "SmartFlow AI",
        }

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_setting_{self.defn.key}"

    @property
    def native_value(self) -> float:
        return float((self.entry.options or {}).get(self.defn.key, self.defn.default))

    async def async_set_native_value(self, value: float) -> None:
        opts = dict(self.entry.options or {})
        opts[self.defn.key] = float(value)
        self.hass.config_entries.async_update_entry(self.entry, options=opts)
        await self.coordinator.async_request_refresh()
