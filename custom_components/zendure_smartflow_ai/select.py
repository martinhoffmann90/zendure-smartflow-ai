from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    AI_MODES,
    AI_MODE_WINTER,
    MANUAL_ACTIONS,
    MANUAL_ACTION_STANDBY,
)
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class _SelSpec:
    key: str
    name: str
    options: list[str]
    default: str


SELECTS: list[_SelSpec] = [
    _SelSpec(
        key="ai_mode",
        name="AI Moduswahl",
        options=AI_MODES,
        default=AI_MODE_WINTER,
    ),
    _SelSpec(
        key="manual_action",
        name="Manuelle Aktion",
        options=MANUAL_ACTIONS,
        default=MANUAL_ACTION_STANDBY,
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureSmartFlowAISelect(coordinator, entry, spec) for spec in SELECTS])


class ZendureSmartFlowAISelect(CoordinatorEntity[ZendureSmartFlowCoordinator], SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, spec: _SelSpec) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._spec = spec

        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_name = spec.name
        self._attr_options = list(spec.options)

        # defaults
        if spec.key == "ai_mode":
            self.coordinator.ai_mode = spec.default
        elif spec.key == "manual_action":
            self.coordinator.manual_action = spec.default

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="TK-Multimedia / Community",
            model="SmartFlow AI",
        )

    @property
    def current_option(self) -> str | None:
        if self._spec.key == "ai_mode":
            return self.coordinator.ai_mode
        if self._spec.key == "manual_action":
            return self.coordinator.manual_action
        return None

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return

        if self._spec.key == "ai_mode":
            self.coordinator.ai_mode = option
        elif self._spec.key == "manual_action":
            self.coordinator.manual_action = option

        self.async_write_ha_state()
