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

UPDATE_INTERVAL = 10        # Sekunden
FREEZE_SECONDS = 120        # Recommendation-Freeze


# ======================================================
# Entity IDs
# ======================================================
@dataclass
class EntityIds:
    # Messwerte
    soc: str
    pv: str
    load: str
    price_export: str  # Tibber Diagramm-Datenexport

    # Parameter / Regler (Integration)
    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    # Zendure SolarFlow AC
    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


# ======================================================
# Helper
# ======================================================
def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default


# ======================================================
# Coordinator
# ======================================================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        data = entry.data or {}

        def pick(*keys: str, default: str | None = None) -> str:
            for k in keys:
                v = data.get(k)
                if v:
                    return v
            return default or ""

        self.entities = EntityIds(
            soc=pick("soc_entity", default=DEFAULT_ENTITY_IDS.soc),
            pv=pick("pv_entity", default=DEFAULT_ENTITY_IDS.pv),
            load=pick("load_entity", default=DEFAULT_ENTITY_IDS.load),
            price_export=pick(
                "price_export_entity",
                "price_entity",
                "price_now_entity",
                default=DEFAULT_ENTITY_IDS.price_export,
            ),
            soc_min=pick("soc_min_entity", default=DEFAULT_ENTITY_IDS.soc_min),
            soc_max=pick("soc_max_entity", default=DEFAULT_ENTITY_IDS.soc_max),
            expensive_threshold=pick(
                "expensive_threshold_entity",
                default=DEFAULT_ENTITY_IDS.expensive_threshold,
            ),
            max_charge=pick("max_charge_entity", default=DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=pick("max_discharge_entity", default=DEFAULT_ENTITY_IDS.max_discharge),
            ac_mode=pick("ac_mode_entity", default=DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=pick("input_limit_entity", default=DEFAULT_ENTITY_IDS.input_limit),
            output_limit=pick("output_limit_entity", default=DEFAULT_ENTITY_IDS.output_limit),
        )

        # Recommendation Freeze
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
    # Helpers
    # --------------------------------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    # Preis aus Tibber-Datenexport
    # --------------------------------------------------
    def _get_price_now(self) -> float | None:
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)

        try:
            return _to_float(export[idx].get("price_per_kwh"), None)
        except Exception:
            return None

    # --------------------------------------------------
    # Hardware Calls
    # --------------------------------------------------
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
            {"entity_id": self.entities.input_limit, "value": round(watts, 0)},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(watts, 0)},
            blocking=False,
        )

    # ==================================================
    # Main Update
    # ==================================================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            soc = _to_float(self._state(self.entities.soc), 0.0)
            pv = _to_float(self._state(self.entities.pv), 0.0)
            load = _to_float(self._state(self.entities.load), 0.0)

            price_now = self._get_price_now()
            if price_now is None:
                return {
                    "ai_status": "price_invalid",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                }

            soc_min = _to_float(self._state(self.entities.soc_min), 12.0)
            soc_max = _to_float(self._state(self.entities.soc_max), 95.0)
            expensive = _to_float(self._state(self.entities.expensive_threshold), 0.35)
            max_charge = _to_float(self._state(self.entities.max_charge), 2000.0)
            max_discharge = _to_float(self._state(self.entities.max_discharge), 700.0)

            surplus = max(pv - load, 0.0)
            soc_notfall = max(soc_min - 4.0, 5.0)

            ai_status = "standby"
            recommendation = "standby"
            ac_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # 1️⃣ TEUER → ENTLADE
            if price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                ac_mode = "output"
                out_w = min(max_discharge, max(load - pv, 0.0))

            # 2️⃣ NOTFALL → LADEN (nur wenn NICHT teuer)
            elif soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                ac_mode = "input"
                in_w = min(max_charge, 300.0)

            # 3️⃣ PV-ÜBERSCHUSS
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                ac_mode = "input"
                in_w = min(max_charge, surplus)

            # Freeze (nur Anzeige!)
            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            # Hardware anwenden
            await self._set_ac_mode(ac_mode)
            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": price_now,
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "set_mode": ac_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
