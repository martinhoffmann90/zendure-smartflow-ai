from __future__ import annotations

import json
from pathlib import Path
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

DOMAIN = "zendure_smartflow_ai"
_TRANSLATIONS = {}


def _load_translation(lang: str) -> dict:
    if lang in _TRANSLATIONS:
        return _TRANSLATIONS[lang]

    base = Path(__file__).parent / "translations"
    path = base / f"{lang}.json"
    if not path.exists():
        path = base / "en.json"

    data = json.loads(path.read_text(encoding="utf-8"))
    _TRANSLATIONS[lang] = data
    return data


def _t(hass, section: str, key: str) -> str:
    lang = (hass.config.language or "en").lower()
    data = _load_translation(lang)
    return (
        data.get("state", {})
        .get(section, {})
        .get(key, key)
    )


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureAIStatusSensor(coordinator),
            ZendureAIRecommendationSensor(coordinator),
            ZendureAIDebugSensor(coordinator),
        ]
    )


class ZendureAIStatusSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_ai_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("ai_status")

    @property
    def extra_state_attributes(self):
        key = self.coordinator.data.get("ai_status", "data_missing")
        return {
            "status_text": _t(self.hass, "ai_status", key)
        }


class ZendureAIRecommendationSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Zendure Akku Steuerungsempfehlung"
    _attr_icon = "mdi:battery-heart"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_recommendation"

    @property
    def native_value(self):
        return self.coordinator.data.get("recommendation")

    @property
    def extra_state_attributes(self):
        key = self.coordinator.data.get("recommendation", "standby")
        return {
            "recommendation_text": _t(self.hass, "recommendation", key)
        }


class ZendureAIDebugSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_debug"

    @property
    def native_value(self):
        return "ok"

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("debug", {})
