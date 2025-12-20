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

# ======================================================
# Betriebsmodi (Integration!)
# ======================================================
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

# ======================================================
# Entity IDs
# ======================================================
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

    operation_mode: str  # ← Betriebsmodus der Integration!

    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.pv_power",
    load="sensor.house_consumption",
    price_export="sensor.price_export",

    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",

    operation_mode="select.zendure_betriebsmodus",

    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)

# ======================================================
# Helper
# ======================================================
def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def _bad(value: Any) -> bool:
    return value in (None, "unknown", "unavailable", "")

# ======================================================
# Coordinator
# ======================================================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
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

    # --------------------------------------------------
    # State helpers
    # --------------------------------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    # Preis jetzt (15-Min Slot)
    # --------------------------------------------------
    def _price_now(self) -> float | None:
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list):
            return None

        idx = int((dt_util.now().hour * 60 + dt_util.now().minute) // 15)
        try:
            return _to_float(export[idx].get("price_per_kwh"))
        except Exception:
            return None

    # --------------------------------------------------
    # Hardware allowed?
    # --------------------------------------------------
    def _hardware_allowed(self, mode: str) -> bool:
        return mode != MODE_MANUAL

    # --------------------------------------------------
    # Hardware calls
    # --------------------------------------------------
    async def _apply_hardware(self, mode: str, in_w: float, out_w: float) -> None:
        if not self._hardware_allowed(mode):
            return

        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(in_w, 0)},
            blocking=False,
        )

        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(out_w, 0)},
            blocking=False,
        )

    # ==================================================
    # Main update
    # ==================================================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # -----------------------------
            # Betriebsmodus
            # -----------------------------
            mode = self._state(self.entities.operation_mode) or MODE_AUTOMATIC

            if mode == MODE_MANUAL:
                return {
                    "ai_status": "manual_mode",
                    "recommendation": "manual_control",
                    "debug": "MANUAL_MODE_ACTIVE",
                }

            # -----------------------------
            # Sensoren
            # -----------------------------
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)
            load_raw = self._state(self.entities.load)

            if _bad(soc_raw) or _bad(load_raw):
                return {
                    "ai_status": "sensor_invalid",
                    "recommendation": "standby",
                    "debug": "SENSOR_INVALID",
                }

            soc = _to_float(soc_raw)
            pv = _to_float(pv_raw)
            load = _to_float(load_raw)

            price_now = self._price_now()
            if price_now is None and mode != MODE_SUMMER:
                return {
                    "ai_status": "price_invalid",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                }

            # -----------------------------
            # Parameter
            # -----------------------------
            soc_min = _to_float(self._state(self.entities.soc_min), 12)
            soc_max = _to_float(self._state(self.entities.soc_max), 100)
            expensive = _to_float(self._state(self.entities.expensive_threshold), 0.35)
            max_charge = _to_float(self._state(self.entities.max_charge), 2000)
            max_discharge = _to_float(self._state(self.entities.max_discharge), 700)

            surplus = max(pv - load, 0)
            soc_notfall = max(soc_min - 4, 5)

            # ==================================================
            # Entscheidungslogik
            # ==================================================
            ai_status = "standby"
            recommendation = "standby"
            ac_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # --- Winter / Automatik: Preis ---
            if mode in (MODE_AUTOMATIC, MODE_WINTER):
                if price_now >= expensive and soc > soc_min:
                    ai_status = "teuer_jetzt"
                    recommendation = "entladen"
                    ac_mode = "output"
                    out_w = min(max_discharge, max(load - pv, 0))

            # --- Sommer: Autarkie ---
            if mode in (MODE_AUTOMATIC, MODE_SUMMER):
                if surplus > 80 and soc < soc_max:
                    ai_status = "pv_laden"
                    recommendation = "laden"
                    ac_mode = "input"
                    in_w = min(max_charge, surplus)

            # --- Notfall immer ---
            if soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                ac_mode = "input"
                in_w = min(max_charge, 300)

            # ==================================================
            # Freeze (nur Anzeige)
            # ==================================================
            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            # ==================================================
            # Hardware anwenden
            # ==================================================
            await self._apply_hardware(ac_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "mode": mode,
                    "price_now": price_now,
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "set_mode": ac_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
