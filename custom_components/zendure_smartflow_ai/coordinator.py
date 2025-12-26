from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    UPDATE_INTERVAL,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    ZENDURE_MODE_INPUT,
    ZENDURE_MODE_OUTPUT,
    STATUS_READY,
    STATUS_ERROR,
    DEBUG_OK,
    DEBUG_SENSOR_INVALID,
    DEBUG_PRICE_INVALID,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    soc: str
    pv: str

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None

    price_export: str | None
    price_now: str | None

    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        s = str(val).strip().replace(",", ".")
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Hält Zustände, berechnet Empfehlung, steuert Hardware, liefert Daten an Sensoren."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        data = entry.data or {}

        self.entities = EntityIds(
            soc=data.get(CONF_SOC_ENTITY, ""),
            pv=data.get(CONF_PV_ENTITY, ""),

            grid_mode=data.get(CONF_GRID_MODE, GRID_MODE_NONE),
            grid_power=data.get(CONF_GRID_POWER_ENTITY),
            grid_import=data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=data.get(CONF_GRID_EXPORT_ENTITY),

            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            price_now=data.get(CONF_PRICE_NOW_ENTITY),

            ac_mode=data.get(CONF_AC_MODE_ENTITY, ""),
            input_limit=data.get(CONF_INPUT_LIMIT_ENTITY, ""),
            output_limit=data.get(CONF_OUTPUT_LIMIT_ENTITY, ""),
        )

        # Runtime (Selects)
        self.runtime_mode: dict[str, str] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        # Settings (Numbers) – werden durch number.py in hass.data gepflegt
        self.settings: dict[str, float] = {
            "soc_min": DEFAULT_SOC_MIN,
            "soc_max": DEFAULT_SOC_MAX,
            "max_charge": DEFAULT_MAX_CHARGE,
            "max_discharge": DEFAULT_MAX_DISCHARGE,
            "price_threshold": DEFAULT_PRICE_THRESHOLD,
            "very_expensive_threshold": DEFAULT_VERY_EXPENSIVE_THRESHOLD,
        }

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # --------------------------------------------------
    def _state(self, entity_id: str | None) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str | None, attr: str) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    def _get_price(self) -> float | None:
        # 1) Direkter Preissensor (state = €/kWh)
        p = _to_float(self._state(self.entities.price_now))
        if p is not None:
            return p

        # 2) Tibber Export: attributes.data mit price_per_kwh (15 min)
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(export):
            return None

        item = export[idx]
        if not isinstance(item, dict):
            return None
        return _to_float(item.get("price_per_kwh"))

    def _get_grid(self) -> tuple[float | None, float | None, float | None]:
        """returns (grid_power_signed, grid_import, grid_export) in W"""
        mode = self.entities.grid_mode

        if mode == GRID_MODE_SINGLE:
            gp = _to_float(self._state(self.entities.grid_power))
            if gp is None:
                return None, None, None
            gi = max(gp, 0.0)
            ge = max(-gp, 0.0)
            return gp, gi, ge

        if mode == GRID_MODE_SPLIT:
            gi = _to_float(self._state(self.entities.grid_import))
            ge = _to_float(self._state(self.entities.grid_export))
            if gi is None and ge is None:
                return None, None, None
            gi = gi or 0.0
            ge = ge or 0.0
            gp = gi - ge
            return gp, gi, ge

        return None, None, None

    # --------------------------------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        if not self.entities.ac_mode:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        if not self.entities.input_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        if not self.entities.output_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)

            soc = _to_float(soc_raw)
            pv = _to_float(pv_raw)

            gp, gi, ge = self._get_grid()

            # Sensor valid?
            if soc is None or pv is None:
                return {
                    "status": STATUS_ERROR,
                    "ai_status": "sensor_invalid",
                    "recommendation": "standby",
                    "debug": DEBUG_SENSOR_INVALID,
                    "details": {
                        "soc_raw": soc_raw,
                        "pv_raw": pv_raw,
                        "grid_mode": self.entities.grid_mode,
                    },
                }

            # Load calculation (preferred)
            load = None
            if gi is not None and ge is not None:
                load = pv + gi - ge
                if load < 0:
                    load = 0.0

            # Price optional
            price = self._get_price()

            # Settings
            soc_min = float(self.settings.get("soc_min", DEFAULT_SOC_MIN))
            soc_max = float(self.settings.get("soc_max", DEFAULT_SOC_MAX))
            max_charge = float(self.settings.get("max_charge", DEFAULT_MAX_CHARGE))
            max_discharge = float(self.settings.get("max_discharge", DEFAULT_MAX_DISCHARGE))
            thr = float(self.settings.get("price_threshold", DEFAULT_PRICE_THRESHOLD))
            thr_very = float(self.settings.get("very_expensive_threshold", DEFAULT_VERY_EXPENSIVE_THRESHOLD))

            ai_mode = self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            manual_action = self.runtime_mode.get("manual_action", MANUAL_STANDBY)

            # If we can't compute load, we still can run basic logic on pv only (but limited)
            load_eff = load if load is not None else 0.0

            surplus = max(pv - load_eff, 0.0)
            deficit = max(load_eff - pv, 0.0)

            # Defaults
            status = STATUS_READY
            ai_status = "standby"
            recommendation = "standby"
            set_mode = ZENDURE_MODE_INPUT
            in_w = 0.0
            out_w = 0.0

            # ==================================================
            # MANUAL
            # ==================================================
            if ai_mode == AI_MODE_MANUAL:
                ai_status = "manual"
                recommendation = manual_action

                if manual_action == MANUAL_STANDBY:
                    set_mode = ZENDURE_MODE_INPUT
                    in_w = 0.0
                    out_w = 0.0
                elif manual_action == MANUAL_CHARGE:
                    set_mode = ZENDURE_MODE_INPUT
                    in_w = max_charge
                    out_w = 0.0
                elif manual_action == MANUAL_DISCHARGE:
                    set_mode = ZENDURE_MODE_OUTPUT
                    out_w = max_discharge
                    in_w = 0.0

            # ==================================================
            # SUMMER (PV-first, price optional)
            # ==================================================
            elif ai_mode == AI_MODE_SUMMER:
                if surplus > 80 and soc < soc_max:
                    ai_status = "pv_surplus"
                    recommendation = "charge"
                    set_mode = ZENDURE_MODE_INPUT
                    in_w = min(max_charge, surplus)
                elif deficit > 50 and soc > soc_min:
                    ai_status = "cover_deficit"
                    recommendation = "discharge"
                    set_mode = ZENDURE_MODE_OUTPUT
                    out_w = min(max_discharge, deficit)
                else:
                    ai_status = "standby"
                    recommendation = "standby"

            # ==================================================
            # WINTER (price-first, requires price)
            # ==================================================
            elif ai_mode == AI_MODE_WINTER:
                if price is None:
                    ai_status = "price_invalid"
                    recommendation = "standby"
                    # no blocking – just no price based actions
                else:
                    if price >= thr_very and soc > soc_min:
                        ai_status = "very_expensive"
                        recommendation = "discharge"
                        set_mode = ZENDURE_MODE_OUTPUT
                        out_w = min(max_discharge, deficit if deficit > 0 else max_discharge)
                    elif price >= thr and soc > soc_min:
                        ai_status = "expensive"
                        recommendation = "discharge"
                        set_mode = ZENDURE_MODE_OUTPUT
                        out_w = min(max_discharge, deficit)
                    elif surplus > 80 and soc < soc_max:
                        ai_status = "pv_surplus"
                        recommendation = "charge"
                        set_mode = ZENDURE_MODE_INPUT
                        in_w = min(max_charge, surplus)
                    else:
                        ai_status = "standby"
                        recommendation = "standby"

            # ==================================================
            # AUTOMATIC (hybrid)
            # ==================================================
            else:
                # Prefer: very expensive -> discharge
                if price is not None and price >= thr_very and soc > soc_min:
                    ai_status = "very_expensive"
                    recommendation = "discharge"
                    set_mode = ZENDURE_MODE_OUTPUT
                    out_w = min(max_discharge, deficit if deficit > 0 else max_discharge)

                elif price is not None and price >= thr and soc > soc_min and deficit > 50:
                    ai_status = "expensive"
                    recommendation = "discharge"
                    set_mode = ZENDURE_MODE_OUTPUT
                    out_w = min(max_discharge, deficit)

                elif surplus > 80 and soc < soc_max:
                    ai_status = "pv_surplus"
                    recommendation = "charge"
                    set_mode = ZENDURE_MODE_INPUT
                    in_w = min(max_charge, surplus)

                elif deficit > 50 and soc > soc_min:
                    ai_status = "cover_deficit"
                    recommendation = "discharge"
                    set_mode = ZENDURE_MODE_OUTPUT
                    out_w = min(max_discharge, deficit)

                else:
                    ai_status = "standby"
                    recommendation = "standby"

            # Apply hardware (always; this is v0.11.1 behavior)
            await self._set_ac_mode(set_mode)
            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            debug = DEBUG_OK
            if ai_mode in (AI_MODE_WINTER, AI_MODE_AUTOMATIC) and price is None:
                debug = DEBUG_PRICE_INVALID

            return {
                "status": status,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": debug,
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "grid_power": gp,
                    "grid_import": gi,
                    "grid_export": ge,
                    "load": load,
                    "surplus": surplus,
                    "deficit": deficit,
                    "price_now": price,
                    "ai_mode": ai_mode,
                    "manual_action": manual_action,
                    "set_mode": set_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                    "settings": {
                        "soc_min": soc_min,
                        "soc_max": soc_max,
                        "max_charge": max_charge,
                        "max_discharge": max_discharge,
                        "price_threshold": thr,
                        "very_expensive_threshold": thr_very,
                    },
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
