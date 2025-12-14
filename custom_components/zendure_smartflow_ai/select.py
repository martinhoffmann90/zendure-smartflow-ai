from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .constants import (
    DOMAIN,
    MODE_AUTOMATIC,
    MODE_MANUAL,
    MODE_SUMMER,
    MODE_WINTER,
    MODES,
    OPT_MODE,
)
from .coordinator import ZendureSmartFlowCoordinator


MODE_LABELS = {
    MODE_AUTOMATIC: "Automatik",
    MODE_SUMMER: "Sommer",
    MODE_WINTER: "Winter",
    MODE_MANUAL: "Manuell",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureModeSelect(coordinator, entry)], update_before_add=True)


class ZendureModeSelect(CoordinatorEntity[ZendureSmartFlowCoordinator], SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:calendar-sync"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_options = [MODE_LABELS[m] for m in MODES]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="PalmManiac",
            model="SF2400AC Controller",
        )

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.get_option_str(OPT_MODE, MODE_AUTOMATIC)
        return MODE_LABELS.get(mode, MODE_LABELS[MODE_AUTOMATIC])

    async def async_select_option(self, option: str) -> None:
        # Label -> internal
        reverse = {v: k for k, v in MODE_LABELS.items()}
        internal = reverse.get(option, MODE_AUTOMATIC)
        await self.coordinator.set_option(OPT_MODE, internal)
