from __future__ import annotations
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import Entity
from .const import *

class ZendureBaseNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_native_step = 1.0


class ZendureSocMin(ZendureBaseNumber):
    _attr_name = "SoC Minimum"
    _attr_native_min_value = 5
    _attr_native_max_value = 50
    _attr_native_value = DEFAULT_SOC_MIN


class ZendureSocMax(ZendureBaseNumber):
    _attr_name = "SoC Maximum"
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_value = DEFAULT_SOC_MAX
