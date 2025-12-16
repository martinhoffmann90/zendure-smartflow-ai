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

UPDATE_INTERVAL = 10          # Sekunden
FREEZE_SECONDS = 120          # Recommendation-Freeze


# =========================
# Entity IDs
# =========================
@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str

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
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",

    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",

    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


# =========================
# Helper
# =========================
_BAD = {"unknown", "unavailable", "none", "", None}

def _norm(s: str | None) -> str | None:
    if s is None:
        return None
    t = str(s).strip()
    return t

def _is_valid_state(s: str | None) -> bool:
    t = _norm(s)
    if t is None:
        return False
    return t.lower() not in _BAD

def _f(state: str | None, default: float | None = None) -> float | None:
    """Float parser, returns None if invalid."""
    t = _norm(state)
    if not _is_valid_state(t):
        return default
    try:
        # nur Komma->Punkt, sonst nix
        return float(t.replace(",", "."))
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

        # Freeze
        self._freeze_until: datetime | None = None
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -------------------------
    # State helpers
    # -------------------------
    def _state(self, entity_id: str) -> str | None:
        s = self.hass.states.get(entity_id)
        return None if s is None else s.state

    async def _set_ac_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(watts, 0)},
            blocking=False,
        )

    async def _set_output(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(watts, 0)},
            blocking=False,
        )

    # =========================
    # Main update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # --- RAW states (für Debug!) ---
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)
            load_raw = self._state(self.entities.load)
            price_raw = self._state(self.entities.price_now)

            soc_min_raw = self._state(self.entities.soc_min)
            soc_max_raw = self._state(self.entities.soc_max)
            expensive_raw = self._state(self.entities.expensive_threshold)
            max_charge_raw = self._state(self.entities.max_charge)
            max_discharge_raw = self._state(self.entities.max_discharge)

            ac_mode_state = self._state(self.entities.ac_mode)

            # --- Parsed values ---
            soc = _f(soc_raw, 0.0) or 0.0
            pv = _f(pv_raw, 0.0) or 0.0
            load = _f(load_raw, 0.0) or 0.0

            price_now_val = _f(price_raw, None)  # <-- None wenn ungültig!

            soc_min = _f(soc_min_raw, 12.0) or 12.0
            soc_max = _f(soc_max_raw, 95.0) or 95.0
            expensive = _f(expensive_raw, 0.35) or 0.35

            max_charge = _f(max_charge_raw, 2000.0) or 2000.0
            max_discharge = _f(max_discharge_raw, 700.0) or 700.0

            surplus = max(pv - load, 0.0)

            # --- Grenzen ---
            soc_notfall = max(soc_min - 4.0, 5.0)

            # =========================
            # Gültigkeitsprüfungen
            # =========================
            price_valid = price_now_val is not None
            soc_valid = _is_valid_state(soc_raw)
            ac_mode_valid = _is_valid_state(ac_mode_state)

            # Wenn Preis ungültig -> NICHT steuern
            if not price_valid:
                return {
                    "ai_status": "datenproblem_preis",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                    "details": {
                        "raw": {
                            "soc": soc_raw,
                            "pv": pv_raw,
                            "load": load_raw,
                            "price_now": price_raw,
                            "soc_min": soc_min_raw,
                            "soc_max": soc_max_raw,
                            "expensive_threshold": expensive_raw,
                            "max_charge": max_charge_raw,
                            "max_discharge": max_discharge_raw,
                            "ac_mode_state": ac_mode_state,
                        },
                        "valid": {
                            "soc_valid": soc_valid,
                            "price_valid": price_valid,
                            "ac_mode_valid": ac_mode_valid,
                        },
                        "hint": "Preis-Entity liefert 'unknown/unavailable' oder Text. Prüfe entity_id & Einheit.",
                    },
                }

            price_now = float(price_now_val)

            # =========================
            # Entscheidungslogik
            # =========================
            ai_status = "standby"
            recommendation = "standby"

            target_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # 1️⃣ TEUER → ENTLADE (hat Vorrang!)
            if price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                target_mode = "output"
                need = max(load - pv, 0.0)
                out_w = min(max_discharge, need)
                in_w = 0.0

            # 2️⃣ NOTFALL (nur wenn NICHT teuer)
            elif soc <= soc_notfall and price_now < expensive:
                ai_status = "notladung"
                recommendation = "billig_laden"
                target_mode = "input"
                in_w = min(max_charge, 300.0)
                out_w = 0.0

            # 3️⃣ PV-Überschuss
            elif surplus > 80.0 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                target_mode = "input"
                in_w = min(max_charge, surplus)
                out_w = 0.0

            # =========================
            # Recommendation Freeze (aber NICHT bei teuer)
            # =========================
            freeze_active = self._freeze_until is not None and now < self._freeze_until
            if freeze_active and price_now < expensive:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            # =========================
            # Hardware anwenden
            # =========================
            await self._set_ac_mode(target_mode)
            await self._set_input(in_w)
            await self._set_output(out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "raw": {
                        "soc": soc_raw,
                        "pv": pv_raw,
                        "load": load_raw,
                        "price_now": price_raw,
                        "soc_min": soc_min_raw,
                        "soc_max": soc_max_raw,
                        "expensive_threshold": expensive_raw,
                        "max_charge": max_charge_raw,
                        "max_discharge": max_discharge_raw,
                        "ac_mode_state": ac_mode_state,
                    },
                    "valid": {
                        "soc_valid": soc_valid,
                        "price_valid": price_valid,
                        "ac_mode_valid": ac_mode_valid,
                    },
                    "price_now": round(price_now, 6),
                    "expensive_threshold": round(expensive, 6),
                    "soc": round(soc, 2),
                    "soc_min": round(soc_min, 2),
                    "soc_max": round(soc_max, 2),
                    "soc_notfall": round(soc_notfall, 2),
                    "pv": round(pv, 1),
                    "load": round(load, 1),
                    "surplus": round(surplus, 1),
                    "set_mode": target_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                    "freeze_active": freeze_active,
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
