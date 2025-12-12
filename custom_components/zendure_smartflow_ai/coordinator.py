from __future__ import annotations

from datetime import timedelta
from typing import Any, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN


class ZendureSmartFlowCoordinator(DataUpdateCoordinator):
    """Central brain of Zendure SmartFlow AI"""

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        super().__init__(
            hass,
            logger=LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=30),
        )

    # ============================================================
    # 🔁 UPDATE LOOP
    # ============================================================

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return self._calculate()
        except Exception as err:
            return {
                "ai_status": "fehler",
                "recommendation": "standby",
                "debug": f"Fehler: {err}",
                "debug_attributes": {},
            }

    # ============================================================
    # 🧠 CORE LOGIC
    # ============================================================

    def _calculate(self) -> dict[str, Any]:
        # ------------------------------------------------------------
        # 🔧 CONFIG
        # ------------------------------------------------------------
        cfg = self.entry.data

        soc_entity = cfg["soc_entity"]
        price_entity = cfg["price_export_entity"]

        soc_min = cfg["soc_min"]
        soc_max = cfg["soc_max"]
        battery_kwh = cfg["battery_kwh"]

        max_charge_w = cfg["max_charge_w"]
        max_discharge_w = cfg["max_discharge_w"]

        expensive_threshold = cfg["price_expensive"]

        # ------------------------------------------------------------
        # 🔋 SOC
        # ------------------------------------------------------------
        soc = float(self._state(soc_entity, 0))
        soc_clamped = min(max(soc, 0), 100)

        usable_kwh = max(soc_clamped - soc_min, 0) / 100 * battery_kwh

        # ------------------------------------------------------------
        # 💰 PRICE SERIES
        # ------------------------------------------------------------
        export = self.hass.states.get(price_entity)
        if not export or not export.attributes.get("data"):
            return self._result(
                ai_status="datenproblem_preise",
                recommendation="standby",
                debug="Keine Preisdaten verfügbar",
            )

        prices: List[float] = [
            float(p["price_per_kwh"])
            for p in export.attributes["data"]
            if "price_per_kwh" in p
        ]

        if not prices:
            return self._result(
                ai_status="datenproblem_preise",
                recommendation="standby",
                debug="Preisliste leer",
            )

        current_price = prices[0]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        span = max_price - min_price

        # ------------------------------------------------------------
        # 📈 DYNAMIC THRESHOLD
        # ------------------------------------------------------------
        dynamic_expensive = avg_price + span * 0.25
        expensive = max(expensive_threshold, dynamic_expensive)

        # ------------------------------------------------------------
        # 🔥 PEAK DETECTION
        # ------------------------------------------------------------
        peak_slots = [p for p in prices if p >= expensive]

        if not peak_slots:
            return self._result(
                ai_status="keine_peaks",
                recommendation="standby",
                debug=f"Keine Peaks > {round(expensive,3)} €/kWh",
                extra={
                    "current_price": current_price,
                    "min_price": min_price,
                    "max_price": max_price,
                },
            )

        first_peak_idx = prices.index(peak_slots[0])
        minutes_to_peak = first_peak_idx * 15

        # ------------------------------------------------------------
        # ⚡ ENERGY CALC
        # ------------------------------------------------------------
        discharge_kw = max_discharge_w * 0.85 / 1000
        charge_kw = max_charge_w * 0.75 / 1000

        peak_hours = len(peak_slots) * 0.25
        needed_kwh = peak_hours * discharge_kw
        missing_kwh = max(needed_kwh - usable_kwh, 0)

        need_minutes = (missing_kwh / charge_kw * 60) if missing_kwh > 0 else 0

        # ------------------------------------------------------------
        # 🟢 CHEAPEST SLOT
        # ------------------------------------------------------------
        cheapest_price = min_price
        cheapest_idx = prices.index(cheapest_price)
        cheapest_in_future = cheapest_idx > 0

        # ------------------------------------------------------------
        # 🧠 DECISION TREE (DE)
        # ------------------------------------------------------------

        # 1) Teuer jetzt
        if current_price >= expensive:
            if soc <= soc_min:
                return self._result(
                    ai_status="teuer_jetzt_akkuschutz",
                    recommendation="standby",
                    debug="Teurer Preis, Akku unter Reserve",
                )
            else:
                return self._result(
                    ai_status="teuer_jetzt_entladen_empfohlen",
                    recommendation="entladen",
                    debug="Teurer Preis, Entladen sinnvoll",
                )

        # 2) Peak kommt + Energie fehlt
        if missing_kwh > 0 and minutes_to_peak <= need_minutes + 30:
            return self._result(
                ai_status="laden_notwendig_fuer_peak",
                recommendation="ki_laden",
                debug=f"Peak in {round(minutes_to_peak/60,2)}h, {round(missing_kwh,2)} kWh fehlen",
            )

        # 3) Günstigste Phase kommt noch
        if cheapest_in_future and soc < soc_max:
            return self._result(
                ai_status="guenstigste_phase_kommt_noch",
                recommendation="standby",
                debug=f"Günstigste Phase bei {round(cheapest_price,3)} €/kWh",
            )

        # 4) Günstigste Phase verpasst
        if not cheapest_in_future and soc < soc_max:
            return self._result(
                ai_status="guenstigste_phase_verpasst",
                recommendation="ki_laden",
                debug="Günstigste Phase war bereits",
            )

        # 5) Alles ok
        return self._result(
            ai_status="ausreichend_geladen",
            recommendation="standby",
            debug="Kein Handlungsbedarf",
        )

    # ============================================================
    # 🧰 HELPERS
    # ============================================================

    def _state(self, entity_id: str, default: Any = None) -> Any:
        s = self.hass.states.get(entity_id)
        return s.state if s else default

    def _result(
        self,
        ai_status: str,
        recommendation: str,
        debug: str,
        extra: dict | None = None,
    ) -> dict[str, Any]:
        return {
            "ai_status": ai_status,
            "recommendation": recommendation,
            "debug": debug,
            "debug_attributes": extra or {},
        }
