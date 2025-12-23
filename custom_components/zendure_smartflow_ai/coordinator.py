from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import *

_LOGGER = logging.getLogger(__name__)


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.data_cfg = entry.data

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -----------------------
    def _state(self, entity_id: str):
        s = self.hass.states.get(entity_id)
        return None if s is None else s.state

    def _attr(self, entity_id: str, attr: str):
        s = self.hass.states.get(entity_id)
        return None if s is None else s.attributes.get(attr)

    # -----------------------
    def _price_now(self) -> float | None:
        export = self._attr(self.data_cfg[CONF_PRICE_EXPORT_ENTITY], "data")
        if not isinstance(export, list):
            return None
        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15
        if idx >= len(export):
            return None
        return _to_float(export[idx].get("price_per_kwh"))

    # -----------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc = _to_float(self._state(self.data_cfg[CONF_SOC_ENTITY]), 0.0)
            pv = _to_float(self._state(self.data_cfg[CONF_PV_ENTITY]), 0.0)
            load = _to_float(self._state(self.data_cfg[CONF_LOAD_ENTITY]), 0.0)

            price = self._price_now()
            surplus = max(pv - load, 0)
            deficit = max(load - pv, 0)

            ai_status = "standby"
            recommendation = "standby"

            if price is not None:
                if price >= DEFAULT_EXPENSIVE_THRESHOLD and soc > DEFAULT_SOC_MIN:
                    ai_status = "expensive"
                    recommendation = "discharge"
                elif surplus > 100 and soc < DEFAULT_SOC_MAX:
                    ai_status = "pv_surplus"
                    recommendation = "charge"

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "price_now": price,
                    "surplus": surplus,
                    "deficit": deficit,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
