from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    # config keys
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    # settings entity ids (created by our number/select platforms)
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE,
    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE,
    # ai modes
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_ACTION_STANDBY,
    MANUAL_ACTION_CHARGE,
    MANUAL_ACTION_DISCHARGE,
)

_LOGGER = logging.getLogger(__name__)

FREEZE_SECONDS = 30  # Stabilität der Anzeige (nur Anzeige einfrieren)


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


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        data = entry.data

        self.entities = EntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],
            load=data[CONF_LOAD_ENTITY],
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit=data[CONF_INPUT_LIMIT_ENTITY],
            output_limit=data[CONF_OUTPUT_LIMIT_ENTITY],
        )

        # Freeze nur für Sensor-Ausgabe
        self._freeze_until: datetime | None = None
        self._last_ai_status: str | None = None
        self._last_recommendation: str | None = None
        self._last_debug: str | None = None

        # Hardware-Entprellung
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
    # HA State helper
    # -------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # -------------------------
    # Unsere internen Entities (Number/Select) per entity_id zusammenbauen
    # (unique_id kommt aus number/select, aber entity_id ist stabil via object_id)
    # -------------------------
    def _our_number_entity_id(self, setting_key: str) -> str:
        # object_id wird in number.py deterministisch vergeben
        return f"number.{DOMAIN}_{setting_key}"

    def _our_select_entity_id(self, object_id: str) -> str:
        return f"select.{DOMAIN}_{object_id}"

    # -------------------------
    # Preis jetzt aus Tibber Datenexport (robust via start_time)
    # attributes.data: list[{start_time, price_per_kwh}]
    # -------------------------
    def _price_now(self) -> float | None:
        if not self.entities.price_export:
            return None

        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list) or not data:
            return None

        now = dt_util.now()

        best_price: float | None = None
        best_start: datetime | None = None

        for item in data:
            if not isinstance(item, dict):
                continue
            start_raw = item.get("start_time")
            price_raw = item.get("price_per_kwh")
            if start_raw is None:
                continue

            try:
                start_dt = dt_util.parse_datetime(str(start_raw))
                if start_dt is None:
                    continue
                # in lokale TZ konvertieren
                if start_dt.tzinfo is None:
                    start_dt = dt_util.as_utc(start_dt)
                start_local = dt_util.as_local(start_dt)
            except Exception:
                continue

            if start_local <= now and (best_start is None or start_local > best_start):
                p = _to_float(price_raw, None)
                if p is None:
                    continue
                best_price = p
                best_start = start_local

        return best_price

    # -------------------------
    # Mode-Option sicher auswählen (Input/Output)
    # -------------------------
    def _pick_select_option(self, entity_id: str, desired: str) -> str:
        options = self._attr(entity_id, "options")
        if isinstance(options, list) and options:
            desired_low = desired.lower()
            # exakte match
            for opt in options:
                if str(opt).lower() == desired_low:
                    return str(opt)
            # enthält match
            for opt in options:
                if desired_low in str(opt).lower():
                    return str(opt)
        # fallback
        return desired

    # -------------------------
    # Hardware calls
    # -------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        try:
            mode_to_set = self._pick_select_option(self.entities.ac_mode, mode)
            if self._last_set_mode == mode_to_set:
                return
            await self.hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": self.entities.ac_mode, "option": mode_to_set},
                blocking=False,
            )
            self._last_set_mode = mode_to_set
        except Exception as e:
            _LOGGER.debug("set_ac_mode failed: %s", e)

    async def _set_input_limit(self, watts: float) -> None:
        try:
            w = float(round(watts, 0))
            if self._last_set_in is not None and abs(self._last_set_in - w) < 10:
                return
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self.entities.input_limit, "value": w},
                blocking=False,
            )
            self._last_set_in = w
        except Exception as e:
            _LOGGER.debug("set_input_limit failed: %s", e)

    async def _set_output_limit(self, watts: float) -> None:
        try:
            w = float(round(watts, 0))
            if self._last_set_out is not None and abs(self._last_set_out - w) < 10:
                return
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self.entities.output_limit, "value": w},
                blocking=False,
            )
            self._last_set_out = w
        except Exception as e:
            _LOGGER.debug("set_output_limit failed: %s", e)

    # -------------------------
    # Read settings
    # -------------------------
    def _read_setting(self, key: str, default: float) -> float:
        ent = self._our_number_entity_id(key)
        val = _to_float(self._state(ent), default)
        return float(val if val is not None else default)

    def _read_ai_mode(self) -> str:
        # select.zendure_smartflow_ai_ai_mode
        mode = self._state(self._our_select_entity_id("ai_mode"))
        if mode is None:
            return AI_MODE_AUTOMATIC
        s = str(mode).strip().lower()
        # wir speichern intern stable keys in select.py als state
        if s in (AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL):
            return s
        return AI_MODE_AUTOMATIC

    def _read_manual_action(self) -> str:
        act = self._state(self._our_select_entity_id("manual_action"))
        if act is None:
            return MANUAL_ACTION_STANDBY
        s = str(act).strip().lower()
        if s in (MANUAL_ACTION_STANDBY, MANUAL_ACTION_CHARGE, MANUAL_ACTION_DISCHARGE):
            return s
        return MANUAL_ACTION_STANDBY

    # -------------------------
    # Main update
    # -------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)
            load_raw = self._state(self.entities.load)

            soc = _to_float(soc_raw, None)
            pv = _to_float(pv_raw, None)
            load = _to_float(load_raw, None)

            if soc is None or pv is None or load is None:
                return {
                    "status": "online",
                    "ai_status": "sensor_invalid",
                    "recommendation": "standby",
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": soc_raw,
                        "pv_raw": pv_raw,
                        "load_raw": load_raw,
                    },
                }

            # settings
            soc_min = self._read_setting(SETTING_SOC_MIN, float(DEFAULT_SOC_MIN))
            soc_max = self._read_setting(SETTING_SOC_MAX, float(DEFAULT_SOC_MAX))
            max_charge = self._read_setting(SETTING_MAX_CHARGE, float(DEFAULT_MAX_CHARGE))
            max_discharge = self._read_setting(SETTING_MAX_DISCHARGE, float(DEFAULT_MAX_DISCHARGE))
            price_thr = self._read_setting(SETTING_PRICE_THRESHOLD, float(DEFAULT_PRICE_THRESHOLD))
            very_expensive = self._read_setting(SETTING_VERY_EXPENSIVE, float(DEFAULT_VERY_EXPENSIVE))

            # clamp sanity
            soc_min = _clamp(soc_min, 0, 100)
            soc_max = _clamp(soc_max, 0, 100)
            if soc_max < soc_min:
                soc_max = soc_min

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            # optional price
            price_now = self._price_now()

            ai_mode = self._read_ai_mode()
            manual_action = self._read_manual_action()

            # Decision
            ai_status = "standby"
            recommendation = "standby"
            debug = "OK"

            set_mode = "input"
            set_in = 0.0
            set_out = 0.0

            # -------------------------
            # MANUAL MODE (überschreibt alles)
            # -------------------------
            if ai_mode == AI_MODE_MANUAL:
                debug = "MANUAL_MODE_ACTIVE"
                if manual_action == MANUAL_ACTION_CHARGE:
                    ai_status = "manual_charge"
                    recommendation = "laden"
                    set_mode = "input"
                    # wenn kein PV-Überschuss vorhanden, trotzdem klein laden? -> nein, sonst Netzbezug
                    set_in = min(max_charge, surplus) if surplus > 50 else 0.0
                    set_out = 0.0
                elif manual_action == MANUAL_ACTION_DISCHARGE:
                    ai_status = "manual_discharge"
                    recommendation = "entladen"
                    set_mode = "output"
                    set_out = min(max_discharge, deficit) if deficit > 50 else min(max_discharge, 300.0)
                    set_in = 0.0
                else:
                    ai_status = "manual_standby"
                    recommendation = "standby"
                    set_mode = "input"
                    set_in = 0.0
                    set_out = 0.0

            # -------------------------
            # SUMMER MODE (Autarkie: Überschuss laden + bei Defizit entladen)
            # -------------------------
            elif ai_mode == AI_MODE_SUMMER:
                if surplus > 80 and soc < soc_max:
                    ai_status = "pv_ueberschuss"
                    recommendation = "laden"
                    set_mode = "input"
                    set_in = min(max_charge, surplus)
                    set_out = 0.0
                elif deficit > 80 and soc > soc_min:
                    ai_status = "autarkie_entladen"
                    recommendation = "entladen"
                    set_mode = "output"
                    set_out = min(max_discharge, deficit)
                    set_in = 0.0
                else:
                    ai_status = "standby"
                    recommendation = "standby"
                    set_mode = "input"
                    set_in = 0.0
                    set_out = 0.0

            # -------------------------
            # WINTER MODE (Preis: Peaks glätten + optional günstig laden)
            # Preisquelle optional -> wenn fehlt, nur PV-Überschuss laden
            # -------------------------
            elif ai_mode == AI_MODE_WINTER:
                if surplus > 80 and soc < soc_max:
                    ai_status = "pv_ueberschuss"
                    recommendation = "laden"
                    set_mode = "input"
                    set_in = min(max_charge, surplus)
                    set_out = 0.0

                elif price_now is not None and price_now >= price_thr and soc > soc_min and deficit > 50:
                    # entladen bei teuer
                    ai_status = "teuer"
                    recommendation = "entladen"
                    set_mode = "output"
                    set_out = min(max_discharge, deficit)
                    set_in = 0.0

                elif price_now is not None and price_now >= very_expensive and soc > soc_min:
                    # sehr teuer: aggressiver ausgleichen (auch ohne großen deficit)
                    ai_status = "sehr_teuer"
                    recommendation = "entladen"
                    set_mode = "output"
                    set_out = min(max_discharge, max(deficit, 300.0))
                    set_in = 0.0

                else:
                    ai_status = "standby"
                    recommendation = "standby"
                    set_mode = "input"
                    set_in = 0.0
                    set_out = 0.0

            # -------------------------
            # AUTOMATIC (Kombi)
            # -------------------------
            else:
                if surplus > 80 and soc < soc_max:
                    ai_status = "pv_ueberschuss"
                    recommendation = "laden"
                    set_mode = "input"
                    set_in = min(max_charge, surplus)
                    set_out = 0.0

                elif price_now is not None and price_now >= price_thr and soc > soc_min and deficit > 50:
                    ai_status = "teuer"
                    recommendation = "entladen"
                    set_mode = "output"
                    set_out = min(max_discharge, deficit)
                    set_in = 0.0

                elif deficit > 150 and soc > soc_min and price_now is None:
                    # ohne Preisquelle: moderat entladen, um Netzbezug zu reduzieren
                    ai_status = "defizit"
                    recommendation = "entladen"
                    set_mode = "output"
                    set_out = min(max_discharge, deficit)
                    set_in = 0.0

                else:
                    ai_status = "standby"
                    recommendation = "standby"
                    set_mode = "input"
                    set_in = 0.0
                    set_out = 0.0

            # -------------------------
            # Hardware anwenden (immer!)
            # -------------------------
            # Zendure Optionen sind meist "Input"/"Output" -> wir setzen "input"/"output" robust
            await self._set_ac_mode("input" if set_mode == "input" else "output")
            await self._set_input_limit(set_in)
            await self._set_output_limit(set_out)

            # -------------------------
            # Freeze nur für Anzeige (damit UI nicht flackert)
            # -------------------------
            now_utc = dt_util.utcnow()
            if self._freeze_until and now_utc < self._freeze_until:
                ai_status_out = self._last_ai_status or ai_status
                rec_out = self._last_recommendation or recommendation
                dbg_out = self._last_debug or debug
            else:
                self._freeze_until = now_utc + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation
                self._last_debug = debug
                ai_status_out = ai_status
                rec_out = recommendation
                dbg_out = debug

            return {
                "status": "online",
                "ai_mode": ai_mode,
                "manual_action": manual_action,
                "ai_status": ai_status_out,
                "recommendation": rec_out,
                "debug": dbg_out,
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "deficit": deficit,
                    "price_now": price_now,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "max_charge": max_charge,
                    "max_discharge": max_discharge,
                    "price_threshold": price_thr,
                    "very_expensive_threshold": very_expensive,
                    "set_mode": set_mode,
                    "set_input_w": round(set_in, 0),
                    "set_output_w": round(set_out, 0),
                    "price_export_entity": self.entities.price_export,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
