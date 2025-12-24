from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SETTING_SOC_MIN, SETTING_SOC_MAX, SETTING_MAX_CHARGE, SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD, SETTING_VERY_EXPENSIVE_THRESHOLD, SETTING_FREEZE_SECONDS,
    DEFAULT_SOC_MIN, DEFAULT_SOC_MAX, DEFAULT_MAX_CHARGE, DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD, DEFAULT_FREEZE_SECONDS,
)
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class ZNumberDescription(NumberEntityDescription):
    setting_key: str = ""
    default: float = 0.0


NUMBERS: tuple[ZNumberDescription, ...] = (
    ZNumberDescription(
        key="soc_min",
        name="SoC Minimum",
        translation_key="soc_min",
        icon="mdi:battery-low",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        setting_key=SETTING_SOC_MIN,
        default=DEFAULT_SOC_MIN,
    ),
    ZNumberDescription(
        key="soc_max",
        name="SoC Maximum",
        translation_key="soc_max",
        icon="mdi:battery-high",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        setting_key=SETTING_SOC_MAX,
        default=DEFAULT_SOC_MAX,
    ),
    ZNumberDescription(
        key="max_charge",
        name="Max. Ladeleistung",
        translation_key="max_charge",
        icon="mdi:flash",
        native_min_value=0,
        native_max_value=6000,
        native_step=10,
        native_unit_of_measurement="W",
        setting_key=SETTING_MAX_CHARGE,
        default=DEFAULT_MAX_CHARGE,
    ),
    ZNumberDescription(
        key="max_discharge",
        name="Max. Entladeleistung",
        translation_key="max_discharge",
        icon="mdi:flash-outline",
        native_min_value=0,
        native_max_value=6000,
        native_step=10,
        native_unit_of_measurement="W",
        setting_key=SETTING_MAX_DISCHARGE,
        default=DEFAULT_MAX_DISCHARGE,
    ),
    ZNumberDescription(
        key="price_threshold",
        name="Schwelle: Teuer",
        translation_key="price_threshold",
        icon="mdi:cash-alert",
        native_min_value=0,
        native_max_value=2,
        native_step=0.001,
        native_unit_of_measurement="€/kWh",
        setting_key=SETTING_PRICE_THRESHOLD,
        default=DEFAULT_PRICE_THRESHOLD,
    ),
    ZNumberDescription(
        key="very_expensive_threshold",
        name="Schwelle: Sehr teuer",
        translation_key="very_expensive_threshold",
        icon="mdi:cash-lock",
        native_min_value=0,
        native_max_value=2,
        native_step=0.001,
        native_unit_of_measurement="€/kWh",
        setting_key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        default=DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    ),
    ZNumberDescription(
        key="freeze_seconds",
        name="Freeze (Sekunden)",
        translation_key="freeze_seconds",
        icon="mdi:snowflake",
        native_min_value=0,
        native_max_value=3600,
        native_step=1,
        native_unit_of_measurement="s",
        setting_key=SETTING_FREEZE_SECONDS,
        default=float(DEFAULT_FREEZE_SECONDS),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ZendureSmartFlowNumber(coordinator, entry, d) for d in NUMBERS])


class ZendureSmartFlowNumber(CoordinatorEntity[ZendureSmartFlowCoordinator], NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry, desc: ZNumberDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

    @property
    def native_value(self) -> float | None:
        val = self._entry.options.get(self.entity_description.setting_key, self.entity_description.default)
        try:
            return float(val)
        except Exception:
            return float(self.entity_description.default)

    async def async_set_native_value(self, value: float) -> None:
        new_opts = dict(self._entry.options)
        new_opts[self.entity_description.setting_key] = float(value)
        self.hass.config_entries.async_update_entry(self._entry, options=new_opts)
        self.async_write_ha_state()
        # Coordinator darf direkt neu berechnen
        await self.coordinator.async_request_refresh()
