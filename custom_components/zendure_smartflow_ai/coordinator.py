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

# =========================
# Konstante Einstellungen
# =========================

FREEZE_SECONDS = 120  # Recommendation-Freeze (2 Minuten)

MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

# =========================
# Entity-Definition
# =========================

@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str

    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    mode: str  # Betriebsmodus (Select)
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
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",

    mode="select.zendure_betriebsmodus",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)

# =========================
# Hilfsfunktionen
# =========================

def _f(state: str | None, default: float = 0.0) -> float:
    try:
        return float(str(state).replace(",", "."))
    except Exception:
        return default


# =========================
# Coordinator
# =========================

class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        self.entities = DEFAULT_ENTITY_IDS

        # Recommendation-Freeze
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None
        self._freeze_until = None

        # Hardware-State (gegen Flattern)
        self._last_hw_mode: str | None = None
        self._last_in_w: float | None = None
        self._last_out_w: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ============
    # State Access
    # ============

    def _state(self, entity: str) -> str | None:
        st = self.hass.states.get(entity)
        return None if st is None else st.state

    def _attr(self, entity: str, attr: str) -> Any:
        st = self.hass.states.get(entity)
        return None if st is None else st.attributes.get(attr)

    # ============
    # Preise
    # ============

    def _future_prices(self) -> list[float]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []

        prices = [_f(e.get("price_per_kwh"), 0.0) for e in export]

        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15
        return prices[idx:] if idx < len(prices) else []

    # ===================
    # Hardware-Steuerung
    # ===================

    async def _apply_hardware(self, mode: str, in_w: float, out_w: float) -> None:
        def changed(a: float | None, b: float, tol: float = 25) -> bool:
            return a is None or abs(a - b) > tol

        if mode != self._last_hw_mode:
            await self.hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": self.entities.ac_mode, "option": mode},
                blocking=False,
            )
            self._last_hw_mode = mode

        if changed(self._last_in_w, in_w):
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self.entities.input_limit, "value": round(in_w, 0)},
                blocking=False,
            )
            self._last_in_w = in_w

        if changed(self._last_out_w, out_w):
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self.entities.output_limit, "value": round(out_w, 0)},
                blocking=False,
            )
            self._last_out_w = out_w

    # ===================
    # Hauptlogik
    # ===================

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # --- Basiswerte ---
            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)

            expensive_fixed = _f(self._state(self.entities.expensive_threshold), 0.35)
            max_charge = _f(self._state(self.entities.max_charge), 2000)
            max_discharge = _f(self._state(self.entities.max_discharge), 700)

            mode = self._state(self.entities.mode) or MODE_AUTOMATIC

            prices = self._future_prices()
            minp = min(prices) if prices else price_now
            maxp = max(prices) if prices else price_now
            avgp = sum(prices) / len(prices) if prices else price_now

            dynamic_expensive = avgp + (maxp - minp) * 0.25
            expensive = max(expensive_fixed, dynamic_expensive)

            surplus = max(pv - load, 0)
            soc_notfall = max(soc_min - 4, 5)

            # --- Entscheidung ---
            ai_status = "standby"
            recommendation = "standby"

            hw_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # Notfall (immer!)
            if soc <= soc_notfall and soc < soc_max:
                ai_status = "notladung"
                recommendation = "billig_laden"
                hw_mode = "input"
                in_w = min(300, max_charge)

            elif mode != MODE_MANUAL:

                # Teuer jetzt → entladen
                if price_now >= expensive and soc > soc_min:
                    ai_status = "teuer_jetzt"
                    recommendation = "entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, max(load - pv, 0))

                # Günstigste Phase → laden
                elif prices and prices[0] == minp and soc < soc_max:
                    ai_status = "günstig_jetzt"
                    recommendation = "ki_laden"
                    hw_mode = "input"
                    in_w = max_charge

                # PV-Überschuss
                elif surplus > 80 and soc < soc_max:
                    ai_status = "pv_laden"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, surplus)

            # --- Recommendation-Freeze ---
            if self._freeze_until and now < self._freeze_until:
                recommendation = self._last_recommendation
                ai_status = self._last_ai_status
            else:
                if recommendation != self._last_recommendation:
                    self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                    self._last_recommendation = recommendation
                    self._last_ai_status = ai_status

            # --- Hardware anwenden ---
            if mode != MODE_MANUAL:
                await self._apply_hardware(hw_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "mode": mode,
                    "price_now": price_now,
                    "min_price": minp,
                    "max_price": maxp,
                    "avg_price": avgp,
                    "expensive": expensive,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "surplus": surplus,
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
