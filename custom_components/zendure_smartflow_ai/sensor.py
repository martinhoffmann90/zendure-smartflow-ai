from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfEnergy

from .const import DOMAIN, DEFAULTS


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([ZendureSmartFlowAISensor(hass)], True)


class ZendureSmartFlowAISensor(SensorEntity):
    _attr_name = "Zendure SmartFlow AI – KI Ladeplan"
    _attr_icon = "mdi:brain"
    _attr_has_entity_name = True

    def __init__(self, hass):
        self.hass = hass
        self._attr_unique_id = "zendure_smartflow_ai_ki_ladeplan"

    async def async_update(self):
        hass = self.hass

        # =========================
        # 1) BASISWERTE
        # =========================
        def f(entity, default=0):
            try:
                return float(hass.states.get(entity).state)
            except Exception:
                return default

        soc = f("sensor.solarflow_2400_ac_electric_level")
        soc_min = f("input_number.zendure_soc_reserve_min", 12)
        soc_max = f("input_number.zendure_soc_ziel_max", 95)

        max_charge_w = f("input_number.zendure_max_ladeleistung", 2000)
        max_discharge_w = f("input_number.zendure_max_entladeleistung", 700)

        fixed_teuer = f("input_number.zendure_schwelle_teuer", 0.35)
        fixed_extrem = f("input_number.zendure_schwelle_extrem", 0.49)

        export = hass.states.get(
            "sensor.paul_schneider_strasse_39_diagramm_datenexport"
        )

        raw = export.attributes.get("data") if export else None

        if not raw or len(raw) < 4:
            self._attr_native_value = "datenproblem_preisquelle"
            return

        # =========================
        # 2) AKKU
        # =========================
        battery_kwh = DEFAULTS["battery_kwh"]

        soc_clamped = min(max(soc, 0), 100)
        usable_soc = max(soc_clamped - soc_min, 0)
        usable_kwh = battery_kwh * usable_soc / 100

        # =========================
        # 3) PREISE
        # =========================
        prices = [float(p["price_per_kwh"]) for p in raw]
        prices = prices[: DEFAULTS["horizon_slots"]]

        current_price = prices[0]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        span = max_price - min_price

        # =========================
        # 4) DYNAMISCHE SCHWELLEN
        # =========================
        expensive = max(fixed_teuer, avg_price + span * 0.25)
        very_expensive = max(fixed_extrem, avg_price + span * 0.55)

        # =========================
        # 5) PEAK-BLÖCKE
        # =========================
        blocks = []
        current = None

        for i, price in enumerate(prices):
            if price >= expensive:
                if current is None:
                    current = {"start": i, "len": 1}
                else:
                    current["len"] += 1
            else:
                if current:
                    blocks.append(current)
                    current = None

        if current:
            blocks.append(current)

        interesting = [
            b for b in blocks
            if b["len"] * 0.25 >= DEFAULTS["min_peak_duration_h"]
        ]

        if not interesting:
            self._attr_native_value = "keine_peaks"
            return

        # =========================
        # 6) PEAK BEWERTUNG
        # =========================
        for b in interesting:
            slice_ = prices[b["start"]: b["start"] + b["len"]]
            b["duration_h"] = b["len"] * 0.25
            b["max"] = max(slice_)
            b["avg"] = sum(slice_) / len(slice_)
            b["score"] = (
                (b["max"] - avg_price) / (span + 0.0001)
                + b["duration_h"] / 24
            )

        best = interesting[0]
        for b in interesting:
            if b["max"] >= very_expensive and best["max"] < very_expensive:
                best = b
            elif b["score"] > best["score"]:
                best = b

        # =========================
        # 7) ENERGIEBEDARF
        # =========================
        discharge_kw = (
            max_discharge_w * DEFAULTS["discharge_efficiency"] / 1000
        )
        total_peak_hours = sum(b["duration_h"] for b in interesting)
        needed_kwh = total_peak_hours * discharge_kw
        missing_kwh = max(needed_kwh - usable_kwh, 0)

        charge_kw = (
            max_charge_w * DEFAULTS["charge_efficiency"] / 1000
        )
        need_minutes = (
            missing_kwh / charge_kw * 60
            if missing_kwh > 0 and charge_kw > 0
            else 0
        )

        minutes_to_peak = best["start"] * 15

        # =========================
        # 8) STATUSLOGIK (DE)
        # =========================
        if current_price >= expensive:
            if soc <= soc_min:
                state = "teuer_jetzt_akkuschutz"
            else:
                state = "teuer_jetzt_entladen_empfohlen"

        elif missing_kwh <= 0:
            state = "ausreichend_geladen"

        else:
            cheapest_idx = prices.index(min_price)
            if cheapest_idx > 0:
                state = "günstige_phase_kommt_noch"
            else:
                state = "laden_notwendig_für_peak"

        self._attr_native_value = state

        # =========================
        # 9) ATTRIBUTE (DEBUG/UI)
        # =========================
        self._attr_extra_state_attributes = {
            "soc": round(soc, 1),
            "usable_kwh": round(usable_kwh, 2),
            "missing_kwh": round(missing_kwh, 2),
            "expensive_threshold": round(expensive, 3),
            "best_peak_hours": round(best["duration_h"], 2),
            "minutes_to_peak": minutes_to_peak,
        }
