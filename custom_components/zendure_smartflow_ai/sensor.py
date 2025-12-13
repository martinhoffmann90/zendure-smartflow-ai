from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True, kw_only=True)
class ZendureSmartFlowSensorEntityDescription(SensorEntityDescription):
    key: str


SENSORS: tuple[ZendureSmartFlowSensorEntityDescription, ...] = (
    ZendureSmartFlowSensorEntityDescription(
        key="ai_status",
        name="Zendure SmartFlow AI Status",
        icon="mdi:brain",
    ),
    ZendureSmartFlowSensorEntityDescription(
        key="recommendation",
        name="Zendure Akku Steuerungsempfehlung",
        icon="mdi:lightning-bolt",
    ),
    ZendureSmartFlowSensorEntityDescription(
        key="debug",
        name="Zendure SmartFlow AI Debug",
        icon="mdi:bug",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for desc in SENSORS:
        entities.append(ZendureSmartFlowSensor(coordinator, entry.entry_id, desc))

    async_add_entities(entities)


class ZendureSmartFlowSensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    """Ein generischer Sensor für ai_status / recommendation / debug."""

    entity_description: ZendureSmartFlowSensorEntityDescription

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry_id: str,
        description: ZendureSmartFlowSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        # Unique ID sauber stabil halten
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_has_entity_name = True

        # optional: device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Community",
            "model": "SF2400AC (SmartFlow AI)",
        }

    @property
    def native_value(self) -> Any:
        # Sicher: wenn Key fehlt -> None statt KeyError
        return (self.coordinator.data or {}).get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        WICHTIG: muss immer ein dict sein!
        Wir legen fürs Debug zusätzliche Felder ab, alle anderen bekommen ein kleines Set.
        """
        data = self.coordinator.data or {}

        # Für alle: Basiskontext
        base = {
            "ai_status": data.get("ai_status"),
            "recommendation": data.get("recommendation"),
            "last_update": data.get("last_update"),
        }

        # Debug-Sensor: mehr Details, aber sauber als dict
        if self.entity_description.key == "debug":
            debug_val = data.get("debug")
            # debug_val kann string sein -> als Feld ablegen, NICHT als dict selbst zurückgeben!
            base.update(
                {
                    "debug_text": debug_val,
                    "prices_len": data.get("prices_len"),
                    "current_price": data.get("current_price"),
                    "expensive_threshold": data.get("expensive_threshold"),
                    "cheap_threshold": data.get("cheap_threshold"),
                    "soc": data.get("soc"),
                    "soc_min": data.get("soc_min"),
                    "soc_max": data.get("soc_max"),
                }
            )

        return base
