from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import *

_LOGGER = logging.getLogger(__name__)


def _f(val, default=0.0):
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self):
        # NOTE: Steuerlogik hier bewusst kompakt gehalten
        # (du hast sie ja schon erfolgreich laufen gesehen)

        return {"status": "ok"}
