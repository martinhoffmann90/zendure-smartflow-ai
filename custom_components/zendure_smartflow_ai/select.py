from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


MODES = [
    "automatic",
    "summer",
    "winter",
    "manual",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    async_add_entities([ZendureModeSelect(hass, entry)])


class ZendureModeSelect(SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:cog-sync"
    _attr_options = MODES

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_current_option = "automatic"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Zendure",
            model="SmartFlow AI",
        )

    async def async_select_option(self, option: str) -> None:
        # Nur lokalen State setzen – KEINE Automatik hier!
        self._attr_current_option = option
        self.async_write_ha_state()
