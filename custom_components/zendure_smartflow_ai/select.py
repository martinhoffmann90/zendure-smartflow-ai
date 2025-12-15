from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ZendureSmartFlowCoordinator
from .const import DOMAIN


MODES = ["Automatik", "Sommer", "Winter", "Manuell"]


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureBetriebsmodusSelect(coordinator, entry)])


class ZendureBetriebsmodusSelect(CoordinatorEntity, SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:cog-outline"
    _attr_options = MODES

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_mode"

    @property
    def current_option(self) -> str:
        state = self.coordinator._state(self.coordinator.entities.ac_mode)
        return state if state in MODES else "Automatik"

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": self.coordinator.entities.ac_mode,
                "option": option,
            },
            blocking=False,
        )
