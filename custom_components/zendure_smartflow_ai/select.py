from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.translation import async_get_translations

from .const import (
    DOMAIN,
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    translations = await async_get_translations(
        hass,
        hass.config.language,
        "entity",
    )

    def _t(key: str, fallback: str) -> str:
        return translations.get(key, fallback)

    async_add_entities(
        [
            ZendureAIModeSelect(hass, entry, _t),
            ZendureManualActionSelect(hass, entry, _t),
        ]
    )


class ZendureAIModeSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, t) -> None:
        self.hass = hass
        self.entry = entry
        self._t = t

        self._attr_unique_id = f"{entry.entry_id}_ai_mode"
        self._attr_translation_key = "ai_mode"

        self._values = {
            AI_MODE_AUTOMATIC: self._t(
                "entity.select.zendure_smartflow_ai.ai_mode.state.automatic", "Automatic"
            ),
            AI_MODE_SUMMER: self._t(
                "entity.select.zendure_smartflow_ai.ai_mode.state.summer", "Summer"
            ),
            AI_MODE_WINTER: self._t(
                "entity.select.zendure_smartflow_ai.ai_mode.state.winter", "Winter"
            ),
            AI_MODE_MANUAL: self._t(
                "entity.select.zendure_smartflow_ai.ai_mode.state.manual", "Manual"
            ),
        }

        self._reverse = {v: k for k, v in self._values.items()}

    @property
    def options(self) -> list[str]:
        return list(self._values.values())

    @property
    def current_option(self) -> str | None:
        mode = self.entry.runtime_data["coordinator"].runtime_mode.get("ai_mode")
        return self._values.get(mode)

    async def async_select_option(self, option: str) -> None:
        key = self._reverse.get(option)
        if key is None:
            return
        self.entry.runtime_data["coordinator"].set_ai_mode(key)
        self.async_write_ha_state()


class ZendureManualActionSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, t) -> None:
        self.hass = hass
        self.entry = entry
        self._t = t

        self._attr_unique_id = f"{entry.entry_id}_manual_action"
        self._attr_translation_key = "manual_action"

        self._values = {
            MANUAL_STANDBY: self._t(
                "entity.select.zendure_smartflow_ai.manual_action.state.standby", "Standby"
            ),
            MANUAL_CHARGE: self._t(
                "entity.select.zendure_smartflow_ai.manual_action.state.charge", "Charge"
            ),
            MANUAL_DISCHARGE: self._t(
                "entity.select.zendure_smartflow_ai.manual_action.state.discharge", "Discharge"
            ),
        }

        self._reverse = {v: k for k, v in self._values.items()}

    @property
    def options(self) -> list[str]:
        return list(self._values.values())

    @property
    def current_option(self) -> str | None:
        action = self.entry.runtime_data["coordinator"].runtime_mode.get("manual_action")
        return self._values.get(action)

    async def async_select_option(self, option: str) -> None:
        key = self._reverse.get(option)
        if key is None:
            return
        self.entry.runtime_data["coordinator"].set_manual_action(key)
        self.async_write_ha_state()
