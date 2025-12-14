from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .constants import DOMAIN, MODES, DEFAULT_MODE
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureSmartFlowModeSelect(coordinator, entry)])


class ZendureSmartFlowModeSelect(SelectEntity):
    _attr_icon = "mdi:toggle-switch"
    _attr_name = "Zendure Betriebsmodus"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_options = list(MODES.keys())

    @property
    def current_option(self) -> str:
        return self.coordinator.mode or DEFAULT_MODE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"label": MODES.get(self.current_option, self.current_option)}

    async def async_select_option(self, option: str) -> None:
        # Setzt Mode im Coordinator + persistiert in entry.options (GUI-stabil, kein "Zucken")
        await self.coordinator.async_set_mode(option)
