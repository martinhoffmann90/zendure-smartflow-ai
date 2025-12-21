from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_FREEZE_SECONDS,
    MODE_CHANGE_MIN_SECONDS,
    LIMIT_CHANGE_TOL_W,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ExternalEntityIds:
    soc: str
    pv: str
    load: str
    price_export: str | None
    ac_mode: str
    input_limit: str
    output_limit: str


@dataclass
class Settings:
    soc_min: float = DEFAULT_SOC_MIN
    soc_max: float = DEFAULT_SOC_MAX
    max_charge: float = DEFAULT_MAX_CHARGE
    max_discharge: float = DEFAULT_MAX_DISCHARGE
    price_threshold: float = DEFAULT_PRICE_THRESHOLD
    freeze_seconds: int = DEFAULT_FREEZE_SECONDS
    ai_mode: str = MODE_AUTOMATIC


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


def _bad_state(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ("unknown", "unavailable", "")


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Zentrales Gehirn: liest Sensoren, trifft Entscheidung, steuert Hardware."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        data = entry.data

        self.ext = ExternalEntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],
            load=data[CONF_LOAD_ENTITY],
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit=data[CONF_INPUT_LIMIT_ENTITY],
            output_limit=data[CONF_OUTPUT_LIMIT_ENTITY],
        )

        # Integration-interne Settings (werden von Number/Select-Entities gepflegt)
        self.settings = Settings()

        # Anti-Flattern / Anti-Spam
        self._last_apply_ts = None
        self._last_hw_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None

        # Freeze (nur Anzeige)
        self._freeze_until_utc = None
        self._last_ai_status: str | None = None
        self._last_recommendation: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )

    # -------------------------
    # Device Info (für Gerätezuordnung)
    # -------------------------
    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
            "sw_version": self.entry.version,
        }

    # -------------------------
    # State / Attr
    # -------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # -------------------------
    # Preis aus Tibber Datenexport (15-Min Slots)
    # -------------------------
    def _price_now(self) -> float | None:
        if not self.ext.price_export:
            return None
        export = self._attr(self.ext.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(export):
            return None
        try:
            return _to_float(export[idx].get("price_per_kwh"), default=None)  # type: ignore[arg-type]
        except Exception:
            return None

    # -------------------------
    # Hardware Calls
    # -------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        # mode muss zur Zendure-Select passen: "input" oder "output"
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.ext.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.ext.input_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.ext.output_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _apply_hw(self, mode: str, in_w: float, out_w: float) -> None:
        """Nur anwenden, wenn nötig. Verhindert Flattern/Spam."""
        now = dt_util.utcnow()

        def changed(prev: float | None, new: float, tol: float) -> bool:
            if prev is None:
                return True
            return abs(prev - new) > tol

        # Mode nur alle X Sekunden, wenn er wechseln würde
        if self._last_apply_ts is None:
            allow_mode_change = True
        else:
            allow_mode_change = (now - self._last_apply_ts).total_seconds() >= MODE_CHANGE_MIN_SECONDS

        if mode != self._last_hw_mode and allow_mode_change:
            await self._set_ac_mode(mode)
            self._last_hw_mode = mode
            self._last_apply_ts = now

        # Limits: kleine Totzone
        if changed(self._last_in, in_w, LIMIT_CHANGE_TOL_W):
            await self._set_input_limit(in_w)
            self._last_in = in_w

        if changed(self._last_out, out_w, LIMIT_CHANGE_TOL_W):
            await self._set_output_limit(out_w)
            self._last_out = out_w

    # -------------------------
    # Mode Entscheidung
    # -------------------------
    def _auto_select_mode(self) -> str:
        # pragmatisch: Sommerhalbjahr = Sommer, sonst Winter
        m = dt_util.now().month
        if 4 <= m <= 9:
            return MODE_SUMMER
        return MODE_WINTER

    # ==================================================
    # Main Update
    # ==================================================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc_raw = self._state(self.ext.soc)
            pv_raw = self._state(self.ext.pv)
            load_raw = self._state(self.ext.load)

            if _bad_state(soc_raw) or _bad_state(pv_raw) or _bad_state(load_raw):
                return {
                    "ai_status": "sensor_invalid",
                    "recommendation": "standby",
                    "debug": "SENSOR_INVALID",
                    "details": {"soc_raw": soc_raw, "pv_raw": pv_raw, "load_raw": load_raw},
                }

            soc = _to_float(soc_raw, 0.0) or 0.0
            pv = _to_float(pv_raw, 0.0) or 0.0
            load = _to_float(load_raw, 0.0) or 0.0

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            # Settings
            s = self.settings
            soc_min = float(s.soc_min)
            soc_max = float(s.soc_max)
            max_charge = float(s.max_charge)
            max_discharge = float(s.max_discharge)
            price_threshold = float(s.price_threshold)
            freeze_seconds = int(s.freeze_seconds)
            ai_mode = str(s.ai_mode)

            # effektiver Modus
            effective_mode = ai_mode
            if ai_mode == MODE_AUTOMATIC:
                effective_mode = self._auto_select_mode()

            # Preis (optional)
            price_now = self._price_now()

            # -------------------------
            # Default Entscheidung
            # -------------------------
            ai_status = "standby"
            recommendation = "standby"
            hw_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # -------------------------
            # MANUAL: AI greift NICHT ein
            # -------------------------
            if ai_mode == MODE_MANUAL:
                ai_status = "manual"
                recommendation = "manual"
                # Hardware unangetastet lassen!
                return {
                    "ai_status": ai_status,
                    "recommendation": recommendation,
                    "debug": "MANUAL_MODE_ACTIVE",
                    "details": {
                        "mode": ai_mode,
                        "effective_mode": effective_mode,
                        "soc": soc,
                        "pv": pv,
                        "load": load,
                        "surplus": surplus,
                        "deficit": deficit,
                        "price_now": price_now,
                    },
                }

            # -------------------------
            # Schutz: Notfallgrenze
            # -------------------------
            soc_notfall = max(soc_min - 4.0, 5.0)

            # -------------------------
            # SOMMER: Autarkie erhöhen
            # - PV Überschuss laden
            # - Abends/Nachts dynamisch entladen nach Bedarf
            # -------------------------
            if effective_mode == MODE_SUMMER:
                hour = dt_util.now().hour
                evening_night = (hour >= 17) or (hour < 7)

                if soc <= soc_notfall:
                    ai_status = "notladung"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, 300.0)
                    out_w = 0.0

                elif surplus > 120.0 and soc < soc_max:
                    ai_status = "pv_ueberschuss"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, surplus)
                    out_w = 0.0

                elif evening_night and deficit > 120.0 and soc > soc_min:
                    ai_status = "abend_entladen"
                    recommendation = "entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, deficit)
                    in_w = 0.0

                else:
                    ai_status = "standby"
                    recommendation = "standby"
                    hw_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

            # -------------------------
            # WINTER: Preis / Peak-Shaving
            # - Bei teuer entladen (wenn möglich)
            # - PV Überschuss trotzdem laden
            # -------------------------
            elif effective_mode == MODE_WINTER:
                if soc <= soc_notfall:
                    ai_status = "notladung"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, 300.0)
                    out_w = 0.0

                elif price_now is not None and price_now >= price_threshold and soc > soc_min and deficit > 50.0:
                    ai_status = "teuer_jetzt"
                    recommendation = "entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, deficit)
                    in_w = 0.0

                elif surplus > 120.0 and soc < soc_max:
                    ai_status = "pv_ueberschuss"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, surplus)
                    out_w = 0.0

                else:
                    ai_status = "standby"
                    recommendation = "standby"
                    hw_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

            # -------------------------
            # Fallback
            # -------------------------
            else:
                ai_status = "standby"
                recommendation = "standby"

            # -------------------------
            # Freeze (nur Anzeige, nicht Hardware!)
            # -------------------------
            now_utc = dt_util.utcnow()
            if freeze_seconds > 0:
                if self._freeze_until_utc and now_utc < self._freeze_until_utc:
                    ai_status = self._last_ai_status or ai_status
                    recommendation = self._last_recommendation or recommendation
                else:
                    self._freeze_until_utc = now_utc + timedelta(seconds=freeze_seconds)
                    self._last_ai_status = ai_status
                    self._last_recommendation = recommendation

            # -------------------------
            # Hardware anwenden
            # -------------------------
            await self._apply_hw(hw_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "mode": ai_mode,
                    "effective_mode": effective_mode,
                    "soc": round(soc, 2),
                    "soc_min": round(soc_min, 2),
                    "soc_max": round(soc_max, 2),
                    "soc_notfall": round(soc_notfall, 2),
                    "pv": round(pv, 1),
                    "load": round(load, 1),
                    "surplus": round(surplus, 1),
                    "deficit": round(deficit, 1),
                    "price_now": price_now,
                    "price_threshold": round(price_threshold, 4),
                    "set_mode": hw_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                    "freeze_seconds": freeze_seconds,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
