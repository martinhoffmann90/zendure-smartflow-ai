from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import *

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    async_add_entities(
        [
            ZendureAINumber("SoC Minimum (%)", DEFAULT_SOC_MIN),
            ZendureAINumber("SoC Maximum (%)", DEFAULT_SOC_MAX),
        ]
    )


class ZendureAINumber(NumberEntity):
    def __init__(self, name: str, default: float):
        self._attr_name = f"Zendure SmartFlow AI {name}"
        self._attr_native_value = default
        self._attr_min_value = 0
        self._attr_max_value = 100
        self._attr_step = 1

    @property
    def native_value(self):
        return self._attr_native_value

    async def async_set_native_value(self, value: float):
        self._attr_native_value = value
