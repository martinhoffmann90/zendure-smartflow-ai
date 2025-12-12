from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)


class ZendureSmartFlowCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.entry_id = entry.entry_id

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """
        Zentrale Datenstruktur für ALLE Sensoren.
        MUSS immer alle Keys enthalten!
        """

        return {
            # Hauptstatus (KI-Status)
            "ai_status": "initial",

            # Steuerungsempfehlung für Automationen
            "recommendation": "standby",

            # Debug / Text / Erklärung
            "debug": "Initialer Start – noch keine Berechnung erfolgt",

            # Optional: später erweiterbar
            "reason": "startup",
        }
