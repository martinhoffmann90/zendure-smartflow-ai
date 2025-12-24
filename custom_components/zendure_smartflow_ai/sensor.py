from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class ZSensorDescription(SensorEntityDescription):
    pass


SENSORS: tuple[ZSensorDescription, ...] = (
    ZSensorDescription(
        key="status",
        name="Status",
        icon="mdi:robot",
        translation_key="status",
    ),
    ZSensorDescription(
        key="recommendation",
        name="Steuerungsempfehlung",
        icon="mdi:lightbulb-auto",
        translation_key="recommendation",
    ),
    ZSensorDescription(
        key="debug",
        name="Debug",
        icon="mdi:bug",
        translation_key="debug",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ZendureSmartFlowSensor(coordinator, entry.entry_id, d) for d in SENSORS])


class ZendureSmartFlowSensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry_id: str, desc: ZSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        self._attr_unique_id = f"{entry_id}_{desc.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

    @property
    def native_value(self) -> Any:
        return (self.coordinator.data or {}).get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "debug":
            # Debug bekommt Details als Attribute
            return (self.coordinator.data or {}).get("details")
        return None
