from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    OPT_AI_MODE,
    OPT_MANUAL_ACTION,
    AI_MODES,
    MANUAL_ACTIONS,
    AI_MODE_AUTOMATIC,
    MANUAL_STANDBY,
)


@dataclass(frozen=True, kw_only=True)
class ZendureSelectDescription(SelectEntityDescription):
    option_key: str
    options_list: list[str]
    default: str


SELECTS: tuple[ZendureSelectDescription, ...] = (
    ZendureSelectDescription(
        key="ai_mode",
        translation_key="ai_mode",
        option_key=OPT_AI_MODE,
        options_list=AI_MODES,
        default=AI_MODE_AUTOMATIC,
        icon="mdi:robot",
    ),
    ZendureSelectDescription(
        key="manual_action",
        translation_key="manual_action",
        option_key=OPT_MANUAL_ACTION,
        options_list=MANUAL_ACTIONS,
        default=MANUAL_STANDBY,
        icon="mdi:gesture-tap",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities([ZendureOptionSelect(hass, entry, desc) for desc in SELECTS])


class ZendureOptionSelect(SelectEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, desc: ZendureSelectDescription):
        self.hass = hass
        self.entry = entry
        self.entity_description = desc

        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

        self._attr_options = desc.options_list
        self._attr_current_option = (entry.options.get(desc.option_key, desc.default)) or desc.default

    async def async_select_option(self, option: str) -> None:
        if option not in self.entity_description.options_list:
            return

        self._attr_current_option = option

        new_opts = dict(self.entry.options or {})
        new_opts[self.entity_description.option_key] = option
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)

        try:
            coordinator = self.hass.data[DOMAIN][self.entry.entry_id]["coordinator"]
            await coordinator.async_request_refresh()
        except Exception:
            pass

        self.async_write_ha_state()
