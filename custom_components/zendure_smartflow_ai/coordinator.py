from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.hass = hass
        self.entry = entry

        # 🔋 Energie-Tracking
        self.energy_buffer_wh: float = 0.0
        self.energy_cost_eur: float = 0.0

        # Runtime-Zustände
        self.runtime_mode: dict[str, Any] = {}

    # --------------------------------------------------
    def _get_price(self) -> float:
        """Aktueller Strompreis €/kWh oder 0.0 bei PV"""
        price = self.data.get("details", {}).get("price_now")
        try:
            return float(price)
        except Exception:
            return 0.0

    # --------------------------------------------------
    def _register_charge(self, power_w: float, seconds: int):
        if power_w <= 0:
            return

        added_wh = power_w * seconds / 3600
        price = self._get_price()

        self.energy_buffer_wh += added_wh
        self.energy_cost_eur += (added_wh / 1000) * price

    # --------------------------------------------------
    def _register_discharge(self, power_w: float, seconds: int):
        if power_w <= 0 or self.energy_buffer_wh <= 0:
            return

        removed_wh = power_w * seconds / 3600
        removed_wh = min(removed_wh, self.energy_buffer_wh)

        ratio = removed_wh / self.energy_buffer_wh

        self.energy_buffer_wh -= removed_wh
        self.energy_cost_eur -= self.energy_cost_eur * ratio

    # --------------------------------------------------
    def _avg_charge_price(self) -> float | None:
        if self.energy_buffer_wh <= 0:
            return None
        return self.energy_cost_eur / (self.energy_buffer_wh / 1000)

    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # ⚠️ Platzhalter – echte Lade/Entladeleistung
            # wird in Schritt B angebunden
            charge_power = 0.0
            discharge_power = 0.0

            interval = UPDATE_INTERVAL

            self._register_charge(charge_power, interval)
            self._register_discharge(discharge_power, interval)

            return {
                "status": "ok",
                "details": {
                    "avg_charge_price": self._avg_charge_price(),
                    "energy_buffer_wh": round(self.energy_buffer_wh, 1),
                    "energy_cost_eur": round(self.energy_cost_eur, 4),
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
