from homeassistant.components.select import SelectEntity
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
            ZendureAIModeSelect(),
            ZendureAIManualActionSelect(),
        ]
    )


class ZendureAIModeSelect(SelectEntity):
    _attr_name = "Zendure SmartFlow AI Modus"
    _attr_options = ["Automatik", "Sommer", "Winter", "Manuell"]
    _attr_current_option = "Automatik"

    async def async_select_option(self, option: str):
        self._attr_current_option = option


class ZendureAIManualActionSelect(SelectEntity):
    _attr_name = "Zendure SmartFlow AI Manuelle Aktion"
    _attr_options = ["Standby", "Laden", "Entladen"]
    _attr_current_option = "Standby"

    async def async_select_option(self, option: str):
        self._attr_current_option = option
