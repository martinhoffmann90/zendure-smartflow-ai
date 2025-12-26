from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


AI_MODES = ["automatic", "summer", "winter", "manual"]
MANUAL_ACTIONS = ["standby", "charge", "discharge"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
):
    async_add_entities(
        [
            ZendureAIModeSelect(entry),
            ZendureManualActionSelect(entry),
        ]
    )


class ZendureAIModeSelect(SelectEntity):
    _attr_translation_key = "ai_mode"
    _attr_options = AI_MODES
    _attr_icon = "mdi:brain"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_ai_mode"
        self._attr_current_option = "automatic"
        self._attr_has_entity_name = True

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class ZendureManualActionSelect(SelectEntity):
    _attr_translation_key = "manual_action"
    _attr_options = MANUAL_ACTIONS
    _attr_icon = "mdi:hand-back-right"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_manual_action"
        self._attr_current_option = "standby"
        self._attr_has_entity_name = True

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
