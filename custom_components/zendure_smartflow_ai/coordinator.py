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

# Sicherheits-Grenze: Notladung nur bei "wirklich leer"
EMERGENCY_SOC_CAP = 20.0      # Notladung nur, wenn SoC < 20%


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
def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None:
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


def _changed(prev: float | None, new: float, tol: float) -> bool:
    if prev is None:
        return True
    return abs(prev - new) > tol


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
        self._last_ai_status: str | None = None
        self._last_recommendation: str | None = None
        self._last_cmd_mode: str | None = None
        self._last_cmd_in: float | None = None
        self._last_cmd_out: float | None = None

        # Anti-Flattern / Service-Spam
        self._last_set_mode: str | None = None
        self._last_set_in: float | None = None
        self._last_set_out: float | None = None

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
            {"entity_id": self.entities.input_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _set_output(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _apply_hw(self, mode: str, in_w: float, out_w: float) -> None:
        """
        Setzt Hardware nur, wenn sich etwas wirklich geändert hat.
        Das verhindert Flackern + Service-Spam.
        """
        # Mode nur bei Änderung
        if mode != self._last_set_mode:
            await self._set_ac_mode(mode)
            self._last_set_mode = mode

        # Input/Output mit Toleranz (W)
        if _changed(self._last_set_in, in_w, tol=25.0):
            await self._set_input(in_w)
            self._last_set_in = in_w

        if _changed(self._last_set_out, out_w, tol=25.0):
            await self._set_output(out_w)
            self._last_set_out = out_w

    # =========================
    # Main update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # --- Basiswerte ---
            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12.0)
            soc_max = _f(self._state(self.entities.soc_max), 95.0)

            expensive = _f(self._state(self.entities.expensive_threshold), 0.35)

            max_charge = _f(self._state(self.entities.max_charge), 2000.0)
            max_discharge = _f(self._state(self.entities.max_discharge), 700.0)

            surplus = max(pv - load, 0.0)

            # --- Grenzen ---
            soc_notfall = max(soc_min - 4.0, 5.0)

            # ✅ Notladung NUR wenn wirklich leer (sonst passiert genau dein Fehler bei hohen soc_min)
            is_real_emergency = (soc <= soc_notfall) and (soc < EMERGENCY_SOC_CAP)

            # =========================
            # Entscheidungslogik
            # =========================
            ai_status = "standby"
            recommendation = "standby"

            # Hardware-Command
            cmd_mode = "input"
            cmd_in = 0.0
            cmd_out = 0.0

            # 1️⃣ NOTFALL (nur wenn NICHT teuer + wirklich leer)
            if is_real_emergency and price_now < expensive and soc < soc_max:
                ai_status = "notladung"
                recommendation = "billig_laden"
                cmd_mode = "input"
                cmd_in = min(max_charge, 300.0)
                cmd_out = 0.0

            # 2️⃣ TEUER → ENTLADE (wenn über Reserve)
            elif price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                cmd_mode = "output"
                need = max(load - pv, 0.0)
                cmd_out = min(max_discharge, need)
                cmd_in = 0.0

            # 3️⃣ PV-Überschuss → laden (wenn nicht voll)
            elif surplus > 80.0 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                cmd_mode = "input"
                cmd_in = min(max_charge, surplus)
                cmd_out = 0.0

            # 4️⃣ Standby → alles 0 (Mode lassen wir auf input, damit nix entlädt)
            else:
                ai_status = "standby"
                recommendation = "standby"
                cmd_mode = "input"
                cmd_in = 0.0
                cmd_out = 0.0

            # =========================
            # Recommendation Freeze (inkl. Hardware-Command!)
            # =========================
            frozen = False
            if self._freeze_until and now < self._freeze_until:
                frozen = True
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
                cmd_mode = self._last_cmd_mode or cmd_mode
                cmd_in = self._last_cmd_in if self._last_cmd_in is not None else cmd_in
                cmd_out = self._last_cmd_out if self._last_cmd_out is not None else cmd_out
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation
                self._last_cmd_mode = cmd_mode
                self._last_cmd_in = cmd_in
                self._last_cmd_out = cmd_out

            # =========================
            # Hardware anwenden
            # =========================
            await self._apply_hw(cmd_mode, cmd_in, cmd_out)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": price_now,
                    "expensive_threshold": expensive,

                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "soc_notfall": soc_notfall,
                    "is_real_emergency": is_real_emergency,

                    "pv": pv,
                    "load": load,
                    "surplus": surplus,

                    "set_mode": cmd_mode,
                    "set_input_w": round(cmd_in, 0),
                    "set_output_w": round(cmd_out, 0),

                    "frozen": frozen,
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
