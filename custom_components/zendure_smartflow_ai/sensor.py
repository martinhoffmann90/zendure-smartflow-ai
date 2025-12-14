from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity

from .constants import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class _SensorSpec:
    key: str
    name: str
    icon: str


SENSORS = [
    _SensorSpec("ai_status", "Zendure SmartFlow AI Status", "mdi:brain"),
    _SensorSpec("recommendation", "Zendure Akku Steuerungsempfehlung", "mdi:auto-fix"),
    _SensorSpec("debug", "Zendure SmartFlow AI Debug", "mdi:bug-outline"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([_ZendureSmartFlowSensor(coordinator, entry, spec) for spec in SENSORS])


class _ZendureSmartFlowSensor(SensorEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, spec: _SensorSpec) -> None:
        self.coordinator = coordinator
        self.entry = entry
        self.spec = spec

        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        val = data.get(self.spec.key, "")
        if val is None:
            return ""
        # Debug-State klein halten
        if self.spec.key == "debug":
            return str(val)[:255]
        return str(val)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        details = data.get("details", {}) or {}
        return {
            "details": details,
            "ai_status": data.get("ai_status"),
            "recommendation": data.get("recommendation"),
            "price_now": data.get("price_now"),
            "expensive_threshold": data.get("expensive_threshold"),
        }

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
