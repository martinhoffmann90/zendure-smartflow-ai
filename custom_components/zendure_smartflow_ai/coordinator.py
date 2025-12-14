from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .constants import (
    MODE_AUTOMATIC,
    MODE_MANUAL,
    MODE_SUMMER,
    MODE_WINTER,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    # Messwerte
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str

    # Parameter / Helfer
    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    # Zendure Steuerung
    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    soc_min="input_number.zendure_soc_reserve_min",
    soc_max="input_number.zendure_soc_ziel_max",
    expensive_threshold="input_number.zendure_schwelle_teuer",
    max_charge="input_number.zendure_max_ladeleistung",
    max_discharge="input_number.zendure_max_entladeleistung",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None:
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Zentrale KI + Steuerlogik"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        # Betriebsmodus (wird über select gesetzt)
        self.mode: str = MODE_AUTOMATIC

        data = entry.data or {}
        self.entities = EntityIds(
            soc=data.get("soc_entity", DEFAULT_ENTITY_IDS.soc),
            pv=data.get("pv_entity", DEFAULT_ENTITY_IDS.pv),
            load=data.get("load_entity", DEFAULT_ENTITY_IDS.load),
            price_now=data.get("price_now_entity", DEFAULT_ENTITY_IDS.price_now),
            price_export=data.get("price_export_entity", DEFAULT_ENTITY_IDS.price_export),
            soc_min=data.get("soc_min_entity", DEFAULT_ENTITY_IDS.soc_min),
            soc_max=data.get("soc_max_entity", DEFAULT_ENTITY_IDS.soc_max),
            expensive_threshold=data.get(
                "expensive_threshold_entity",
                DEFAULT_ENTITY_IDS.expensive_threshold,
            ),
            max_charge=data.get("max_charge_entity", DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=data.get(
                "max_discharge_entity",
                DEFAULT_ENTITY_IDS.max_discharge,
            ),
            ac_mode=data.get("ac_mode_entity", DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=data.get(
                "input_limit_entity",
                DEFAULT_ENTITY_IDS.input_limit,
            ),
            output_limit=data.get(
                "output_limit_entity",
                DEFAULT_ENTITY_IDS.output_limit,
            ),
        )

        # Schutz gegen Flattern
        self._last_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None
        self._last_recommendation: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ------------------ Helpers ------------------

    def _get_state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _get_attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        if st is None:
            return None
        return st.attributes.get(attr)

    async def _set_mode(self, mode: str) -> None:
        if mode != self._last_mode:
            await self.hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": self.entities.ac_mode, "option": mode},
                blocking=False,
            )
            self._last_mode = mode

    async def _set_input_limit(self, watts: float) -> None:
        if self._last_in is None or abs(self._last_in - watts) > 25:
            await self.hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": self.entities.input_limit,
                    "value": float(round(watts, 0)),
                },
                blocking=False,
            )
            self._last_in = watts

    async def _set_output_limit(self, watts: float) -> None:
        if self._last_out is None or abs(self._last_out - watts) > 25:
            await self.hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": self.entities.output_limit,
                    "value": float(round(watts, 0)),
                },
                blocking=False,
            )
            self._last_out = watts

    def _extract_prices(self) -> list[float]:
        export = self._get_attr(self.entities.price_export, "data")
        if not export:
            return []
        prices: list[float] = []
        for item in export:
            prices.append(_f(item.get("price_per_kwh"), 0.0))
        return prices

    def _idx_now(self) -> int:
        now = dt_util.now()
        return int((now.hour * 60 + now.minute) // 15)

    # ------------------ Core Update ------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc = _f(self._get_state(self.entities.soc), 0.0)
            pv = _f(self._get_state(self.entities.pv), 0.0)
            load = _f(self._get_state(self.entities.load), 0.0)
            price_now = _f(self._get_state(self.entities.price_now), 0.0)

            soc_min = _f(self._get_state(self.entities.soc_min), 12.0)
            soc_max = _f(self._get_state(self.entities.soc_max), 95.0)
            soc_notfall = max(soc_min - 4.0, 5.0)

            expensive_fixed = _f(
                self._get_state(self.entities.expensive_threshold),
                0.35,
            )
            max_charge = _f(self._get_state(self.entities.max_charge), 2000.0)
            max_discharge = _f(self._get_state(self.entities.max_discharge), 700.0)

            prices = self._extract_prices()
            idx = self._idx_now()
            future = prices[idx:] if idx < len(prices) else []

            if future:
                minp = min(future)
                maxp = max(future)
                avg = sum(future) / len(future)
                expensive = max(expensive_fixed, avg + (maxp - minp) * 0.25)
            else:
                minp = maxp = avg = expensive = price_now

            surplus = max(pv - load, 0.0)

            ai_status = "standby"
            recommendation = "standby"
            control_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # ---------- MANUELL ----------
            if self.mode == MODE_MANUAL:
                ai_status = "manuell"
                recommendation = "standby"

            # ---------- NOTFALL ----------
            elif soc <= soc_notfall and soc < soc_max:
                ai_status = "notladung"
                recommendation = "billig_laden"
                in_w = min(max_charge, 300)

            # ---------- TEUER ----------
            elif price_now >= expensive:
                if soc > soc_min and self.mode != MODE_SUMMER:
                    ai_status = "teuer_entladen"
                    recommendation = "entladen"
                    control_mode = "output"
                    out_w = min(max_discharge, max(load - pv, 0))
                else:
                    ai_status = "teuer_schutz"

            # ---------- GÜNSTIG ----------
            elif future and future[0] == min(future) and soc < soc_max and self.mode in (
                MODE_AUTOMATIC,
                MODE_WINTER,
            ):
                ai_status = "guenstig_laden"
                recommendation = "ki_laden"
                in_w = max_charge

            # ---------- PV ----------
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                in_w = min(max_charge, surplus)

            # ---------- Steuerung ----------
            if recommendation != self._last_recommendation:
                if control_mode == "output":
                    await self._set_mode("output")
                else:
                    await self._set_mode("input")

                await self._set_input_limit(in_w)
                await self._set_output_limit(out_w)

                self._last_recommendation = recommendation

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": price_now,
                    "min_price_future": minp,
                    "max_price_future": maxp,
                    "avg_price_future": avg,
                    "expensive_threshold": expensive,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "mode": self.mode,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
