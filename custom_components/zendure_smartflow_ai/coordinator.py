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


# =========================
# Helper
# =========================
def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None or state in ("unknown", "unavailable"):
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


# =========================
# Coordinator
# =========================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        # --- Config aus Flow ---
        data = entry.data

        self.soc_entity = data["soc_entity"]
        self.pv_entity = data["pv_entity"]
        self.load_entity = data["load_entity"]
        self.price_now_entity = data["price_now_entity"]

        self.grid_mode = data.get("grid_mode", "single_sensor")
        self.grid_power_entity = data.get("grid_power_entity")
        self.grid_import_entity = data.get("grid_import_entity")
        self.grid_export_entity = data.get("grid_export_entity")

        self.ac_mode_entity = data["ac_mode_entity"]
        self.input_limit_entity = data["input_limit_entity"]
        self.output_limit_entity = data["output_limit_entity"]

        # Freeze
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
    # State helper
    # -------------------------
    def _state(self, entity_id: str | None) -> str | None:
        if not entity_id:
            return None
        s = self.hass.states.get(entity_id)
        return None if s is None else s.state

    # =========================
    # Netz-Logik (KERN von Schritt 2)
    # =========================
    def _calc_grid(self) -> tuple[float, float]:
        """
        Liefert immer:
        - grid_import_w ≥ 0
        - grid_export_w ≥ 0
        """
        # --- Variante 1: EIN Sensor ± ---
        if self.grid_mode == "single_sensor" and self.grid_power_entity:
            v = _f(self._state(self.grid_power_entity))
            if v >= 0:
                return v, 0.0
            return 0.0, abs(v)

        # --- Variante 2: GETRENNT ---
        if self.grid_mode == "split_sensors":
            imp = _f(self._state(self.grid_import_entity))
            exp = _f(self._state(self.grid_export_entity))
            return max(imp, 0.0), max(exp, 0.0)

        # --- Fallback ---
        load = _f(self._state(self.load_entity))
        pv = _f(self._state(self.pv_entity))
        net = load - pv
        return max(net, 0.0), max(-net, 0.0)

    # =========================
    # Update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # --- Basis ---
            soc = _f(self._state(self.soc_entity))
            pv = _f(self._state(self.pv_entity))
            load = _f(self._state(self.load_entity))
            price_now = _f(self._state(self.price_now_entity))

            grid_import, grid_export = self._calc_grid()

            # =========================
            # (LOGIK kommt in Schritt 3)
            # =========================
            ai_status = "standby"
            recommendation = "standby"

            # Freeze nur vorbereiten
            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "price_now": price_now,
                    "grid_import_w": round(grid_import, 1),
                    "grid_export_w": round(grid_export, 1),
                    "grid_mode": self.grid_mode,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
