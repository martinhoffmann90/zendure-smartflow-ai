from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 10
FREEZE_SECONDS = 120


@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_export: str

    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",

    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",

    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        self.entities = DEFAULT_ENTITY_IDS

        self._freeze_until: datetime | None = None
        self._last_ai_status: str | None = None
        self._last_recommendation: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def _state(self, entity: str) -> Any:
        s = self.hass.states.get(entity)
        return None if s is None else s.state

    def _attr(self, entity: str, attr: str) -> Any:
        s = self.hass.states.get(entity)
        return None if s is None else s.attributes.get(attr)

    async def _set_mode(self, mode: str):
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input(self, w: float):
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(w, 0)},
            blocking=False,
        )

    async def _set_output(self, w: float):
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(w, 0)},
            blocking=False,
        )

    def _prices(self) -> list[float]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []
        return [_f(p.get("price_per_kwh")) for p in export]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)
            expensive_fixed = _f(self._state(self.entities.expensive_threshold), 0.35)

            max_charge = _f(self._state(self.entities.max_charge), 2000)
            max_discharge = _f(self._state(self.entities.max_discharge), 700)

            prices = self._prices()
            if not prices:
                return {
                    "ai_status": "price_invalid",
                    "recommendation": "standby",
                    "debug": "NO_PRICE_DATA",
                    "details": {},
                }

            price_now = prices[0]

            minp = min(prices)
            maxp = max(prices)
            avgp = sum(prices) / len(prices)
            span = maxp - minp
            expensive = max(expensive_fixed, avgp + span * 0.25)

            surplus = max(pv - load, 0)
            soc_notfall = max(soc_min - 4, 5)

            ai_status = "standby"
            recommendation = "standby"
            mode = "input"
            in_w = 0
            out_w = 0

            if price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                mode = "output"
                out_w = min(max_discharge, max(load - pv, 0))

            elif soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                in_w = min(max_charge, 300)

            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                in_w = min(max_charge, surplus)

            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            await self._set_mode(mode)
            await self._set_input(in_w)
            await self._set_output(out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": price_now,
                    "expensive_threshold": expensive,
                    "soc": soc,
                    "set_mode": mode,
                    "set_input_w": in_w,
                    "set_output_w": out_w,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
