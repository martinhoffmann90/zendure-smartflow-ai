from homeassistant.components.number import NumberEntity
from .const import *

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        SoCMin(),
        SoCMax(),
    ])

class SoCMin(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "SoC Minimum"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_value = DEFAULT_SOC_MIN

class SoCMax(NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "SoC Maximum"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_value = DEFAULT_SOC_MAX
