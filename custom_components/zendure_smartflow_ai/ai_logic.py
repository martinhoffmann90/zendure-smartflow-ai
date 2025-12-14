from __future__ import annotations

from typing import Any

from .constants import MODE_AUTOMATIC, MODE_MANUAL, MODE_SUMMER, MODE_WINTER


def calculate_ai_state(
    *,
    soc: float,
    soc_min: float,
    soc_max: float,
    pv: float,
    load: float,
    price_now: float,
    future_prices: list[float],
    expensive_threshold_fixed: float,
    mode: str,
) -> dict[str, Any]:
    """
    Liefert:
      - ai_status: kurzer Status-Key (für Übersetzungen)
      - recommendation: 'standby' | 'laden' | 'billig_laden' | 'ki_laden' | 'entladen'
      - debug: sehr kurzer State (max 255 wird in sensor.py begrenzt)
      - details: dict mit Zahlen/Infos (als Attribute)
    """

    # Clamp
    soc = max(0.0, min(100.0, soc))
    soc_min = max(0.0, min(100.0, soc_min))
    soc_max = max(0.0, min(100.0, soc_max))

    soc_notfall = max(soc_min - 4.0, 5.0)
    surplus = max(pv - load, 0.0)

    # Preisstatistik
    future = future_prices or []
    if future:
        minp = min(future)
        maxp = max(future)
        avg = sum(future) / len(future)
        span = maxp - minp
        dynamic_expensive = avg + span * 0.25
        expensive = max(expensive_threshold_fixed, dynamic_expensive)
    else:
        minp = price_now
        maxp = price_now
        avg = price_now
        dynamic_expensive = expensive_threshold_fixed
        expensive = expensive_threshold_fixed

    # Peak start (erste teure Phase)
    peak_start = None
    for i, p in enumerate(future):
        if p >= expensive:
            peak_start = i
            break

    # Günstigster Slot VOR Peak (oder allgemein, wenn kein Peak)
    cheapest_idx = None
    cheapest_price = None
    if future:
        if peak_start is None or peak_start <= 0:
            cheapest_price = min(future)
            cheapest_idx = future.index(cheapest_price)
        else:
            window = future[:peak_start]
            if window:
                cheapest_price = min(window)
                cheapest_idx = window.index(cheapest_price)

    in_cheapest_slot = (cheapest_idx == 0) if cheapest_idx is not None else False

    # ===== Modus-Handling (Option A: nur Empfehlung, keine Steuerung) =====
    if mode == MODE_MANUAL:
        ai_status = "mode_manual"
        recommendation = "standby"
    else:
        # Kernlogik: teuer jetzt -> entladen (wenn möglich), sonst schützen
        if price_now >= expensive:
            if soc <= soc_min:
                ai_status = "expensive_now_protect"
                recommendation = "standby"
            else:
                ai_status = "expensive_now_discharge"
                recommendation = "entladen"

        # Notfall
        elif soc <= soc_notfall and soc < soc_max:
            ai_status = "emergency_charge"
            recommendation = "billig_laden"

        # günstigster Slot (vor Peak oder allgemein) -> laden
        elif in_cheapest_slot and soc < soc_max:
            ai_status = "cheapest_now_charge"
            recommendation = "ki_laden"

        # PV Überschuss -> laden
        elif surplus > 80 and soc < soc_max:
            ai_status = "pv_surplus_charge"
            recommendation = "laden"

        else:
            ai_status = "standby"
            recommendation = "standby"

        # Sommer/Winter Feinheit (nur Empfehlung)
        if mode == MODE_SUMMER and recommendation in ("billig_laden", "ki_laden"):
            # im Sommer keine Netz-Ladeorgien
            ai_status = "mode_summer_standby"
            recommendation = "standby"

        if mode == MODE_WINTER:
            # Winter lässt Netzladen eher zu -> keine Änderung nötig (Info-Key optional)
            pass

    details = {
        "soc": round(soc, 2),
        "soc_min": round(soc_min, 2),
        "soc_max": round(soc_max, 2),
        "soc_notfall": round(soc_notfall, 2),
        "pv": round(pv, 1),
        "load": round(load, 1),
        "surplus": round(surplus, 1),
        "price_now": round(price_now, 4),
        "min_price_future": round(minp, 4),
        "max_price_future": round(maxp, 4),
        "avg_price_future": round(avg, 4),
        "expensive_threshold_fixed": round(expensive_threshold_fixed, 4),
        "expensive_threshold_dynamic": round(dynamic_expensive, 4),
        "expensive_threshold_effective": round(expensive, 4),
        "future_len": len(future),
        "peak_start_idx": peak_start,
        "cheapest_idx": cheapest_idx,
        "cheapest_price": cheapest_price,
        "in_cheapest_slot": in_cheapest_slot,
        "mode": mode,
    }

    return {
        "ai_status": ai_status,
        "recommendation": recommendation,
        "debug": "OK",
        "details": details,
        "price_now": price_now,
        "expensive_threshold": expensive,
    }
