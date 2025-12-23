# custom_components/zendure_smartflow_ai/coordinator.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    UPDATE_INTERVAL,
    FREEZE_SECONDS,
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_SURPLUS_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_export: str | None

    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        s = str(val).strip()
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s.replace(",", "."))
    except Exception:
        return default


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = dt_util.parse_datetime(str(value))
        if dt is None:
            return None
        # normalize to aware
        if dt.tzinfo is None:
            dt = dt_util.as_utc(dt_util.as_local(dt))
        return dt
    except Exception:
        return None


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    v0.6.0 master:
    - hardware control included (as in v0.5.0 behavior)
    - price is optional
    - manual mode never overridden
    - summer strategy works without price
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        data = entry.data or {}

        self.entities = EntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],
            load=data[CONF_LOAD_ENTITY],
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),

            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit=data[CONF_INPUT_LIMIT_ENTITY],
            output_limit=data[CONF_OUTPUT_LIMIT_ENTITY],
        )

        # AI mode + manual action are controlled by select entities in this integration
        self.operation_mode: str = MODE_AUTOMATIC
        self.manual_action: str = MANUAL_STANDBY

        # freeze only text outputs
        self._freeze_until: datetime | None = None
        self._last_ai_status: str | None = None
        self._last_recommendation: str | None = None

        # anti-spam for hardware calls
        self._last_hw_mode: str | None = None
        self._last_in_w: float | None = None
        self._last_out_w: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -------------------------
    # Entity helpers
    # -------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # -------------------------
    # Settings from our number entities (created by this integration)
    # (they may not exist yet on very first refresh -> use defaults)
    # -------------------------
    def _get_setting_number(self, key: str, default: float) -> float:
        # number entity ids are stable: number.<domain>_<key>
        ent = f"number.{self.entry.entry_id}_{key}"
        return _to_float(self._state(ent), default) or default

    # -------------------------
    # Price export (Tibber data export)
    # attributes.data: list[{start_time, price_per_kwh}, ...]
    # -------------------------
    def _price_now_from_export(self) -> float | None:
        if not self.entities.price_export:
            return None

        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        start0 = _parse_dt(export[0].get("start_time"))
        if start0 is None:
            # fallback: old behavior by index-from-midnight
            now_local = dt_util.now()
            idx = int((now_local.hour * 60 + now_local.minute) // 15)
            if 0 <= idx < len(export):
                return _to_float(export[idx].get("price_per_kwh"))
            return None

        now = dt_util.now()
        # make now aware in same tz as start0
        if start0.tzinfo is not None:
            now = dt_util.as_local(now)
        delta = now - dt_util.as_local(start0)
        idx = int(delta.total_seconds() // 900)

        if 0 <= idx < len(export):
            return _to_float(export[idx].get("price_per_kwh"))
        return None

    def _price_stats_future(self) -> dict[str, float] | None:
        """Return min/max/avg for upcoming 24h-ish window (from now)."""
        if not self.entities.price_export:
            return None
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        # try aligned index like _price_now_from_export
        start0 = _parse_dt(export[0].get("start_time"))
        now = dt_util.now()
        if start0 is None:
            idx = int((now.hour * 60 + now.minute) // 15)
        else:
            idx = int(((dt_util.as_local(now) - dt_util.as_local(start0)).total_seconds()) // 900)

        future = export[idx:] if 0 <= idx < len(export) else export
        prices = []
        for item in future:
            p = _to_float(item.get("price_per_kwh"))
            if p is not None:
                prices.append(p)
        if not prices:
            return None
        return {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
        }

    # -------------------------
    # Hardware calls (anti-spam)
    # -------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        if mode == self._last_hw_mode:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )
        self._last_hw_mode = mode

    async def _set_input_limit(self, watts: float) -> None:
        watts = float(round(watts, 0))
        if self._last_in_w is not None and abs(self._last_in_w - watts) < 25:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": watts},
            blocking=False,
        )
        self._last_in_w = watts

    async def _set_output_limit(self, watts: float) -> None:
        watts = float(round(watts, 0))
        if self._last_out_w is not None and abs(self._last_out_w - watts) < 25:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": watts},
            blocking=False,
        )
        self._last_out_w = watts

    async def _apply_hw(self, mode: str, in_w: float, out_w: float) -> None:
        if mode == "input":
            await self._set_ac_mode("input")
            await self._set_input_limit(in_w)
            await self._set_output_limit(0)
        elif mode == "output":
            await self._set_ac_mode("output")
            await self._set_output_limit(out_w)
            await self._set_input_limit(0)
        else:
            # safe fallback
            await self._set_ac_mode("input")
            await self._set_input_limit(0)
            await self._set_output_limit(0)

    # -------------------------
    # Called by select entities
    # -------------------------
    async def async_set_operation_mode(self, mode: str) -> None:
        self.operation_mode = mode
        await self.async_request_refresh()

    async def async_set_manual_action(self, action: str) -> None:
        self.manual_action = action
        await self.async_request_refresh()

    # -------------------------
    # Main update
    # -------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now_utc = dt_util.utcnow()

            soc = _to_float(self._state(self.entities.soc), 0.0) or 0.0
            pv = _to_float(self._state(self.entities.pv), 0.0) or 0.0
            load = _to_float(self._state(self.entities.load), 0.0) or 0.0

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            # settings (from our own number entities, fallback to defaults)
            soc_min = self._get_setting_number("soc_min", float(DEFAULT_SOC_MIN))
            soc_max = self._get_setting_number("soc_max", float(DEFAULT_SOC_MAX))
            max_charge = self._get_setting_number("max_charge", float(DEFAULT_MAX_CHARGE))
            max_discharge = self._get_setting_number("max_discharge", float(DEFAULT_MAX_DISCHARGE))
            expensive_thr = self._get_setting_number("expensive_threshold", float(DEFAULT_EXPENSIVE_THRESHOLD))
            very_expensive_thr = self._get_setting_number("very_expensive_threshold", float(DEFAULT_VERY_EXPENSIVE_THRESHOLD))
            surplus_thr = self._get_setting_number("surplus_threshold", float(DEFAULT_SURPLUS_THRESHOLD))

            price_now = self._price_now_from_export()
            stats = self._price_stats_future()

            # dynamic expensive (optional enhancement)
            dynamic_expensive = None
            if stats:
                span = stats["max"] - stats["min"]
                dynamic_expensive = stats["avg"] + span * 0.25
            effective_expensive = max(expensive_thr, dynamic_expensive) if dynamic_expensive is not None else expensive_thr

            # decision outputs
            ai_status = "init"
            recommendation = "init"
            debug = "OK"

            hw_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # -------------------------
            # 0) MANUAL mode: never overridden
            # -------------------------
            if self.operation_mode == MODE_MANUAL:
                debug = "MANUAL_MODE_ACTIVE"
                ai_status = "manual"
                recommendation = self.manual_action

                if self.manual_action == MANUAL_CHARGE and soc < soc_max:
                    hw_mode = "input"
                    in_w = max_charge
                elif self.manual_action == MANUAL_DISCHARGE and soc > soc_min:
                    hw_mode = "output"
                    out_w = min(max_discharge, max(deficit, 0.0))
                else:
                    hw_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

                # apply hardware (manual is allowed to control)
                await self._apply_hw(hw_mode, in_w, out_w)

                return {
                    "ai_status": ai_status,
                    "recommendation": recommendation,
                    "debug": debug,
                    "details": {
                        "mode": self.operation_mode,
                        "manual_action": self.manual_action,
                        "soc": soc,
                        "pv": pv,
                        "load": load,
                        "surplus": surplus,
                        "deficit": deficit,
                        "set_mode": hw_mode,
                        "set_input_w": round(in_w, 0),
                        "set_output_w": round(out_w, 0),
                    },
                }

            # -------------------------
            # 1) Common emergency guard (only when soc is extremely low)
            # -------------------------
            soc_notfall = max(soc_min - 4.0, 5.0)

            # -------------------------
            # 2) Mode strategies
            # -------------------------
            # SUMMER = PV/autarky, works without price
            if self.operation_mode == MODE_SUMMER:
                ai_status = "summer"
                if soc <= soc_notfall:
                    recommendation = "notladung"
                    hw_mode = "input"
                    in_w = min(max_charge, 300.0)
                elif surplus >= surplus_thr and soc < soc_max:
                    recommendation = "pv_ueberschuss_laden"
                    hw_mode = "input"
                    in_w = min(max_charge, surplus)
                elif deficit > 80 and soc > soc_min:
                    recommendation = "autarkie_entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, deficit)
                else:
                    recommendation = "standby"
                    hw_mode = "input"
                    in_w = 0.0

            # WINTER = price shaving; if no price -> fallback to summer logic
            elif self.operation_mode == MODE_WINTER:
                ai_status = "winter"
                if price_now is None:
                    debug = "PRICE_MISSING_FALLBACK_SUMMER"
                    # fallback like summer
                    if surplus >= surplus_thr and soc < soc_max:
                        recommendation = "pv_ueberschuss_laden"
                        hw_mode = "input"
                        in_w = min(max_charge, surplus)
                    elif deficit > 80 and soc > soc_min:
                        recommendation = "autarkie_entladen"
                        hw_mode = "output"
                        out_w = min(max_discharge, deficit)
                    else:
                        recommendation = "standby"
                        hw_mode = "input"
                        in_w = 0.0
                else:
                    # very expensive always discharge (if possible)
                    if price_now >= very_expensive_thr and soc > soc_min:
                        recommendation = "sehr_teuer_entladen"
                        hw_mode = "output"
                        out_w = min(max_discharge, deficit)
                    elif price_now >= effective_expensive and soc > soc_min:
                        recommendation = "teuer_entladen"
                        hw_mode = "output"
                        out_w = min(max_discharge, deficit)
                    elif surplus >= surplus_thr and soc < soc_max:
                        recommendation = "pv_ueberschuss_laden"
                        hw_mode = "input"
                        in_w = min(max_charge, surplus)
                    else:
                        recommendation = "standby"
                        hw_mode = "input"
                        in_w = 0.0

            # AUTO = if price available -> winter-ish, else summer-ish
            else:
                self.operation_mode = MODE_AUTOMATIC
                ai_status = "automatic"
                if price_now is not None and price_now >= effective_expensive and soc > soc_min:
                    recommendation = "teuer_entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, deficit)
                elif surplus >= surplus_thr and soc < soc_max:
                    recommendation = "pv_ueberschuss_laden"
                    hw_mode = "input"
                    in_w = min(max_charge, surplus)
                elif deficit > 80 and soc > soc_min and price_now is None:
                    # no price sensor -> still allow autarky discharge
                    recommendation = "autarkie_entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, deficit)
                else:
                    recommendation = "standby"
                    hw_mode = "input"
                    in_w = 0.0

            # -------------------------
            # 3) Freeze ONLY text (optional)
            # -------------------------
            if self._freeze_until and now_utc < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now_utc + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            # -------------------------
            # 4) Apply hardware
            # -------------------------
            await self._apply_hw(hw_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": debug,
                "details": {
                    "mode": self.operation_mode,
                    "price_now": price_now,
                    "expensive_threshold_fixed": expensive_thr,
                    "expensive_threshold_dynamic": dynamic_expensive,
                    "expensive_threshold_effective": effective_expensive,
                    "very_expensive_threshold": very_expensive_thr,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "deficit": deficit,
                    "set_mode": hw_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
