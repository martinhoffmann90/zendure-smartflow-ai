from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, MODES, DEVICE_MANUFACTURER, DEVICE_MODEL, DEVICE_NAME


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureModeSelect(coordinator, entry)])


class ZendureModeSelect(SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:cog-outline"
    _attr_options = MODES

    def __init__(self, coordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_current_option = MODES[0]

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
            "name": DEVICE_NAME,
        }

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._attr_current_option
