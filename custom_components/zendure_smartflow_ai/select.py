from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


OPTIONS = ["Automatik", "Sommer", "Winter", "Manuell"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    async_add_entities([ZendureBetriebsmodusSelect(entry)], update_before_add=True)


class ZendureBetriebsmodusSelect(SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:cog-sync"
    _attr_options = OPTIONS
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_betriebsmodus"
        self._current = "Automatik"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SmartFlow AI",
        }

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        self.async_write_ha_state()
