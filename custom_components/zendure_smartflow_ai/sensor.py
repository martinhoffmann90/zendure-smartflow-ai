from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    data_key: str


SENSORS: tuple[ZendureSensorEntityDescription, ...] = (
    ZendureSensorEntityDescription(
        key="status",
        translation_key="status",
        data_key="status",
        icon="mdi:information-outline",
    ),
    ZendureSensorEntityDescription(
        key="ai_status",
        translation_key="ai_status",
        data_key="ai_status",
        icon="mdi:robot",
    ),
    ZendureSensorEntityDescription(
        key="ai_debug",
        translation_key="ai_debug",
        data_key="ai_debug",
        icon="mdi:bug-outline",
    ),
    ZendureSensorEntityDescription(
        key="house_load",
        translation_key="house_load",
        data_key="house_load",
        icon="mdi:home-lightning-bolt",
        native_unit_of_measurement="W",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    add_entities(
        ZendureSmartFlowSensor(entry, coordinator, description)
        for description in SENSORS
    )


class ZendureSmartFlowSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureSensorEntityDescription) -> None:
        self.entity_description = description
        self.coordinator = coordinator

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.data_key)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
