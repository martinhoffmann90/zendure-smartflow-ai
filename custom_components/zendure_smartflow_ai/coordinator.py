from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

FREEZE_SECONDS = 120


@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str
    soc_min: str
    soc_max: str
    expensive: str
    max_charge: str
    max_discharge: str
    mode: str
    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",
    mode="select.zendure_betriebsmodus",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


def _f(val: str | None, default: float = 0.0) -> float:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entities = DEFAULT_ENTITY_IDS

        self._freeze_until = None
        self._last_rec = None
        self._last_status = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    def _state(self, e: str) -> str | None:
        s = self.hass.states.get(e)
        return None if s is None else s.state

    def _attr(self, e: str, a: str) -> Any:
        s = self.hass.states.get(e)
        return None if s is None else s.attributes.get(a)

    def _future_prices(self) -> list[float]:
        data = self._attr(self.entities.price_export, "data")
        if not data:
            return []
        prices = [_f(p.get("price_per_kwh")) for p in data]
        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15
        return prices[idx:]

    async def _set(self, domain, service, data):
        await self.hass.services.async_call(domain, service, data, blocking=False)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)
            expensive = _f(self._state(self.entities.expensive), 0.35)
            max_charge = _f(self._state(self.entities.max_charge), 2000)
            max_dis = _f(self._state(self.entities.max_discharge), 700)

            mode = (self._state(self.entities.mode) or "Automatik").lower()
            prices = self._future_prices()

            surplus = max(pv - load, 0)
            ai_status = "standby"
            rec = "standby"
            ac_mode = "input"
            in_w = out_w = 0

            # 🔥 Notfall
            if soc <= max(soc_min - 4, 5):
                ai_status = "notladung"
                rec = "billig_laden"
                in_w = min(max_charge, 300)

            elif mode == "manuell":
                ai_status = "manuell"

            elif price >= expensive and soc > soc_min:
                ai_status = "teuer_entladen"
                rec = "entladen"
                ac_mode = "output"
                out_w = min(max_dis, max(load - pv, 0))

            elif prices and prices[0] == min(prices) and soc < soc_max:
                ai_status = "guenstig_laden"
                rec = "ki_laden"
                in_w = max_charge

            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                rec = "laden"
                in_w = min(max_charge, surplus)

            # Freeze
            if self._freeze_until and now < self._freeze_until:
                rec = self._last_rec
                ai_status = self._last_status
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_rec = rec
                self._last_status = ai_status

            # Anwenden
            await self._set("select", "select_option", {
                "entity_id": self.entities.ac_mode,
                "option": ac_mode,
            })
            await self._set("number", "set_value", {
                "entity_id": self.entities.input_limit,
                "value": round(in_w),
            })
            await self._set("number", "set_value", {
                "entity_id": self.entities.output_limit,
                "value": round(out_w),
            })

            return {
                "ai_status": ai_status,
                "recommendation": rec,
                "debug": "OK",
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
