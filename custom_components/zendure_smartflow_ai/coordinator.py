from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    UPDATE_INTERVAL,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_FREEZE_SECONDS,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    AI_MODE_OFF,
    MANUAL_ACTION_STANDBY,
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
        s = str(val).strip().replace(",", ".")
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    V0.7.0:
    - helper-frei
    - Preis optional
    - AI Modes: summer/winter/manual/off
    - Manuelle Aktion: standby/charge/discharge (wir greifen NUR ein, wenn AI Mode != manual/off)
    - Hardwaresteuerung: ac_mode + input_limit + output_limit
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

        # runtime (set by select/number entities in this integration)
        self.ai_mode: str = AI_MODE_WINTER
        self.manual_action: str = MANUAL_ACTION_STANDBY

        self.soc_min: float = DEFAULT_SOC_MIN
        self.soc_max: float = DEFAULT_SOC_MAX
        self.max_charge: float = DEFAULT_MAX_CHARGE
        self.max_discharge: float = DEFAULT_MAX_DISCHARGE
        self.expensive_threshold: float = DEFAULT_EXPENSIVE_THRESHOLD
        self.very_expensive_threshold: float = DEFAULT_VERY_EXPENSIVE_THRESHOLD
        self.freeze_seconds: int = DEFAULT_FREEZE_SECONDS

        # freeze for status/recommendation only
        self._freeze_until: datetime | None = None
        self._last_status: str | None = None
        self._last_reco: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -------------------------
    # State / Attr helpers
    # -------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # -------------------------
    # Price handling (optional)
    # expects sensor.attributes["data"] = list of dicts with "price_per_kwh" and "start_time"
    # -------------------------
    def _price_now(self) -> float | None:
        if not self.entities.price_export:
            return None
        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list) or not data:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(data):
            return None
        item = data[idx]
        if not isinstance(item, dict):
            return None
        return _to_float(item.get("price_per_kwh"), default=None)

    def _prices_future(self) -> list[float]:
        """Return prices from now forward (15min resolution). Empty if not available."""
        if not self.entities.price_export:
            return []
        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list) or not data:
            return []

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        out: list[float] = []
        for item in data[idx:]:
            if isinstance(item, dict):
                p = _to_float(item.get("price_per_kwh"), default=None)
                if p is not None:
                    out.append(p)
        return out

    # -------------------------
    # Hardware calls
    # -------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": int(round(max(watts, 0.0), 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": int(round(max(watts, 0.0), 0))},
            blocking=False,
        )

    # -------------------------
    # Core decision logic
    # -------------------------
    def _decide(
        self,
        soc: float,
        pv: float,
        load: float,
        price_now: float | None,
        prices_future: list[float],
    ) -> tuple[str, str, str, float, float]:
        """
        returns: (ai_status, recommendation, ac_mode, in_w, out_w)
        """
        surplus = max(pv - load, 0.0)
        deficit = max(load - pv, 0.0)

        # defaults
        ai_status = "standby"
        recommendation = "standby"
        ac_mode = "input"
        in_w = 0.0
        out_w = 0.0

        # OFF: never touch hardware
        if self.ai_mode == AI_MODE_OFF:
            return ("off", "standby", "input", 0.0, 0.0)

        # MANUAL: never override user (no hardware writes)
        if self.ai_mode == AI_MODE_MANUAL:
            # still provide info/reco
            return ("manual", self.manual_action, "input", 0.0, 0.0)

        # safety bounds
        soc_min = float(self.soc_min)
        soc_max = float(self.soc_max)
        soc_notfall = max(soc_min - 4.0, 5.0)

        # clamps
        max_charge = max(0.0, float(self.max_charge))
        max_discharge = max(0.0, float(self.max_discharge))

        expensive = float(self.expensive_threshold)
        very_expensive = float(self.very_expensive_threshold)

        # -------------------------
        # SUMMER: Autarkie / PV-first
        # -------------------------
        if self.ai_mode == AI_MODE_SUMMER:
            # 1) PV Überschuss -> laden
            if surplus > 80.0 and soc < soc_max:
                ai_status = "pv_surplus"
                recommendation = "charge"
                ac_mode = "input"
                in_w = min(max_charge, surplus)
                out_w = 0.0
                return (ai_status, recommendation, ac_mode, in_w, out_w)

            # 2) Defizit -> entladen (Autarkie), aber nur wenn SoC über Minimum
            if deficit > 80.0 and soc > soc_min:
                ai_status = "autarky_discharge"
                recommendation = "discharge"
                ac_mode = "output"
                out_w = min(max_discharge, deficit)
                in_w = 0.0
                return (ai_status, recommendation, ac_mode, in_w, out_w)

            return ("standby", "standby", "input", 0.0, 0.0)

        # -------------------------
        # WINTER: Preis / Peak-Shaving
        # price optional: if missing -> fallback to autarky-like behavior (but weaker)
        # -------------------------
        if self.ai_mode == AI_MODE_WINTER:
            # if price missing -> behave like mild summer (autarky only)
            if price_now is None:
                if surplus > 80.0 and soc < soc_max:
                    return ("pv_surplus_no_price", "charge", "input", min(max_charge, surplus), 0.0)
                if deficit > 80.0 and soc > soc_min:
                    return ("deficit_no_price", "discharge", "output", 0.0, min(max_discharge, deficit))
                return ("standby_no_price", "standby", "input", 0.0, 0.0)

            # 0) Notfall -> laden (aber nur wenn nicht gerade sehr teuer – bei sehr teuer lieber trotzdem entladen vermeiden?)
            # Notfall heißt: SoC unter (soc_min - 4) -> mindestens mit kleiner Leistung nachladen.
            if soc <= soc_notfall and price_now < expensive:
                return ("emergency_charge", "charge", "input", min(max_charge, 300.0), 0.0)

            # 1) VERY EXPENSIVE -> entladen aggressiv, solange SoC > soc_min
            if price_now >= very_expensive and soc > soc_min:
                return ("very_expensive", "discharge", "output", 0.0, min(max_discharge, deficit))

            # 2) EXPENSIVE -> entladen, solange SoC > soc_min
            if price_now >= expensive and soc > soc_min:
                return ("expensive", "discharge", "output", 0.0, min(max_discharge, deficit))

            # 3) PV Überschuss -> laden (immer sinnvoll)
            if surplus > 80.0 and soc < soc_max:
                return ("pv_surplus", "charge", "input", min(max_charge, surplus), 0.0)

            # 4) Günstiges Fenster erkennen (simple Planung): wenn price_now in den unteren 15% der nächsten 12h
            # -> optional grid charge (sehr konservativ), nur wenn SoC deutlich unter soc_max
            future = prices_future[:48]  # ~12h
            if future and soc < (soc_max - 5.0):
                sorted_future = sorted(future)
                p15 = sorted_future[max(0, int(len(sorted_future) * 0.15) - 1)]
                if price_now <= p15:
                    # konservatives Netzladen
                    return ("cheap_window", "charge", "input", min(max_charge, 300.0), 0.0)

            return ("standby", "standby", "input", 0.0, 0.0)

        # fallback
        return ("standby", "standby", "input", 0.0, 0.0)

    # -------------------------
    # Main update
    # -------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now_utc = dt_util.utcnow()

            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)
            load_raw = self._state(self.entities.load)

            soc = _to_float(soc_raw, default=None)
            pv = _to_float(pv_raw, default=None)
            load = _to_float(load_raw, default=None)

            if soc is None or pv is None or load is None:
                return {
                    "ai_status": "sensor_invalid",
                    "recommendation": "standby",
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": soc_raw,
                        "pv_raw": pv_raw,
                        "load_raw": load_raw,
                    },
                }

            price_now = self._price_now()
            prices_future = self._prices_future()

            ai_status, recommendation, ac_mode, in_w, out_w = self._decide(
                soc=soc,
                pv=pv,
                load=load,
                price_now=price_now,
                prices_future=prices_future,
            )

            # freeze only for ai_status/recommendation (never freeze hardware)
            freeze = int(max(0, self.freeze_seconds))
            if freeze > 0:
                if self._freeze_until and now_utc < self._freeze_until:
                    ai_status = self._last_status or ai_status
                    recommendation = self._last_reco or recommendation
                else:
                    self._freeze_until = now_utc + timedelta(seconds=freeze)
                    self._last_status = ai_status
                    self._last_reco = recommendation

            # Apply hardware ONLY if not manual/off
            if self.ai_mode not in (AI_MODE_MANUAL, AI_MODE_OFF):
                await self._set_ac_mode(ac_mode)
                await self._set_input_limit(in_w)
                await self._set_output_limit(out_w)

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "ai_mode": self.ai_mode,
                    "manual_action": self.manual_action,
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "deficit": deficit,
                    "price_now": price_now,
                    "threshold_expensive": self.expensive_threshold,
                    "threshold_very_expensive": self.very_expensive_threshold,
                    "soc_min": self.soc_min,
                    "soc_max": self.soc_max,
                    "max_charge": self.max_charge,
                    "max_discharge": self.max_discharge,
                    "set_mode": ac_mode if self.ai_mode not in (AI_MODE_MANUAL, AI_MODE_OFF) else None,
                    "set_input_w": int(round(in_w, 0)) if self.ai_mode not in (AI_MODE_MANUAL, AI_MODE_OFF) else None,
                    "set_output_w": int(round(out_w, 0)) if self.ai_mode not in (AI_MODE_MANUAL, AI_MODE_OFF) else None,
                    "price_source": self.entities.price_export,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
