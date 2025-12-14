from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


MODES = [
    "Automatik",
    "Sommer",
    "Winter",
    "Manuell",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureBetriebsmodusSelect(coordinator, entry),
        ]
    )


class ZendureBetriebsmodusSelect(SelectEntity):
    """Betriebsmodus der Zendure SmartFlow AI."""

    _attr_name = "Betriebsmodus"
    _attr_icon = "mdi:cog-sync"
    _attr_options = MODES
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._mode = "Automatik"

        self._attr_unique_id = f"{entry.entry_id}_betriebsmode"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Zendure",
            model="SmartFlow AI",
            configuration_url="https://github.com/PalmManiac/zendure-smartflow-ai",
        )

    @property
    def current_option(self) -> str:
        return self._mode

    async def async_select_option(self, option: str) -> None:
        if option not in MODES:
            return

        self._mode = option

        # Modus im Coordinator hinterlegen
        self.coordinator.set_user_mode(option)

        self.async_write_ha_state()
