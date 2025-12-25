from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


# =========================
# AI MODE SELECT
# =========================

MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

AI_MODES = [
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
]


class ZendureAIModeSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "ai_mode"
    _attr_options = AI_MODES
    _attr_current_option = MODE_AUTOMATIC

    def __init__(self, entry_id: str):
        self._attr_unique_id = f"{entry_id}_ai_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Zendure SmartFlow AI",
        }

    def select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


# =========================
# AI RECOMMENDATION SELECT
# =========================

RECOMMEND_STANDBY = "standby"
RECOMMEND_CHARGE = "charge"
RECOMMEND_DISCHARGE = "discharge"

RECOMMENDATIONS = [
    RECOMMEND_STANDBY,
    RECOMMEND_CHARGE,
    RECOMMEND_DISCHARGE,
]


class ZendureAIRecommendationSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "ai_recommendation"
    _attr_options = RECOMMENDATIONS
    _attr_current_option = RECOMMEND_STANDBY

    def __init__(self, entry_id: str):
        self._attr_unique_id = f"{entry_id}_ai_recommendation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Zendure SmartFlow AI",
        }

    def select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


# =========================
# SETUP
# =========================

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            ZendureAIModeSelect(entry.entry_id),
            ZendureAIRecommendationSelect(entry.entry_id),
        ]
    )
