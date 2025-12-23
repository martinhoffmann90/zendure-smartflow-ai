from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODES, MODE_AUTOMATIC


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # store für AI-Mode Auswahl
    store = hass.data[DOMAIN][entry.entry_id].setdefault("settings", {})
    store.setdefault("ai_mode", MODE_AUTOMATIC)

    async_add_entities([ZendureAIModeSelect(coordinator, entry, store)])


class ZendureBaseEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="PalmManiac / Community",
            model="SmartFlow AI",
            entry_type=DeviceEntryType.SERVICE,
        )


class ZendureAIModeSelect(ZendureBaseEntity, SelectEntity):
    """AI Betriebsmodus der Integration (nicht zu verwechseln mit Zendure AC Mode input/output)."""

    _attr_entity_category = EntityCategory.CONFIG

    entity_description = SelectEntityDescription(
        key="ai_mode",
        translation_key="ai_mode",
        name="Betriebsmodus",
        icon="mdi:robot",
    )

    _attr_options = list(MODES)

    def __init__(self, coordinator, entry: ConfigEntry, store: dict[str, Any]) -> None:
        super().__init__(coordinator, entry)
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_ai_mode"

    @property
    def current_option(self) -> str:
        return str(self._store.get("ai_mode", MODE_AUTOMATIC))

    async def async_select_option(self, option: str) -> None:
        if option not in MODES:
            return
        self._store["ai_mode"] = option
        self.async_write_ha_state()
