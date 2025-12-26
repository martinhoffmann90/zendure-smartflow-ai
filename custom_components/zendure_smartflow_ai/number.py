from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    OPT_SOC_MIN,
    OPT_SOC_MAX,
    OPT_MAX_CHARGE,
    OPT_MAX_DISCHARGE,
    OPT_PRICE_THRESHOLD,
    OPT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
)


@dataclass(frozen=True, kw_only=True)
class ZendureNumberDescription(NumberEntityDescription):
    option_key: str
    default: float


NUMBERS: tuple[ZendureNumberDescription, ...] = (
    ZendureNumberDescription(
        key="soc_min",
        translation_key="soc_min",
        option_key=OPT_SOC_MIN,
        default=DEFAULT_SOC_MIN,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
        icon="mdi:battery-10",
    ),
    ZendureNumberDescription(
        key="soc_max",
        translation_key="soc_max",
        option_key=OPT_SOC_MAX,
        default=DEFAULT_SOC_MAX,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
        icon="mdi:battery",
    ),
    ZendureNumberDescription(
        key="max_charge",
        translation_key="max_charge",
        option_key=OPT_MAX_CHARGE,
        default=DEFAULT_MAX_CHARGE,
        native_min_value=0.0,
        native_max_value=2400.0,
        native_step=10.0,
        icon="mdi:transmission-tower-export",
    ),
    ZendureNumberDescription(
        key="max_discharge",
        translation_key="max_discharge",
        option_key=OPT_MAX_DISCHARGE,
        default=DEFAULT_MAX_DISCHARGE,
        native_min_value=0.0,
        native_max_value=2400.0,
        native_step=10.0,
        icon="mdi:transmission-tower-import",
    ),
    ZendureNumberDescription(
        key="price_threshold",
        translation_key="price_threshold",
        option_key=OPT_PRICE_THRESHOLD,
        default=DEFAULT_PRICE_THRESHOLD,
        native_min_value=0.0,
        native_max_value=2.0,
        native_step=0.01,
        icon="mdi:currency-eur",
    ),
    ZendureNumberDescription(
        key="very_expensive_threshold",
        translation_key="very_expensive_threshold",
        option_key=OPT_VERY_EXPENSIVE_THRESHOLD,
        default=DEFAULT_VERY_EXPENSIVE_THRESHOLD,
        native_min_value=0.0,
        native_max_value=2.0,
        native_step=0.01,
        icon="mdi:alert-decagram",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities([ZendureOptionNumber(hass, entry, desc) for desc in NUMBERS])


class ZendureOptionNumber(RestoreEntity, NumberEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, desc: ZendureNumberDescription):
        self.hass = hass
        self.entry = entry
        self.entity_description = desc
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

        self._attr_native_value = float(entry.options.get(desc.option_key, desc.default))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore only if option missing
        if self.entity_description.option_key not in (self.entry.options or {}):
            last = await self.async_get_last_state()
            if last and last.state not in ("unknown", "unavailable"):
                try:
                    self._attr_native_value = float(str(last.state).replace(",", "."))
                except Exception:
                    self._attr_native_value = float(self.entity_description.default)

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = float(value)

        new_opts = dict(self.entry.options or {})
        new_opts[self.entity_description.option_key] = float(value)

        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)

        # Kein harter Refresh-Zwang, aber hilft bei UI/Logik direkt:
        try:
            coordinator = self.hass.data[DOMAIN][self.entry.entry_id]["coordinator"]
            await coordinator.async_request_refresh()
        except Exception:
            pass

        self.async_write_ha_state()
