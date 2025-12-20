from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Zendure SmartFlow AI numbers."""
    async_add_entities(
        [
            ZendureSocMinNumber(entry),
            ZendureSocMaxNumber(entry),
        ]
    )


class ZendureBaseNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique: str) -> None:
        self._attr_unique_id = f"{entry.entry_id}_{unique}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SolarFlow AI",
        }
        self._value = None

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        self.async_write_ha_state()


class ZendureSocMinNumber(ZendureBaseNumber):
    _attr_name = "SoC Minimum"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "soc_min")
        self._value = DEFAULT_SOC_MIN


class ZendureSocMaxNumber(ZendureBaseNumber):
    _attr_name = "SoC Maximum"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "soc_max")
        self._value = DEFAULT_SOC_MAX
