from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
)
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureNumber(coordinator, entry, "Zendure SoC Minimum", "mdi:battery-low", SETTING_SOC_MIN, DEFAULT_SOC_MIN, 0, 100, 1),
            ZendureNumber(coordinator, entry, "Zendure SoC Maximum", "mdi:battery-high", SETTING_SOC_MAX, DEFAULT_SOC_MAX, 0, 100, 1),
            ZendureNumber(coordinator, entry, "Zendure Max Ladeleistung", "mdi:flash", SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE, 0, 5000, 50),
            ZendureNumber(coordinator, entry, "Zendure Max Entladeleistung", "mdi:flash-outline", SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE, 0, 5000, 50),
            ZendureNumber(coordinator, entry, "Zendure Teuer-Schwelle", "mdi:cash", SETTING_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD, 0.0, 2.0, 0.01),
        ]
    )


class ZendureNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry: ConfigEntry,
        name: str,
        icon: str,
        key: str,
        default: float,
        min_v: float,
        max_v: float,
        step: float,
    ) -> None:
        self.coordinator = coordinator
        self.entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._key = key
        self._default = float(default)

        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_native_step = step

        # Units
        if key in (SETTING_SOC_MIN, SETTING_SOC_MAX):
            self._attr_native_unit_of_measurement = "%"
        elif key in (SETTING_MAX_CHARGE, SETTING_MAX_DISCHARGE):
            self._attr_native_unit_of_measurement = "W"
        elif key == SETTING_PRICE_THRESHOLD:
            self._attr_native_unit_of_measurement = "€/kWh"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.settings.get(self._key, self._default)
        try:
            return float(v)
        except Exception:
            return float(self._default)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.settings[self._key] = float(value)
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state not in ("unknown", "unavailable", ""):
            try:
                self.coordinator.settings[self._key] = float(str(last.state).replace(",", "."))
                return
            except Exception:
                pass
        self.coordinator.settings[self._key] = float(self._default)
