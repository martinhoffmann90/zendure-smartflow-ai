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
    UPDATE_INTERVAL,
    # config
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    # runtime
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    # settings defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    # settings keys
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    # enum states
    STATUS_INIT,
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_INVALID,
    STATUS_ERROR,
    AI_STATUS_STANDBY,
    AI_STATUS_PV_CHARGE,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_PRICE_PEAK,
    AI_STATUS_MANUAL_ACTIVE,
    AI_STATUS_WAITING,
    RECOMMENDATION_STANDBY,
    RECOMMENDATION_CHARGE,
    RECOMMENDATION_DISCHARGE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    soc: str
    pv: str

    price_export: str | None
    price_now: str | None

    ac_mode: str
    input_limit: str
    output_limit: str

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None


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
    """Core logic + hardware control."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        data = entry.data or {}

        self.entities = EntityIds(
            soc=data.get(CONF_SOC_ENTITY, ""),
            pv=data.get(CONF_PV_ENTITY, ""),

            price_export=data.get(CONF_PRICE_EXPORT_ENTITY) or None,
            price_now=data.get(CONF_PRICE_NOW_ENTITY) or None,

            ac_mode=data.get(CONF_AC_MODE_ENTITY, ""),
            input_limit=data.get(CONF_INPUT_LIMIT_ENTITY, ""),
            output_limit=data.get(CONF_OUTPUT_LIMIT_ENTITY, ""),

            grid_mode=data.get(CONF_GRID_MODE, GRID_MODE_NONE),
            grid_power=data.get(CONF_GRID_POWER_ENTITY) or None,
            grid_import=data.get(CONF_GRID_IMPORT_ENTITY) or None,
            grid_export=data.get(CONF_GRID_EXPORT_ENTITY) or None,
        )

        # Runtime modes (Select entities write here)
        self.runtime_mode: dict[str, str] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        # Runtime settings (Number entities write here)
        self.runtime_settings: dict[str, float] = {
            SETTING_SOC_MIN: DEFAULT_SOC_MIN,
            SETTING_SOC_MAX: DEFAULT_SOC_MAX,
            SETTING_MAX_CHARGE: DEFAULT_MAX_CHARGE,
            SETTING_MAX_DISCHARGE: DEFAULT_MAX_DISCHARGE,
            SETTING_PRICE_THRESHOLD: DEFAULT_PRICE_THRESHOLD,
            SETTING_VERY_EXPENSIVE_THRESHOLD: DEFAULT_VERY_EXPENSIVE_THRESHOLD,
        }

        # Summer heuristic: only allow summer discharge if PV surplus was seen today
        self._pv_surplus_seen_day: str | None = None
        self._pv_surplus_seen_today: bool = False

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
    def _price_from_export(self) -> float | None:
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

    def _price_now(self) -> float | None:
        # prefer direct price sensor if configured
        direct = _to_float(self._state(self.entities.price_now))
        if direct is not None:
            return direct
        return self._price_from_export()

    # --------------------------------------------------
    def _compute_grid(self) -> tuple[float | None, float | None, float | None]:
        """Returns (grid_power, grid_import, grid_export) as floats (W)."""
        mode = self.entities.grid_mode or GRID_MODE_NONE

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
            if gi is None or ge is None:
                return None, None, None
            gp = gi - ge
            return gp, gi, ge

        return None, None, None

    def _compute_house_load(self, pv: float, grid_power: float | None, grid_import: float | None, grid_export: float | None) -> float | None:
        """Compute house load (W) from PV + grid sensors."""
        mode = self.entities.grid_mode or GRID_MODE_NONE
        if mode == GRID_MODE_SINGLE and grid_power is not None:
            # load = pv + grid_power (grid_power positive import, negative export)
            return max(pv + grid_power, 0.0)

        if mode == GRID_MODE_SPLIT and grid_import is not None and grid_export is not None:
            # load = pv + import - export
            return max(pv + grid_import - grid_export, 0.0)

        return None

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
            {"entity_id": self.entities.input_limit, "value": int(round(watts, 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        if not self.entities.output_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": int(round(watts, 0))},
            blocking=False,
        )

    # --------------------------------------------------
    def _reset_daily_flags_if_needed(self) -> None:
        day = dt_util.now().date().isoformat()
        if self._pv_surplus_seen_day != day:
            self._pv_surplus_seen_day = day
            self._pv_surplus_seen_today = False

    # ==================================================
    async def _async_update_data(self) -> dict[str, Any]:
        self._reset_daily_flags_if_needed()

        try:
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)

            soc = _to_float(soc_raw)
            pv = _to_float(pv_raw)

            grid_power, grid_import, grid_export = self._compute_grid()

            if soc is None or pv is None:
                return {
                    "status": STATUS_SENSOR_INVALID,
                    "ai_status": AI_STATUS_WAITING,
                    "recommendation": RECOMMENDATION_STANDBY,
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": soc_raw,
                        "pv_raw": pv_raw,
                        "grid_mode": self.entities.grid_mode,
                        "grid_power": grid_power,
                        "grid_import": grid_import,
                        "grid_export": grid_export,
                    },
                }

            load = self._compute_house_load(pv, grid_power, grid_import, grid_export)

            # We can still operate without load, but deficit/covering won't be possible.
            deficit = None if load is None else max(load - pv, 0.0)
            surplus = None if load is None else max(pv - load, 0.0)

            # mark PV surplus seen today (for summer discharge gating)
            if surplus is not None and surplus > 200:
                self._pv_surplus_seen_today = True

            price_now = self._price_now()  # may be None (allowed!)

            # Settings
            soc_min = float(self.runtime_settings.get(SETTING_SOC_MIN, DEFAULT_SOC_MIN))
            soc_max = float(self.runtime_settings.get(SETTING_SOC_MAX, DEFAULT_SOC_MAX))
            max_charge = float(self.runtime_settings.get(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE))
            max_discharge = float(self.runtime_settings.get(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE))
            expensive = float(self.runtime_settings.get(SETTING_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD))
            very_expensive = float(self.runtime_settings.get(SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD))

            ai_mode = self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            manual_action = self.runtime_mode.get("manual_action", MANUAL_STANDBY)

            # Outputs to hardware
            set_mode = "input"
            set_in_w = 0.0
            set_out_w = 0.0

            # Sensor enums
            status = STATUS_OK
            ai_status = AI_STATUS_STANDBY
            recommendation = RECOMMENDATION_STANDBY
            debug = "OK"

            # ---------------------------
            # Manual overrides everything
            # ---------------------------
            if ai_mode == AI_MODE_MANUAL:
                ai_status = AI_STATUS_MANUAL_ACTIVE
                debug = "MANUAL_MODE_ACTIVE"

                if manual_action == MANUAL_CHARGE:
                    recommendation = RECOMMENDATION_CHARGE
                    set_mode = "input"
                    set_in_w = max_charge
                    set_out_w = 0.0

                elif manual_action == MANUAL_DISCHARGE:
                    recommendation = RECOMMENDATION_DISCHARGE
                    set_mode = "output"
                    # if we know deficit, cover it; otherwise discharge at max_discharge
                    if deficit is not None:
                        set_out_w = min(max_discharge, deficit)
                    else:
                        set_out_w = max_discharge
                    set_in_w = 0.0

                else:
                    recommendation = RECOMMENDATION_STANDBY
                    set_mode = "input"
                    set_in_w = 0.0
                    set_out_w = 0.0

            else:
                # ---------------------------
                # Automatic / Summer / Winter
                # ---------------------------

                # PV surplus charging (works without price)
                if surplus is not None and surplus > 80 and soc < soc_max:
                    ai_status = AI_STATUS_PV_CHARGE
                    recommendation = RECOMMENDATION_CHARGE
                    set_mode = "input"
                    set_in_w = min(max_charge, surplus)
                    set_out_w = 0.0
                    debug = "PV_SURPLUS_CHARGE"

                # Discharge rules (need deficit)
                if deficit is not None and deficit > 0 and soc > soc_min:
                    # VERY EXPENSIVE always discharge (if price exists)
                    if price_now is not None and price_now >= very_expensive:
                        ai_status = AI_STATUS_PRICE_PEAK
                        recommendation = RECOMMENDATION_DISCHARGE
                        set_mode = "output"
                        set_out_w = min(max_discharge, deficit)
                        set_in_w = 0.0
                        debug = "VERY_EXPENSIVE_DISCHARGE"

                    # WINTER/AUTO: expensive discharge
                    elif ai_mode in (AI_MODE_WINTER, AI_MODE_AUTOMATIC) and price_now is not None and price_now >= expensive:
                        ai_status = AI_STATUS_COVER_DEFICIT
                        recommendation = RECOMMENDATION_DISCHARGE
                        set_mode = "output"
                        set_out_w = min(max_discharge, deficit)
                        set_in_w = 0.0
                        debug = "EXPENSIVE_COVER_DEFICIT"

                    # SUMMER: discharge for autonomy, but only if PV surplus was seen today
                    elif ai_mode == AI_MODE_SUMMER and self._pv_surplus_seen_today:
                        ai_status = AI_STATUS_COVER_DEFICIT
                        recommendation = RECOMMENDATION_DISCHARGE
                        set_mode = "output"
                        set_out_w = min(max_discharge, deficit)
                        set_in_w = 0.0
                        debug = "SUMMER_AUTARKY_DISCHARGE"

            # If price missing in winter/auto, keep status OK (no error) – just no price-based actions
            if ai_mode in (AI_MODE_WINTER, AI_MODE_AUTOMATIC) and price_now is None and self.entities.price_now is None and self.entities.price_export is None:
                # no price configured at all
                pass
            elif ai_mode in (AI_MODE_WINTER, AI_MODE_AUTOMATIC) and price_now is None and (self.entities.price_now or self.entities.price_export):
                # configured but invalid right now
                status = STATUS_PRICE_INVALID
                debug = "PRICE_INVALID"

            # If no grid sensors configured -> load cannot be computed
            if self.entities.grid_mode == GRID_MODE_NONE:
                # not an error, but we can't compute house load/deficit/surplus precisely
                if load is None:
                    debug = f"{debug}|NO_GRID"

            # Apply to hardware
            await self._set_ac_mode(set_mode)
            await self._set_input_limit(set_in_w)
            await self._set_output_limit(set_out_w)

            return {
                "status": status,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": debug,
                "details": {
                    "ai_mode": ai_mode,
                    "manual_action": manual_action,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "pv": pv,
                    "grid_mode": self.entities.grid_mode,
                    "grid_power": grid_power,
                    "grid_import": grid_import,
                    "grid_export": grid_export,
                    "load": load,
                    "deficit": deficit,
                    "surplus": surplus,
                    "pv_surplus_seen_today": self._pv_surplus_seen_today,
                    "price_now": price_now,
                    "expensive_threshold": expensive,
                    "very_expensive_threshold": very_expensive,
                    "max_charge": max_charge,
                    "max_discharge": max_discharge,
                    "set_mode": set_mode,
                    "set_input_w": int(round(set_in_w, 0)),
                    "set_output_w": int(round(set_out_w, 0)),
                    "entities": {
                        "soc": self.entities.soc,
                        "pv": self.entities.pv,
                        "price_export": self.entities.price_export,
                        "price_now": self.entities.price_now,
                        "ac_mode": self.entities.ac_mode,
                        "input_limit": self.entities.input_limit,
                        "output_limit": self.entities.output_limit,
                        "grid_mode": self.entities.grid_mode,
                        "grid_power": self.entities.grid_power,
                        "grid_import": self.entities.grid_import,
                        "grid_export": self.entities.grid_export,
                    },
                },
            }

        except Exception as err:
            _LOGGER.exception("Update failed")
            raise UpdateFailed(str(err)) from err
