from homeassistant.components.select import SelectEntity
from .const import DOMAIN

MODES = ["automatic", "summer", "winter", "manual"]

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ZendureAIMode(entry.entry_id)])


class ZendureAIMode(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "AI Modus"
    _attr_translation_key = "ai_mode"
    _attr_options = MODES
    _attr_current_option = "automatic"

    def __init__(self, entry_id: str):
        self._attr_unique_id = f"{entry_id}_ai_mode"
