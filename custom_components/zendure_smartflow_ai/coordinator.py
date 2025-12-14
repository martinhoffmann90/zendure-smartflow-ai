from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .constants import (
    FREEZE_MIN_TOL_W,
    MODE_AUTOMATIC,
    MODE_MANUAL,
    MODE_SUMMER,
    MODE_WINTER,
    AI_DATA_PROBLEM,
    AI_MANUELL,
    AI_NOTLADUNG_AKTIV,
    AI_PV_UEBERSCHUSS_LADEN,
    AI_STANDBY,
    AI_TEUER_AKKUSCHUTZ,
    AI_TEUER_ENTLADEN,
    AI_GUENSTIG_JETZT_LADEN,
    AI_GUENSTIG_WARTEN,
    AI_GUENSTIG_VERPASST,
    REC_BILLIG_LADEN,
    REC_ENTLADEN,
    REC_KI_LADEN,
    REC_LADEN,
    REC_STANDBY,
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

    # Helfer / Parameter
    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str
    mode_select: str  # input_select.zendure_betriebsmodus

    # Zendure Steuer-Entitäten
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
    mode_select="input_select.zendure_betriebsmodus",
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
    """Coordinator = Daten holen + Entscheidung + direkte Steuerung."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        data = entry.data or {}
        self.entities = EntityIds(
            soc=data.get("soc_entity", DEFAULT_ENTITY_IDS.soc),
            pv=data.get("pv_entity", DEFAULT_ENTITY_IDS.pv),
            load=data.get("load_entity", DEFAULT_ENTITY_IDS.load),
            price_now=data.get("price_now_entity", DEFAULT_ENTITY_IDS.price_now),
            price_export=data.get("price_export_entity", DEFAULT_ENTITY_IDS.price_export),
            soc_min=data.get("soc_min_entity", DEFAULT_ENTITY_IDS.soc_min),
            soc_max=data.get("soc_max_entity", DEFAULT_ENTITY_IDS.soc_max),
            expensive_threshold=data.get("expensive_threshold_entity", DEFAULT_ENTITY_IDS.expensive_threshold),
            max_charge=data.get("max_charge_entity", DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=data.get("max_discharge_entity", DEFAULT_ENTITY_IDS.max_discharge),
            mode_select=data.get("mode_select_entity", DEFAULT_ENTITY_IDS.mode_select),
            ac_mode=data.get("ac_mode_entity", DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=data.get("input_limit_entity", DEFAULT_ENTITY_IDS.input_limit),
            output_limit=data.get("output_limit_entity", DEFAULT_ENTITY_IDS.output_limit),
        )

        # Schutz gegen Flattern/Service-Spam
        self._last_set_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None

        # Recommendation-Freeze
        self._last_eval_idx: int | None = None
        self._last_user_mode: str | None = None
        self._frozen_ai_status: str = AI_STANDBY
        self._frozen_recommendation: str = REC_STANDBY
        self._frozen_control_mode: str = "input"
        self._frozen_in_w: float = 0.0
        self._frozen_out_w: float = 0.0

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # -------------------- HA State Helpers --------------------

    def _get_state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _get_attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        if st is None:
            return None
        return st.attributes.get(attr)

    # -------------------- Control Calls --------------------

    async def _set_mode_input(self) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": "input"},
            blocking=False,
        )

    async def _set_mode_output(self) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": "output"},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _apply_control(self, mode: str, in_w: float, out_w: float) -> None:
        """Apply only if changed enough -> verhindert Flattern & Log-Spam."""

        def changed(prev: float | None, new: float, tol: float) -> bool:
            if prev is None:
                return True
            return abs(prev - new) > tol

        if mode != self._last_set_mode:
            if mode == "input":
                await self._set_mode_input()
            elif mode == "output":
                await self._set_mode_output()
            self._last_set_mode = mode

        if changed(self._last_in, in_w, FREEZE_MIN_TOL_W):
            await self._set_input_limit(in_w)
            self._last_in = in_w

        if changed(self._last_out, out_w, FREEZE_MIN_TOL_W):
            await self._set_output_limit(out_w)
            self._last_out = out_w

    # -------------------- Price Helpers --------------------

    def _extract_prices(self) -> list[float]:
        """
        Tibber Datenexport:
        attributes.data = [{start_time:..., price_per_kwh: 0.287}, ...]
        """
        export = self._get_attr(self.entities.price_export, "data")
        if not export:
            return []

        prices: list[float] = []
        try:
            for item in export:
                p = item.get("price_per_kwh")
                prices.append(_f(p, 0.0))
        except Exception:
            return []
        return prices

    def _idx_now_15min(self) -> int:
        now = dt_util.now()
        minutes = (now.hour * 60) + now.minute
        return int(minutes // 15)

    def _find_first_peak_start(self, future: list[float], expensive: float) -> int | None:
        for i, p in enumerate(future):
            if p >= expensive:
                return i
        return None

    def _find_cheapest_before_peak(
        self, future: list[float], peak_start: int | None
    ) -> tuple[int | None, float | None]:
        if not future:
            return None, None

        if peak_start is None or peak_start <= 0:
            # kein Peak -> günstigste Phase in der Zukunft (innerhalb future)
            m = min(future)
            return future.index(m), m

        window = future[:peak_start]  # nur VOR dem Peak
        if not window:
            return None, None
        m = min(window)
        return window.index(m), m

    # -------------------- Freeze Decision --------------------

    def _should_recompute(
        self,
        idx: int,
        user_mode: str,
        soc: float,
        soc_min: float,
        soc_max: float,
        soc_notfall: float,
    ) -> bool:
        # 1) erster Lauf
        if self._last_eval_idx is None:
            return True

        # 2) neuer 15-Minuten Slot
        if idx != self._last_eval_idx:
            return True

        # 3) Modus geändert
        if user_mode != self._last_user_mode:
            return True

        # 4) Notfall / Schwellenwechsel
        # (Wenn SoC in kritische Bereiche kommt, neu bewerten)
        if soc <= soc_notfall:
            return True
        if soc <= soc_min:
            return True
        if soc >= soc_max:
            return True

        return False

    # -------------------- Main Update --------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # --- Basiswerte ---
            soc = _f(self._get_state(self.entities.soc), 0.0)
            pv = _f(self._get_state(self.entities.pv), 0.0)
            load = _f(self._get_state(self.entities.load), 0.0)
            price_now = _f(self._get_state(self.entities.price_now), 0.0)

            soc_min = _f(self._get_state(self.entities.soc_min), 12.0)
            soc_max = _f(self._get_state(self.entities.soc_max), 95.0)
            soc_notfall = max(soc_min - 4.0, 5.0)

            expensive_threshold = _f(self._get_state(self.entities.expensive_threshold), 0.35)
            max_charge = _f(self._get_state(self.entities.max_charge), 2000.0)
            max_discharge = _f(self._get_state(self.entities.max_discharge), 700.0)

            user_mode = self._get_state(self.entities.mode_select) or MODE_AUTOMATIC

            prices_all = self._extract_prices()
            idx = self._idx_now_15min()
            future = prices_all[idx:] if idx < len(prices_all) else []

            # dynamische Schwelle
            if future:
                minp = min(future)
                maxp = max(future)
                avg = sum(future) / len(future)
                span = maxp - minp
                dynamic_expensive = avg + span * 0.25
                expensive = max(expensive_threshold, dynamic_expensive)
            else:
                minp = price_now
                maxp = price_now
                avg = price_now
                span = 0.0
                dynamic_expensive = expensive_threshold
                expensive = expensive_threshold

            peak_start = self._find_first_peak_start(future, expensive) if future else None
            cheapest_idx, cheapest_price = self._find_cheapest_before_peak(future, peak_start)

            in_cheapest_slot = (cheapest_idx == 0) if cheapest_idx is not None else False
            cheapest_future = (cheapest_idx is not None and cheapest_idx > 0)

            surplus = max(pv - load, 0.0)

            # --- Freeze Gate ---
            recompute = self._should_recompute(idx, user_mode, soc, soc_min, soc_max, soc_notfall)

            if recompute:
                ai_status, recommendation, control_mode, in_w, out_w = self._compute_decision(
                    user_mode=user_mode,
                    soc=soc,
                    soc_min=soc_min,
                    soc_max=soc_max,
                    soc_notfall=soc_notfall,
                    price_now=price_now,
                    expensive=expensive,
                    surplus=surplus,
                    in_cheapest_slot=in_cheapest_slot,
                    cheapest_future=cheapest_future,
                    max_charge=max_charge,
                    max_discharge=max_discharge,
                    load=load,
                    pv=pv,
                    has_prices=bool(prices_all),
                )

                # Freeze store
                self._last_eval_idx = idx
                self._last_user_mode = user_mode
                self._frozen_ai_status = ai_status
                self._frozen_recommendation = recommendation
                self._frozen_control_mode = control_mode
                self._frozen_in_w = in_w
                self._frozen_out_w = out_w

            # --- APPLY CONTROL ---
            # Modus B (Manuell): nur Notfallschutz, sonst KEINE Eingriffe!
            if user_mode == MODE_MANUAL:
                if self._frozen_ai_status == AI_NOTLADUNG_AKTIV:
                    await self._apply_control(self._frozen_control_mode, self._frozen_in_w, self._frozen_out_w)
                # else: gar nichts setzen
            else:
                await self._apply_control(self._frozen_control_mode, self._frozen_in_w, self._frozen_out_w)

            details = {
                "mode_user": user_mode,
                "price_now": round(price_now, 4),
                "min_price_future": round(minp, 4),
                "max_price_future": round(maxp, 4),
                "avg_price_future": round(avg, 4),
                "expensive_threshold_effective": round(expensive, 4),
                "expensive_threshold_fixed": round(expensive_threshold, 4),
                "expensive_threshold_dynamic": round(dynamic_expensive, 4),
                "idx_now": idx,
                "future_len": len(future),
                "peak_start_idx": peak_start,
                "cheapest_idx": cheapest_idx,
                "cheapest_price": cheapest_price,
                "cheapest_future": cheapest_future,
                "in_cheapest_slot": in_cheapest_slot,
                "soc": round(soc, 2),
                "soc_min": round(soc_min, 2),
                "soc_max": round(soc_max, 2),
                "soc_notfall": round(soc_notfall, 2),
                "pv": round(pv, 1),
                "load": round(load, 1),
                "surplus": round(surplus, 1),
                "max_charge": round(max_charge, 0),
                "max_discharge": round(max_discharge, 0),
                "set_mode": self._frozen_control_mode,
                "set_input_w": round(self._frozen_in_w, 0),
                "set_output_w": round(self._frozen_out_w, 0),
                "freeze": {
                    "recomputed": recompute,
                    "last_eval_idx": self._last_eval_idx,
                    "last_user_mode": self._last_user_mode,
                },
            }

            return {
                "ai_status": self._frozen_ai_status,
                "recommendation": self._frozen_recommendation,
                "debug": "OK",
                "details": details,
                "price_now": price_now,
                "expensive_threshold": expensive,
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

    def _compute_decision(
        self,
        *,
        user_mode: str,
        soc: float,
        soc_min: float,
        soc_max: float,
        soc_notfall: float,
        price_now: float,
        expensive: float,
        surplus: float,
        in_cheapest_slot: bool,
        cheapest_future: bool,
        max_charge: float,
        max_discharge: float,
        load: float,
        pv: float,
        has_prices: bool,
    ) -> tuple[str, str, str, float, float]:
        """
        Returns: ai_status, recommendation, control_mode, in_w, out_w
        """

        # Datenproblem
        if not has_prices:
            return AI_DATA_PROBLEM, REC_STANDBY, "input", 0.0, 0.0

        # MANUELL (Modus B): nur Notfallschutz
        if user_mode == MODE_MANUAL:
            if soc <= soc_notfall and soc < soc_max:
                in_w = max(0.0, min(max_charge, 300.0))
                return AI_NOTLADUNG_AKTIV, REC_BILLIG_LADEN, "input", in_w, 0.0
            return AI_MANUELL, REC_STANDBY, "input", 0.0, 0.0

        # 1) Notladung (immer, auch Sommer/Winter/Automatik)
        if soc <= soc_notfall and soc < soc_max:
            in_w = max(0.0, min(max_charge, 300.0))
            return AI_NOTLADUNG_AKTIV, REC_BILLIG_LADEN, "input", in_w, 0.0

        # 2) Teuer jetzt -> entladen wenn möglich, sonst Schutz
        if price_now >= expensive:
            if soc <= soc_min:
                return AI_TEUER_AKKUSCHUTZ, REC_STANDBY, "input", 0.0, 0.0
            need = max(load - pv, 0.0)
            out_w = min(max_discharge, need)
            return AI_TEUER_ENTLADEN, REC_ENTLADEN, "output", 0.0, out_w

        # 3) Sommer: keine Netz-Ladung (nur PV), aber Entladen bei teuer erlauben (oben schon)
        if user_mode == MODE_SUMMER:
            if surplus > 80 and soc < soc_max:
                in_w = min(max_charge, max(0.0, surplus))
                return AI_PV_UEBERSCHUSS_LADEN, REC_LADEN, "input", in_w, 0.0
            return AI_STANDBY, REC_STANDBY, "input", 0.0, 0.0

        # 4) Automatik/Winter: günstigste Phase vor Peak zählt (oder allgemein günstigste, wenn kein Peak)
        if in_cheapest_slot and soc < soc_max:
            return AI_GUENSTIG_JETZT_LADEN, REC_KI_LADEN, "input", max_charge, 0.0

        if cheapest_future and soc < soc_max:
            return AI_GUENSTIG_WARTEN, REC_STANDBY, "input", 0.0, 0.0

        if (not cheapest_future) and soc < soc_max:
            # günstigste Phase war schon – wir laden NICHT blind, aber markieren
            return AI_GUENSTIG_VERPASST, REC_STANDBY, "input", 0.0, 0.0

        # 5) PV Überschuss immer nutzen (auch Automatik/Winter)
        if surplus > 80 and soc < soc_max:
            in_w = min(max_charge, max(0.0, surplus))
            return AI_PV_UEBERSCHUSS_LADEN, REC_LADEN, "input", in_w, 0.0

        return AI_STANDBY, REC_STANDBY, "input", 0.0, 0.0
