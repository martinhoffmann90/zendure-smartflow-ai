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
FREEZE_SECONDS = 60   # bewusst kurz für V0.1.1


# =========================
# Defaults
# =========================
@dataclass(frozen=True)
class Defaults:
    soc_entity: str = "sensor.solarflow_2400_ac_electric_level"
    pv_entity: str = "sensor.pv_power"
    load_entity: str = "sensor.house_load"
    price_now_entity: str | None = None

    grid_mode: str = "single_sensor"
    grid_power_entity: str | None = None
    grid_import_entity: str | None = None
    grid_export_entity: str | None = None

    expensive_threshold_entity: str = "number.zendure_schwelle_teuer"
    soc_min_entity: str = "number.zendure_soc_min"
    soc_max_entity: str = "number.zendure_soc_max"
    max_charge_entity: str = "number.zendure_max_ladeleistung"
    max_discharge_entity: str = "number.zendure_max_entladeleistung"

    ac_mode_entity: str = "select.solarflow_2400_ac_ac_mode"
    input_limit_entity: str = "number.solarflow_2400_ac_input_limit"
    output_limit_entity: str = "number.solarflow_2400_ac_output_limit"


DEFAULTS = Defaults()


# =========================
# Helper
# =========================
def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state in (None, "unknown", "unavailable"):
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


def _pick(entry: ConfigEntry, *keys: str, default=None):
    for src in (entry.options or {}, entry.data or {}):
        for k in keys:
            if k in src and src[k] not in ("", None):
                return src[k]
    return default


# =========================
# Coordinator
# =========================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # Entities
        self.soc_entity = _pick(entry, "soc_entity", default=DEFAULTS.soc_entity)
        self.pv_entity = _pick(entry, "pv_entity", default=DEFAULTS.pv_entity)
        self.load_entity = _pick(entry, "load_entity", default=DEFAULTS.load_entity)
        self.price_now_entity = _pick(entry, "price_now_entity", default=None)

        self.grid_mode = _pick(entry, "grid_mode", default=DEFAULTS.grid_mode)
        self.grid_power_entity = _pick(entry, "grid_power_entity", default=None)
        self.grid_import_entity = _pick(entry, "grid_import_entity", default=None)
        self.grid_export_entity = _pick(entry, "grid_export_entity", default=None)

        self.expensive_threshold_entity = DEFAULTS.expensive_threshold_entity
        self.soc_min_entity = DEFAULTS.soc_min_entity
        self.soc_max_entity = DEFAULTS.soc_max_entity
        self.max_charge_entity = DEFAULTS.max_charge_entity
        self.max_discharge_entity = DEFAULTS.max_discharge_entity

        self.ac_mode_entity = DEFAULTS.ac_mode_entity
        self.input_limit_entity = DEFAULTS.input_limit_entity
        self.output_limit_entity = DEFAULTS.output_limit_entity

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
    # Helpers
    # -------------------------
    def _state(self, entity: str | None) -> str | None:
        if not entity:
            return None
        s = self.hass.states.get(entity)
        return None if s is None else s.state

    def _grid(self) -> tuple[float, float]:
        if self.grid_mode == "single_sensor" and self.grid_power_entity:
            v = _f(self._state(self.grid_power_entity))
            return (max(v, 0.0), max(-v, 0.0))
        if self.grid_mode == "split_sensors":
            return (
                _f(self._state(self.grid_import_entity)),
                _f(self._state(self.grid_export_entity)),
            )
        load = _f(self._state(self.load_entity))
        pv = _f(self._state(self.pv_entity))
        net = load - pv
        return max(net, 0.0), max(-net, 0.0)

    async def _set_mode(self, mode: str):
        await self.hass.services.async_call(
            "select", "select_option",
            {"entity_id": self.ac_mode_entity, "option": mode},
            blocking=False,
        )

    async def _set_input(self, w: float):
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": self.input_limit_entity, "value": round(w, 0)},
            blocking=False,
        )

    async def _set_output(self, w: float):
        await self.hass.services.async_call(
            "number", "set_value",
            {"entity_id": self.output_limit_entity, "value": round(w, 0)},
            blocking=False,
        )

    # =========================
    # Update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            soc = _f(self._state(self.soc_entity))
            pv = _f(self._state(self.pv_entity))
            load = _f(self._state(self.load_entity))
            price_now = _f(self._state(self.price_now_entity), -1)

            soc_min = _f(self._state(self.soc_min_entity), 15)
            soc_max = _f(self._state(self.soc_max_entity), 95)
            expensive = _f(self._state(self.expensive_threshold_entity), 0.35)

            max_charge = _f(self._state(self.max_charge_entity), 2000)
            max_discharge = _f(self._state(self.max_discharge_entity), 800)

            grid_import, grid_export = self._grid()
            surplus = grid_export

            ai_status = "standby"
            recommendation = "standby"
            mode = "input"
            in_w = 0
            out_w = 0

            is_expensive = price_now >= expensive and price_now > 0

            # 1️⃣ TEUER → ENTLADE
            if is_expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                mode = "output"
                out_w = min(max_discharge, grid_import)
                in_w = 0

            # 2️⃣ NOTLADUNG (nur wenn NICHT teuer)
            elif soc <= max(soc_min - 4, 5):
                ai_status = "notladung"
                recommendation = "billig_laden"
                mode = "input"
                in_w = min(max_charge, 300)
                out_w = 0

            # 3️⃣ PV-Überschuss
            elif surplus > 100 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                mode = "input"
                in_w = min(max_charge, surplus)
                out_w = 0

            # Freeze
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
                    "is_expensive": is_expensive,
                    "soc": soc,
                    "grid_import_w": grid_import,
                    "grid_export_w": grid_export,
                    "set_mode": mode,
                    "set_input_w": in_w,
                    "set_output_w": out_w,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
