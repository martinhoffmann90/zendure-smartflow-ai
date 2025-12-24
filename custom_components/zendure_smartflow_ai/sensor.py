from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class _SensorSpec:
    key: str
    name: str


SENSORS: list[_SensorSpec] = [
    _SensorSpec("ai_status", "AI Status"),
    _SensorSpec("recommendation", "Steuerungsempfehlung"),
    _SensorSpec("debug", "AI Debug"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureSmartFlowAISensor(coordinator, entry, spec) for spec in SENSORS])


class ZendureSmartFlowAISensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, spec: _SensorSpec) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._spec = spec

        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_name = spec.name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="TK-Multimedia / Community",
            model="SmartFlow AI",
        )

    @property
    def native_value(self) -> Any:
        return (self.coordinator.data or {}).get(self._spec.key)
