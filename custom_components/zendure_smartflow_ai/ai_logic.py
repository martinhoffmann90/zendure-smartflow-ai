from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .const import (
    AI_STATUS_NO_DATA,
    AI_STATUS_EXPENSIVE_NOW_PROTECT,
    AI_STATUS_EXPENSIVE_NOW_DISCHARGE,
    AI_STATUS_CHARGE_FOR_PEAK,
    AI_STATUS_WAIT_FOR_CHEAPEST,
    AI_STATUS_IDLE,
    RECOMMENDATION_STANDBY,
    RECOMMENDATION_CHARGE,
    RECOMMENDATION_DISCHARGE,
    RECOMMENDATION_KI_CHARGE,
)


def calculate_ai_state(
    data: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Zentrale KI-Logik.

    Unterstützt 2 Aufrufarten:
      1) calculate_ai_state({...})                 -> data dict
      2) calculate_ai_state(prices=[...], soc=..., ...) -> kwargs

    Erwartete Felder (egal ob in data oder kwargs):
    - soc (float, %)
    - soc_min (float)
    - soc_max (float)
    - prices (list[float])  # 15-Minuten-Preise, ab JETZT
    - current_price (float)
    - expensive_threshold (float)
    - cheap_threshold (float)
    - battery_kwh (float)
    - max_charge_w (float)
    - max_discharge_w (float)

    Rückgabe:
    {
        "ai_status": <ENUM>,
        "recommendation": <ENUM>,
        "debug": str
    }
    """

    # -------------------------------------------------
    # 1) Input normalisieren: Dict + kwargs zusammenführen
    # -------------------------------------------------
    merged: Dict[str, Any] = {}
    if isinstance(data, dict):
        merged.update(data)
    merged.update(kwargs)

    # -----------------------------
    # 2) Basiswerte einlesen
    # -----------------------------
    soc: float = float(merged.get("soc", 0))
    soc_min: float = float(merged.get("soc_min", 12))
    soc_max: float = float(merged.get("soc_max", 95))

    prices = merged.get("prices", [])
    current_price: float = float(merged.get("current_price", 0))

    expensive = float(merged.get("expensive_threshold", 0.35))
    cheap = float(merged.get("cheap_threshold", 0.15))

    battery_kwh: float = float(merged.get("battery_kwh", 5.76))
    max_charge_w: float = float(merged.get("max_charge_w", 2000))
    max_discharge_w: float = float(merged.get("max_discharge_w", 700))

    _now = datetime.now()  # für spätere Erweiterungen (Zeitfenster etc.)

    # -----------------------------
    # 3) Validierung
    # -----------------------------
    if not prices:
        return {
            "ai_status": AI_STATUS_NO_DATA,
            "recommendation": RECOMMENDATION_STANDBY,
            "debug": "Keine Preisdaten vorhanden",
        }

    # sicherstellen, dass es floats sind
    try:
        prices = [float(p) for p in prices]
    except Exception:
        return {
            "ai_status": AI_STATUS_NO_DATA,
            "recommendation": RECOMMENDATION_STANDBY,
            "debug": "Preisdaten sind nicht numerisch",
        }

    # -----------------------------
    # 4) Energie-Berechnungen
    # -----------------------------
    usable_soc = max(soc - soc_min, 0)
    available_kwh = battery_kwh * usable_soc / 100.0

    charge_kw = (max_charge_w * 0.75) / 1000.0
    discharge_kw = (max_discharge_w * 0.85) / 1000.0

    # -----------------------------
    # 5) Peak-Erkennung
    # -----------------------------
    peak_slots = [p for p in prices if p >= expensive]
    peak_hours = len(peak_slots) * 0.25
    needed_kwh = peak_hours * discharge_kw
    missing_kwh = max(needed_kwh - available_kwh, 0.0)

    # ersten Peak in der Zukunft finden
    first_peak_index = None
    for i, p in enumerate(prices):
        if p >= expensive:
            first_peak_index = i
            break

    minutes_to_peak = first_peak_index * 15 if first_peak_index is not None else None
    needed_minutes = (missing_kwh / charge_kw * 60.0) if (charge_kw > 0 and missing_kwh > 0) else 0.0

    # günstigster Slot in der betrachteten Reihe
    cheapest_price = min(prices)
    cheapest_index = prices.index(cheapest_price)
    cheapest_in_future = cheapest_index > 0

    # -----------------------------
    # 6) Entscheidungslogik
    # -----------------------------

    # A) Aktuell teuer
    if current_price >= expensive:
        if soc <= soc_min:
            return {
                "ai_status": AI_STATUS_EXPENSIVE_NOW_PROTECT,
                "recommendation": RECOMMENDATION_STANDBY,
                "debug": "Teurer Preis, Akku unter Reserve → Schutz",
            }
        return {
            "ai_status": AI_STATUS_EXPENSIVE_NOW_DISCHARGE,
            "recommendation": RECOMMENDATION_DISCHARGE,
            "debug": "Teurer Preis, Akku ausreichend → Entladen empfohlen",
        }

    # B) Peak kommt & Energie fehlt → laden muss rechtzeitig passieren
    if (
        first_peak_index is not None
        and missing_kwh > 0
        and minutes_to_peak is not None
        and minutes_to_peak <= needed_minutes + 30  # safety 30 min
        and soc < soc_max
    ):
        return {
            "ai_status": AI_STATUS_CHARGE_FOR_PEAK,
            "recommendation": RECOMMENDATION_KI_CHARGE,
            "debug": (
                f"Peak in {minutes_to_peak} min, fehlend {missing_kwh:.2f} kWh "
                f"(Ladezeit ~{needed_minutes:.0f} min) → Laden erforderlich"
            ),
        }

    # C) Günstigste Phase kommt noch → warten (nicht jetzt laden)
    if cheapest_in_future and soc < soc_max:
        return {
            "ai_status": AI_STATUS_WAIT_FOR_CHEAPEST,
            "recommendation": RECOMMENDATION_STANDBY,
            "debug": f"Günstigster Preis ({cheapest_price:.3f} €/kWh) in {cheapest_index * 15} min",
        }

    # D) Standard
    return {
        "ai_status": AI_STATUS_IDLE,
        "recommendation": RECOMMENDATION_STANDBY,
        "debug": "Keine besondere Aktion erforderlich",
    }
