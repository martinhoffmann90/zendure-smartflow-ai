from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureAiStatusSensor(coordinator, entry),
            ZendureRecommendationSensor(coordinator, entry),
            ZendureDebugSensor(coordinator, entry),
            ZendureOnlineSensor(coordinator, entry),
        ],
        True,
    )


class _BaseSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ):
        self.coordinator = coordinator
        self.entry = entry
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SmartFlow AI",
        }

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._key)

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get("details", {})

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class ZendureAiStatusSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "ai_status", "AI Status")


class ZendureRecommendationSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "recommendation", "Steuerungsempfehlung")


class ZendureDebugSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "debug", "AI Debug")


class ZendureOnlineSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "status", "Status")
