from __future__ import annotations
from typing import List, Dict


def calculate_ai_state(
    prices: List[float],
    soc: float,
    soc_min: float,
    soc_max: float,
    battery_kwh: float,
    max_charge_w: float,
    max_discharge_w: float,
    expensive_threshold: float,
) -> Dict[str, object]:
    """
    Core AI logic.
    Returns ONLY stable keys, never localized strings.
    """

    result: Dict[str, object] = {
        "ai_status": "data_missing",
        "recommendation": "standby",
        "debug": {},
    }

    if not prices:
        return result

    # --- Basic stats ---
    current_price = prices[0]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    span = max_price - min_price

    dynamic_expensive = max(expensive_threshold, avg_price + span * 0.25)

    # --- Energy ---
    usable_soc = max(soc - soc_min, 0)
    usable_kwh = battery_kwh * usable_soc / 100.0

    # --- Peak detection ---
    peak_slots = [p for p in prices if p >= dynamic_expensive]

    # --- Cheapest slot ---
    cheapest_price = min_price
    cheapest_index = prices.index(cheapest_price)
    cheapest_future = cheapest_index > 0

    # --- Peak energy demand ---
    peak_hours = len(peak_slots) * 0.25
    discharge_kw = max_discharge_w / 1000.0
    peak_needed_kwh = peak_hours * discharge_kw
    missing_kwh = max(peak_needed_kwh - usable_kwh, 0)

    # --- Charge time ---
    charge_kw = (max_charge_w * 0.75) / 1000.0
    need_minutes = (missing_kwh / charge_kw * 60) if missing_kwh > 0 else 0
    safety_minutes = 30

    # --- Debug ---
    result["debug"] = {
        "current_price": round(current_price, 4),
        "min_price": round(min_price, 4),
        "max_price": round(max_price, 4),
        "avg_price": round(avg_price, 4),
        "dynamic_expensive": round(dynamic_expensive, 4),
        "usable_kwh": round(usable_kwh, 2),
        "missing_kwh": round(missing_kwh, 2),
        "cheapest_future": cheapest_future,
    }

    # ================== DECISION TREE ==================

    # 1) We are in expensive phase NOW
    if current_price >= dynamic_expensive:
        if soc <= soc_min:
            result["ai_status"] = "expensive_now_battery_protect"
            result["recommendation"] = "standby"
        else:
            result["ai_status"] = "expensive_now_discharge"
            result["recommendation"] = "discharge"
        return result

    # 2) Cheapest phase still coming
    if cheapest_future and soc < soc_max:
        result["ai_status"] = "cheap_phase_coming"
        result["recommendation"] = "standby"
        return result

    # 3) Cheapest phase missed
    if not cheapest_future and soc < soc_max:
        result["ai_status"] = "cheap_phase_missed"
        result["recommendation"] = "ai_charge"
        return result

    # 4) Peak coming & energy missing
    if missing_kwh > 0:
        peak_start_minutes = prices.index(peak_slots[0]) * 15
        if peak_start_minutes <= need_minutes + safety_minutes:
            result["ai_status"] = "peak_coming_need_charge"
            result["recommendation"] = "ai_charge"
            return result

    # 5) Everything fine
    result["ai_status"] = "battery_ok"
    result["recommendation"] = "standby"
    return result
