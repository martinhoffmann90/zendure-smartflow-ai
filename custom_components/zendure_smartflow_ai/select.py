from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .constants import DOMAIN


OPTIONS = ["Automatik", "Sommer", "Winter", "Manuell"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([ZendureBetriebsmodus(entry)])


class ZendureBetriebsmodus(SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:toggle-switch"
    _attr_options = OPTIONS

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_current_option = "Automatik"

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
