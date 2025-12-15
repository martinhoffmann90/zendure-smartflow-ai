from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    async_add_entities(
        [
            ZendureSocMinNumber(entry),
            ZendureSocMaxNumber(entry),
        ]
    )


class _BaseZendureNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._value = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Zendure",
            model="SmartFlow AI",
        )

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = round(float(value), 1)
        self.async_write_ha_state()


class ZendureSocMinNumber(_BaseZendureNumber):
    _attr_name = "Zendure SoC Minimum"
    _attr_icon = "mdi:battery-low"
    _attr_native_min_value = 5
    _attr_native_max_value = 40
    _attr_native_step = 1
    _attr_unit_of_measurement = "%"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_min"
        self._value = 12


class ZendureSocMaxNumber(_BaseZendureNumber):
    _attr_name = "Zendure SoC Maximum"
    _attr_icon = "mdi:battery-high"
    _attr_native_min_value = 60
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_unit_of_measurement = "%"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_max"
        self._value = 95
