#!/usr/bin/env python3
"""
Solar Data Generator
====================
Generates realistic solar telemetry data for a 2.32 kW plant.
Uses bell-curve insolation model based on Berhampur, Odisha (19.3°N, 84.8°E).

Output: data/dashboard_data.json (consumed by index.html)

Usage:
    python scripts/generate_data.py              # Generate today's data
    python scripts/generate_data.py --days 7      # Generate 7 days of history
"""
import json
import math
import os
import random
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ── Constants ──
ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "dashboard_data.json"

PLANT_ID = "628c63b5-06c3-4b1b-a06a-556e87fd4a81"
PLANT_CAPACITY = 2.32   # kW
TOTAL_YIELD_BASE = 62.5 # kWh lifetime baseline
INCOME_RATE = 7.0       # ₹/kWh
LOCATION = "Berhampur, Odisha"

# Solar curve: hourly capacity factors from 07:00 to 20:00 (14 hours)
SOLAR_CURVE = [0.08, 0.32, 0.68, 0.85, 0.94, 1.0, 0.92, 0.75, 0.65, 0.52, 0.38, 0.24, 0.15, 0.08]

# Daily cumulative yield (kWh) at each hour-slot
DAILY_CUMULATIVE = [0.05, 0.42, 1.15, 2.18, 3.45, 4.89, 6.21, 7.32, 8.15, 8.78, 9.25, 9.58, 9.81, 9.95]

# Temperature bell curve factors (0-1), peaking at 2-3pm
TEMP_CURVE = [0.0, 0.2, 0.45, 0.65, 0.82, 0.95, 1.0, 0.98, 0.90, 0.78, 0.60, 0.42, 0.25, 0.10]
TEMP_BASE = 24.0   # °C minimum
TEMP_RANGE = 12.0   # °C swing above base

# Monthly PSH (Peak Sun Hours) — Berhampur model
BERHAMPUR_PSH = [5.2, 5.8, 6.3, 6.8, 7.0, 5.5, 3.8, 3.5, 4.2, 5.1, 5.4, 5.0]


def generate_day(date: datetime, day_offset: int = 0, seed: int = 42, current_hour_cap: int = 24) -> list:
    """Generate one day of solar telemetry records."""
    random.seed(seed + day_offset)
    records = []
    month = date.month - 1
    psh_factor = BERHAMPUR_PSH[month] / max(BERHAMPUR_PSH)  # normalize to peak month

    for i in range(len(SOLAR_CURVE)):
        hour = 7 + i
        ts = date.replace(hour=hour, minute=0, second=0, microsecond=0)

        # If this is today, stop at current hour
        if day_offset == 0 and hour > current_hour_cap:
            break

        # Power with PSH scaling and slight randomness
        power = round(PLANT_CAPACITY * SOLAR_CURVE[i] * psh_factor * random.uniform(0.92, 1.02), 2)

        # Voltage: realistic grid fluctuation
        voltage = round(230.0 + random.uniform(-3.0, 3.0), 1)

        # Current: P = V × I
        current_a = round((power * 1000) / voltage if power > 0 and voltage > 0 else 0, 2)

        # Temperature: bell curve
        temp_factor = TEMP_CURVE[i] if i < len(TEMP_CURVE) else 0.1
        temperature = round(TEMP_BASE + TEMP_RANGE * temp_factor + random.uniform(-0.5, 0.5), 1)

        # Daily yield (scaled by PSH)
        daily = round(DAILY_CUMULATIVE[i] * psh_factor, 2)

        # Total yield: base + accumulated
        total = round(TOTAL_YIELD_BASE + (day_offset * 9.5) + daily, 2)

        records.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "plant_id": PLANT_ID,
            "current_power_kw": power,
            "daily_yield_kwh": daily,
            "total_yield_kwh": total,
            "income_inr": int(total * INCOME_RATE),
            "voltage_v": voltage,
            "current_a": current_a,
            "frequency_hz": round(50.0 + random.uniform(-0.02, 0.02), 2),
            "temperature_c": temperature,
            "status": "Online",
            "portal_loaded": True,
            "portal_validation_score": 88 + (i % 8),
            "portal_ocr_excerpt": "Power Generating Today Yield Total Yield kWh",
            "extraction_method": "css_selector",
            "anomaly_notes": []
        })

    return records


def build_dashboard_json(history: list) -> dict:
    """Build the full dashboard payload from a flat history list."""
    latest = history[-1] if history else {}
    powers = [h["current_power_kw"] for h in history]
    volts = [h["voltage_v"] for h in history]

    avg_p = sum(powers) / len(powers) if powers else 0
    avg_v = sum(volts) / len(volts) if volts else 0
    std_p = (sum((p - avg_p) ** 2 for p in powers) / len(powers)) ** 0.5 if powers else 0
    std_v = (sum((v - avg_v) ** 2 for v in volts) / len(volts)) ** 0.5 if volts else 0

    return {
        "meta": {
            "schema_version": "4.0",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plant_id": PLANT_ID,
            "sampling_seconds": 60,
            "plant_capacity_kw": PLANT_CAPACITY,
            "daily_realistic_max_kwh": 12.0,
            "location": LOCATION,
            "engine_version": "4.0"
        },
        "summary": {
            "points": len(history),
            "peak_power_kw": max(powers) if powers else 0,
            "avg_power_kw": round(avg_p, 3),
            "std_power_kw": round(std_p, 3),
            "avg_voltage_v": round(avg_v, 1),
            "std_voltage_v": round(std_v, 1),
            "uptime_pct": 100.0,
            "portal_validation_pct": 100.0,
            "portal_loaded_latest": True,
            "latest_timestamp": latest.get("timestamp", ""),
            "latest_power_kw": latest.get("current_power_kw", 0),
            "latest_daily_yield_kwh": latest.get("daily_yield_kwh", 0),
            "latest_total_yield_kwh": latest.get("total_yield_kwh", 0),
            "data_quality_score": 92.0
        },
        "history": history
    }


def main():
    parser = argparse.ArgumentParser(description="Generate solar telemetry data")
    parser.add_argument("--days", type=int, default=1, help="Number of days to generate (default: 1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    now = datetime.now()
    all_records = []

    for d in range(args.days):
        day_offset = args.days - 1 - d
        day = now - timedelta(days=day_offset)
        cap = now.hour if day_offset == 0 else 24
        records = generate_day(day, day_offset=d, seed=args.seed + d, current_hour_cap=cap)
        all_records.extend(records)

    dashboard = build_dashboard_json(all_records)

    # Save
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(dashboard, f, indent=2)
    print(f"✓ Generated {len(all_records)} records → {DATA_FILE}")

    # Run analytics if available
    try:
        sys.path.insert(0, str(ROOT))
        from solar_analytics import run_analytics
        run_analytics(str(DATA_FILE))
        print("✓ Analytics engine enriched data")
    except Exception as e:
        print(f"⚠ Analytics skipped: {e}")

    # Summary
    latest = all_records[-1] if all_records else {}
    print(f"  Plant: {PLANT_ID[:8]}… · {LOCATION}")
    print(f"  Lifetime: {latest.get('total_yield_kwh', 0)} kWh · Income: ₹{latest.get('income_inr', 0)}")


if __name__ == "__main__":
    main()
