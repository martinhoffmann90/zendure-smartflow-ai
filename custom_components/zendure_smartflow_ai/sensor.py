from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureAISensor(coordinator, "ai_status", "AI Status"),
            ZendureAISensor(coordinator, "recommendation", "Steuerungsempfehlung"),
            ZendureAISensor(coordinator, "house_load", "Hausverbrauch"),
        ]
    )


class ZendureAISensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Zendure SmartFlow AI {name}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)
