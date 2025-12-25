from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            ZendureSettingNumber(entry, SETTING_SOC_MIN, "SoC Min (%)", DEFAULT_SOC_MIN, 0, 100, 1, "%"),
            ZendureSettingNumber(entry, SETTING_SOC_MAX, "SoC Max (%)", DEFAULT_SOC_MAX, 0, 100, 1, "%"),
            ZendureSettingNumber(entry, SETTING_MAX_CHARGE, "Max Ladeleistung (W)", DEFAULT_MAX_CHARGE, 0, 2400, 1, "W"),
            ZendureSettingNumber(entry, SETTING_MAX_DISCHARGE, "Max Entladeleistung (W)", DEFAULT_MAX_DISCHARGE, 0, 2400, 1, "W"),
            ZendureSettingNumber(entry, SETTING_PRICE_THRESHOLD, "Teuer-Schwelle (€/kWh)", DEFAULT_PRICE_THRESHOLD, 0, 2, 0.01, "€/kWh"),
            ZendureSettingNumber(entry, SETTING_VERY_EXPENSIVE, "Sehr teuer (€/kWh)", DEFAULT_VERY_EXPENSIVE, 0, 2, 0.01, "€/kWh"),
        ],
        True,
    )


class ZendureSettingNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        key: str,
        name: str,
        default: float,
        min_v: float,
        max_v: float,
        step: float,
        unit: str | None,
    ):
        self.entry = entry
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_setting_{key}"
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._value = float(default)

        # Deterministisches entity_id Objekt (wichtig für Coordinator)
        self.entity_id = f"number.{DOMAIN}_{key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SmartFlow AI",
        }

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = float(value)
        self.async_write_ha_state()
