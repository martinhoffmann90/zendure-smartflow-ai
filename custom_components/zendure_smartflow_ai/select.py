from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


MODES = [
    "Automatik",
    "Sommer",
    "Winter",
    "Manuell",
]


class ZendureBetriebsmodusSelect(
    CoordinatorEntity[ZendureSmartFlowCoordinator], SelectEntity
):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:cog-sync"

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_betriebsmodus"
        self._attr_options = MODES

        # 🔑 DAS WAR DER FEHLENDE TEIL
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Zendure",
            model="SmartFlow AI",
        )

    @property
    def current_option(self) -> str:
        state = self.coordinator._state(self.coordinator.entities.ac_mode)
        return state if state in MODES else "Automatik"

    async def async_select_option(self, option: str) -> None:
        # Modus wird DIREKT gesetzt (kein Flackern)
        await self.coordinator.hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": self.coordinator.entities.ac_mode,
                "option": option,
            },
            blocking=False,
        )

        # Coordinator neu triggern
        await self.coordinator.async_request_refresh()
