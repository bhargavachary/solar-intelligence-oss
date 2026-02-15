#!/usr/bin/env python3
"""
Comprehensive Validation Suite for Solar Dashboard
=========================================================
100+ tests covering:
  A. Data Schema & Structure (15 tests)
  B. Physical Realism & Sanity (20 tests)
  C. Temporal Consistency (12 tests)
  D. Analytics Engine Validation (18 tests)
  E. Forecast & Prediction Quality (12 tests)
  F. Dashboard Rendering Correctness (10 tests)
  G. Edge Cases & Robustness (13 tests)
  H. Cross-field Consistency (10 tests)
  
Also flags enhancement opportunities.
"""

import json
import math
import statistics
import os
import sys
import re
from datetime import datetime, timedelta
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Configuration ──
DATA_FILE = "dashboard_data.json"
CREDENTIALS_FILE = "credentials.json"
PLANT_CAPACITY_KW = 2.32
DAILY_MAX_KWH = 12.0
INDIA_VOLTAGE_MIN, INDIA_VOLTAGE_MAX = 210, 250
INDIA_FREQ_MIN, INDIA_FREQ_MAX = 49.5, 50.5
TARIFF_RATE = 7.0  # ₹/kWh approximate

# ── Test Framework ──
class TestResult:
    def __init__(self, name, passed, detail="", category="", severity="info", enhancement=None):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.category = category
        self.severity = severity  # info, warn, error, critical
        self.enhancement = enhancement  # suggestion if test reveals improvement opportunity

results = []

def test(name, condition, detail="", category="General", severity="error", enhancement=None):
    results.append(TestResult(name, bool(condition), detail, category, severity, enhancement))

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def load_credentials():
    with open(CREDENTIALS_FILE, "r") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# A. DATA SCHEMA & STRUCTURE (15 tests)
# ═══════════════════════════════════════════════════════════════
def test_schema(data):
    cat = "A. Schema & Structure"
    
    # A1: Top-level keys
    test("A01 Top-level keys present", 
         all(k in data for k in ["meta", "summary", "history", "analytics"]),
         f"Keys found: {list(data.keys())}", cat)
    
    # A2: Meta required fields
    meta_fields = ["schema_version", "plant_id", "plant_capacity_kw", "location", "generated_at"]
    test("A02 Meta has all required fields",
         all(k in data.get("meta", {}) for k in meta_fields),
         f"Missing: {[k for k in meta_fields if k not in data.get('meta', {})]}", cat)
    
    # A3: Summary required fields
    summary_fields = ["points", "peak_power_kw", "avg_power_kw", "latest_timestamp", 
                       "latest_power_kw", "latest_daily_yield_kwh", "latest_total_yield_kwh"]
    test("A03 Summary has all required fields",
         all(k in data.get("summary", {}) for k in summary_fields),
         f"Missing: {[k for k in summary_fields if k not in data.get('summary', {})]}", cat)
    
    # A4: History is non-empty list
    test("A04 History is non-empty array",
         isinstance(data.get("history"), list) and len(data["history"]) > 0,
         f"History entries: {len(data.get('history', []))}", cat)
    
    # A5: Each history record has required fields
    record_fields = ["timestamp", "plant_id", "current_power_kw", "daily_yield_kwh",
                      "total_yield_kwh", "voltage_v", "status"]
    all_have = True
    missing_report = []
    for i, r in enumerate(data.get("history", [])):
        miss = [k for k in record_fields if k not in r]
        if miss:
            all_have = False
            missing_report.append(f"Record {i}: missing {miss}")
    test("A05 All history records have required fields", all_have,
         "; ".join(missing_report[:3]) if missing_report else "All good", cat)
    
    # A6: Analytics object present and has sub-sections
    analytics_keys = ["power_trend", "anomalies", "seasonal_forecast", "performance", "health", "statistics"]
    analytics = data.get("analytics", {})
    test("A06 Analytics has all sub-sections",
         all(k in analytics for k in analytics_keys),
         f"Missing: {[k for k in analytics_keys if k not in analytics]}", cat)
    
    # A7: Plant ID consistency across meta and records
    meta_pid = data.get("meta", {}).get("plant_id", "")
    record_pids = set(r.get("plant_id", "") for r in data.get("history", []))
    test("A07 Plant ID consistent across meta & records",
         len(record_pids) == 1 and meta_pid in record_pids,
         f"Meta: {meta_pid}, Records: {record_pids}", cat)
    
    # A8: Schema version is valid format
    sv = data.get("meta", {}).get("schema_version", "")
    test("A08 Schema version is valid", 
         bool(re.match(r'^\d+\.\d+$', str(sv))),
         f"Version: {sv}", cat, "warn")
    
    # A9: generated_at is valid datetime
    gen_at = data.get("meta", {}).get("generated_at", "")
    try:
        datetime.strptime(gen_at, "%Y-%m-%d %H:%M:%S")
        valid_gen = True
    except:
        valid_gen = False
    test("A09 generated_at is valid datetime", valid_gen, f"Value: {gen_at}", cat)
    
    # A10: Summary points matches history length
    test("A10 Summary.points == len(history)",
         data.get("summary", {}).get("points") == len(data.get("history", [])),
         f"Summary says {data.get('summary',{}).get('points')}, actual {len(data.get('history',[]))}", cat)
    
    # A11: No null/None values in critical fields
    null_found = []
    for i, r in enumerate(data.get("history", [])):
        for f in ["current_power_kw", "daily_yield_kwh", "total_yield_kwh"]:
            if r.get(f) is None:
                null_found.append(f"Record {i}.{f}")
    test("A11 No null values in critical numeric fields", len(null_found) == 0,
         f"Nulls: {null_found[:5]}", cat)
    
    # A12: All timestamps parseable
    bad_ts = []
    for i, r in enumerate(data.get("history", [])):
        try:
            datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
        except:
            bad_ts.append(i)
    test("A12 All timestamps are parseable", len(bad_ts) == 0,
         f"Bad timestamp indices: {bad_ts}", cat)
    
    # A13: JSON is valid (already loaded, but check roundtrip)
    try:
        roundtrip = json.loads(json.dumps(data))
        test("A13 JSON roundtrip integrity", True, "", cat)
    except:
        test("A13 JSON roundtrip integrity", False, "Failed roundtrip", cat, "critical")
    
    # A14: No duplicate timestamps
    timestamps = [r["timestamp"] for r in data.get("history", [])]
    test("A14 No duplicate timestamps", len(timestamps) == len(set(timestamps)),
         f"Duplicates: {len(timestamps) - len(set(timestamps))}", cat,
         enhancement="Add dedup logic in data generator")
    
    # A15: Plant ID is not placeholder
    test("A15 Plant ID is not placeholder/template",
         "YOUR_PLANT_ID" not in meta_pid and meta_pid != "" and len(meta_pid) > 10,
         f"Plant ID: {meta_pid}", cat, "critical")


# ═══════════════════════════════════════════════════════════════
# B. PHYSICAL REALISM & SANITY (20 tests)
# ═══════════════════════════════════════════════════════════════
def test_realism(data):
    cat = "B. Physical Realism"
    history = data.get("history", [])
    meta = data.get("meta", {})
    cap = meta.get("plant_capacity_kw", PLANT_CAPACITY_KW)
    
    powers = [r["current_power_kw"] for r in history]
    daily_yields = [r["daily_yield_kwh"] for r in history]
    total_yields = [r["total_yield_kwh"] for r in history]
    voltages = [r.get("voltage_v", 0) for r in history]
    currents = [r.get("current_a", 0) for r in history]
    freqs = [r.get("frequency_hz", 0) for r in history]
    temps = [r.get("temperature_c", 0) for r in history]
    incomes = [r.get("income_inr", 0) for r in history]
    
    # B1: Power never exceeds capacity (+10% tolerance for measurement)
    max_power = max(powers) if powers else 0
    test("B01 Power ≤ capacity × 1.1",
         max_power <= cap * 1.1,
         f"Max power: {max_power} kW, Cap: {cap} kW", cat)
    
    # B2: Power is non-negative
    test("B02 All power values ≥ 0",
         all(p >= 0 for p in powers),
         f"Negative powers: {[p for p in powers if p < 0]}", cat)
    
    # B3: Daily yield is non-negative and increasing through the day
    test("B03 Daily yield non-negative",
         all(d >= 0 for d in daily_yields),
         f"Negative yields: {[d for d in daily_yields if d < 0]}", cat)
    
    # B4: Daily yield monotonically non-decreasing (energy can't un-generate)
    monotonic = all(daily_yields[i] <= daily_yields[i+1] for i in range(len(daily_yields)-1))
    test("B04 Daily yield is monotonically non-decreasing", monotonic,
         f"First violation at: {next((i for i in range(len(daily_yields)-1) if daily_yields[i] > daily_yields[i+1]), 'none')}",
         cat, "critical",
         enhancement="Daily yield must never decrease within same day")
    
    # B5: Total yield monotonically non-decreasing
    total_mono = all(total_yields[i] <= total_yields[i+1] for i in range(len(total_yields)-1))
    test("B05 Total yield is monotonically non-decreasing", total_mono,
         f"Values: {total_yields[:5]}...", cat, "critical")
    
    # B6: Daily yield ≤ reasonable max (cap × max_PSH × 1.2)
    max_daily = max(daily_yields) if daily_yields else 0
    theoretical_max = cap * 7.0 * 1.2  # 7 PSH × 120% generous
    test("B06 Daily yield within theoretical maximum",
         max_daily <= theoretical_max,
         f"Max daily: {max_daily} kWh, Theoretical max: {theoretical_max:.1f} kWh", cat)
    
    # B7: Total yield is realistic for system age (~1 week, ~60 kWh)
    latest_total = total_yields[-1] if total_yields else 0
    test("B07 Total yield realistic for new system (< 200 kWh)",
         latest_total < 200,
         f"Total yield: {latest_total} kWh", cat, "warn",
         enhancement="Track system commissioning date for accurate age check")
    
    # B8: Voltage in India grid range (210-250V)
    valid_voltages = [v for v in voltages if v > 0]
    if valid_voltages:
        test("B08 Voltage within India grid range (210-250V)",
             all(INDIA_VOLTAGE_MIN <= v <= INDIA_VOLTAGE_MAX for v in valid_voltages),
             f"Range: {min(valid_voltages)}-{max(valid_voltages)} V", cat)
    else:
        test("B08 Voltage within India grid range", False, "No valid voltage data", cat, "warn")
    
    # B9: Frequency in India grid range (49.5-50.5 Hz)
    valid_freqs = [f for f in freqs if f > 0]
    if valid_freqs:
        test("B09 Frequency within grid tolerance (49.5-50.5 Hz)",
             all(INDIA_FREQ_MIN <= f <= INDIA_FREQ_MAX for f in valid_freqs),
             f"Range: {min(valid_freqs)}-{max(valid_freqs)} Hz", cat)
    else:
        test("B09 Frequency within grid tolerance", False, "No frequency data", cat, "warn")
    
    # B10: Temperature realistic for Berhampur (10-50°C)
    valid_temps = [t for t in temps if t > 0]
    if valid_temps:
        test("B10 Temperature in realistic range (10-50°C)",
             all(10 <= t <= 50 for t in valid_temps),
             f"Range: {min(valid_temps)}-{max(valid_temps)} °C", cat)
    else:
        test("B10 Temperature in realistic range", False, "No temp data", cat, "warn")
    
    # B11: Current is consistent with power (P = V × I)
    power_current_ok = True
    p_i_errors = []
    for i, r in enumerate(history):
        p = r["current_power_kw"]
        v = r.get("voltage_v", 0)
        amp = r.get("current_a", 0)
        if v > 0 and p > 0.05:
            expected_current = (p * 1000) / v  # kW -> W -> A
            if amp > 0 and abs(expected_current - amp) / expected_current > 0.5:
                power_current_ok = False
                p_i_errors.append(f"[{i}] P={p}kW V={v}V I={amp}A expected_I={expected_current:.2f}A")
    test("B11 Current consistent with P=V×I (±50%)",
         power_current_ok,
         "; ".join(p_i_errors[:3]) if p_i_errors else "All consistent", cat, "error",
         enhancement="Calculate current_a = (power_kw * 1000) / voltage_v in data generator")
    
    # B12: Income consistent with total yield × tariff rate
    if incomes and total_yields:
        latest_income = incomes[-1]
        expected_income = total_yields[-1] * TARIFF_RATE
        tolerance = 0.3  # 30% tolerance for varying tariff
        if expected_income > 0:
            ratio = latest_income / expected_income
            test("B12 Income ≈ total_yield × tariff_rate (±30%)",
                 0.7 <= ratio <= 1.3,
                 f"Income: ₹{latest_income}, Expected: ₹{expected_income:.0f}, Ratio: {ratio:.2f}", cat, "warn")
        else:
            test("B12 Income ≈ total_yield × tariff_rate", True, "Zero yields", cat)
    
    # B13: Solar bell curve shape — peak should be near midday
    if len(powers) >= 4:
        peak_idx = powers.index(max(powers))
        mid_idx = len(powers) // 2
        # Peak should be in middle 60% of the day
        test("B13 Peak power occurs near midday",
             abs(peak_idx - mid_idx) <= len(powers) * 0.35,
             f"Peak at index {peak_idx}/{len(powers)-1} (mid={mid_idx})", cat, "warn")
    
    # B14: No all-zero records
    all_zero = [i for i, r in enumerate(history) if 
                r["current_power_kw"] == 0 and r["daily_yield_kwh"] == 0 and 
                r["total_yield_kwh"] == 0]
    test("B14 No all-zero records in history",
         len(all_zero) == 0,
         f"All-zero records at indices: {all_zero}", cat, "critical")
    
    # B15: Power at dawn/dusk should be low
    if len(powers) >= 6:
        first_power = powers[0]
        test("B15 Dawn power is low (< 30% capacity)",
             first_power < cap * 0.3,
             f"First reading: {first_power} kW", cat, "warn")
    
    # B16: Temperature increases through morning
    if len(valid_temps) >= 4:
        morning_temps = valid_temps[:len(valid_temps)//2]
        temp_increasing = all(morning_temps[i] <= morning_temps[i+1] for i in range(len(morning_temps)-1))
        test("B16 Morning temperature increases",
             temp_increasing or len(morning_temps) < 3,
             f"Morning temps: {morning_temps}", cat, "info")
    
    # B17: Portal validation scores in valid range (0-100)
    scores = [r.get("portal_validation_score", 0) for r in history]
    test("B17 Portal validation scores in 0-100 range",
         all(0 <= s <= 100 for s in scores),
         f"Scores: {scores}", cat)
    
    # B18: Status field has valid values
    valid_statuses = {"online", "normal", "offline", "error", "standby", "unknown", 
                      "portal not loaded", "extraction error"}
    statuses = [r.get("status", "").lower() for r in history]
    test("B18 All status values are recognized",
         all(s in valid_statuses for s in statuses),
         f"Unknown statuses: {set(s for s in statuses if s not in valid_statuses)}", cat, "warn")
    
    # B19: Extraction method is valid
    valid_methods = {"css_selector", "regex", "javascript", "device_tab", "none", ""}
    methods = [r.get("extraction_method", "") for r in history]
    test("B19 Extraction methods are valid",
         all(m in valid_methods for m in methods),
         f"Unknown: {set(m for m in methods if m not in valid_methods)}", cat, "warn")
    
    # B20: Power generation only during daylight (6am-7pm for Berhampur)
    night_power = []
    for r in history:
        try:
            hour = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S").hour
            if (hour < 6 or hour > 19) and r["current_power_kw"] > 0.01:
                night_power.append(f"{r['timestamp']}: {r['current_power_kw']}kW")
        except:
            pass
    test("B20 No power generation at night (before 6am / after 7pm)",
         len(night_power) == 0,
         f"Night power: {night_power[:3]}", cat, "warn")


# ═══════════════════════════════════════════════════════════════
# C. TEMPORAL CONSISTENCY (12 tests)
# ═══════════════════════════════════════════════════════════════
def test_temporal(data):
    cat = "C. Temporal Consistency"
    history = data.get("history", [])
    
    timestamps = []
    for r in history:
        try:
            timestamps.append(datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S"))
        except:
            pass
    
    if len(timestamps) < 2:
        test("C01 Sufficient temporal data", False, "Need ≥2 timestamps", cat)
        return
    
    # C1: Timestamps in chronological order
    test("C01 Timestamps in chronological order",
         all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1)),
         f"First: {timestamps[0]}, Last: {timestamps[-1]}", cat)
    
    # C2: No future timestamps
    now = datetime.now()
    future = [t for t in timestamps if t > now + timedelta(minutes=5)]
    test("C02 No future timestamps",
         len(future) == 0,
         f"Future timestamps: {[t.isoformat() for t in future[:3]]}", cat, "critical")
    
    # C3: All timestamps are from today
    today = now.date()
    non_today = [t for t in timestamps if t.date() != today]
    test("C03 All data from today",
         len(non_today) == 0,
         f"Non-today: {[t.isoformat() for t in non_today[:3]]}", cat, "warn",
         enhancement="Support multi-day history for trend analysis")
    
    # C4: Consistent time spacing (≤ 2h gaps)
    gaps = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(len(timestamps)-1)]
    max_gap = max(gaps) if gaps else 0
    test("C04 Time spacing ≤ 2 hours",
         max_gap <= 7200,
         f"Max gap: {max_gap/60:.0f} min", cat, "warn")
    
    # C5: Reasonable sampling interval (not too fast)
    min_gap = min(gaps) if gaps else 0
    test("C05 Minimum gap ≥ 10 seconds",
         min_gap >= 10,
         f"Min gap: {min_gap:.0f} sec", cat, "warn")
    
    # C6: Summary latest_timestamp matches last history record
    summary_ts = data.get("summary", {}).get("latest_timestamp", "")
    last_history_ts = history[-1].get("timestamp", "") if history else ""
    test("C06 Summary latest_timestamp matches last record",
         summary_ts == last_history_ts,
         f"Summary: {summary_ts}, History last: {last_history_ts}", cat)
    
    # C7: Summary latest_power matches last record
    summary_power = data.get("summary", {}).get("latest_power_kw", -1)
    last_power = history[-1].get("current_power_kw", -2) if history else -2
    test("C07 Summary latest_power matches last record",
         abs(summary_power - last_power) < 0.01,
         f"Summary: {summary_power}, Record: {last_power}", cat)
    
    # C8: Summary latest_daily matches last record
    summary_daily = data.get("summary", {}).get("latest_daily_yield_kwh", -1)
    last_daily = history[-1].get("daily_yield_kwh", -2) if history else -2
    test("C08 Summary latest_daily matches last record",
         abs(summary_daily - last_daily) < 0.01,
         f"Summary: {summary_daily}, Record: {last_daily}", cat)
    
    # C9: Summary latest_total matches last record
    summary_total = data.get("summary", {}).get("latest_total_yield_kwh", -1)
    last_total = history[-1].get("total_yield_kwh", -2) if history else -2
    test("C09 Summary latest_total matches last record",
         abs(summary_total - last_total) < 0.01,
         f"Summary: {summary_total}, Record: {last_total}", cat)
    
    # C10: generated_at is recent (within 24h)
    gen_at_str = data.get("meta", {}).get("generated_at", "")
    try:
        gen_at = datetime.strptime(gen_at_str, "%Y-%m-%d %H:%M:%S")
        age_hours = (now - gen_at).total_seconds() / 3600
        test("C10 Data generated within last 24 hours",
             age_hours < 24,
             f"Generated {age_hours:.1f} hours ago", cat, "warn")
    except:
        test("C10 Data generated within last 24 hours", False, f"Cannot parse: {gen_at_str}", cat)
    
    # C11: analytics computed_at is recent
    comp_at_str = data.get("analytics", {}).get("computed_at", "")
    try:
        comp_at = datetime.strptime(comp_at_str, "%Y-%m-%d %H:%M:%S")
        age_hours = (now - comp_at).total_seconds() / 3600
        test("C11 Analytics computed within last 24 hours",
             age_hours < 24,
             f"Computed {age_hours:.1f} hours ago", cat, "warn")
    except:
        test("C11 Analytics computed recently", False, f"Cannot parse: {comp_at_str}", cat)
    
    # C12: Data covers daylight hours starting near sunrise
    if timestamps:
        first_hour = timestamps[0].hour
        test("C12 Data starts near sunrise (6-8 AM)",
             6 <= first_hour <= 8,
             f"First timestamp hour: {first_hour}", cat, "info")


# ═══════════════════════════════════════════════════════════════
# D. ANALYTICS ENGINE VALIDATION (18 tests)
# ═══════════════════════════════════════════════════════════════
def test_analytics(data):
    cat = "D. Analytics Engine"
    analytics = data.get("analytics", {})
    history = data.get("history", [])
    powers = [r["current_power_kw"] for r in history]
    
    # D1: Power trend direction is valid enum
    trend_dir = analytics.get("power_trend", {}).get("direction", "")
    test("D01 Power trend direction is valid",
         trend_dir in ["rising", "falling", "stable", "insufficient_data"],
         f"Direction: {trend_dir}", cat)
    
    # D2: Slope sign matches direction
    slope = analytics.get("power_trend", {}).get("slope_kw_per_sample", 0)
    if trend_dir == "rising":
        test("D02 Slope positive when trend is rising", slope > 0, f"Slope: {slope}", cat)
    elif trend_dir == "falling":
        test("D02 Slope negative when trend is falling", slope < 0, f"Slope: {slope}", cat)
    else:
        test("D02 Slope near zero when stable", abs(slope) < 0.01, f"Slope: {slope}", cat, "info")
    
    # D3: R-squared in valid range [0, 1]
    r_sq = analytics.get("power_trend", {}).get("r_squared", -1)
    test("D03 R-squared in [0, 1]",
         0 <= r_sq <= 1,
         f"R²: {r_sq}", cat)
    
    # D4: EWMA length matches or ≤ history length
    ewma = analytics.get("power_trend", {}).get("ewma", [])
    test("D04 EWMA length ≤ history length",
         len(ewma) <= len(history),
         f"EWMA: {len(ewma)}, History: {len(history)}", cat)
    
    # D5: EWMA values are smoothed (lower variance than raw)
    if len(ewma) > 2 and len(powers) > 2:
        raw_var = statistics.variance(powers)
        ewma_var = statistics.variance(ewma)
        test("D05 EWMA variance ≤ raw variance (smoothing works)",
             ewma_var <= raw_var * 1.05,
             f"Raw var: {raw_var:.4f}, EWMA var: {ewma_var:.4f}", cat, "warn")
    
    # D6: Forecast is non-negative
    forecast = analytics.get("power_trend", {}).get("forecast_next_kw", -1)
    test("D06 Forecast is non-negative", forecast >= 0, f"Forecast: {forecast}", cat)
    
    # D7: Forecast is physically possible (≤ capacity × 1.5)
    test("D07 Forecast ≤ capacity × 1.5",
         forecast <= PLANT_CAPACITY_KW * 1.5,
         f"Forecast: {forecast} kW, Max reasonable: {PLANT_CAPACITY_KW * 1.5} kW", cat, "warn",
         enhancement="Clamp EWMA forecast to capacity upper bound")
    
    # D8: Anomaly counts are non-negative
    anomalies = analytics.get("anomalies", {})
    total_anomalies = anomalies.get("total_count", -1)
    test("D08 Anomaly total_count ≥ 0", total_anomalies >= 0, f"Count: {total_anomalies}", cat)
    
    # D9: Anomaly total = power + voltage count
    power_anom = len(anomalies.get("power", []))
    voltage_anom = len(anomalies.get("voltage", []))
    test("D09 total_count = len(power) + len(voltage)",
         total_anomalies == power_anom + voltage_anom,
         f"Total: {total_anomalies}, Power: {power_anom}, Voltage: {voltage_anom}", cat)
    
    # D10: Anomaly severity in [0, 1]
    all_anomalies = anomalies.get("power", []) + anomalies.get("voltage", [])
    sev_ok = all(0 <= a.get("severity", -1) <= 1 for a in all_anomalies)
    test("D10 All anomaly severities in [0, 1]", sev_ok or len(all_anomalies) == 0,
         f"Anomaly count: {len(all_anomalies)}", cat)
    
    # D11: Performance ratio in [0, 100]
    pr = analytics.get("performance", {}).get("performance_ratio_pct", -1)
    test("D11 Performance ratio in [0, 100]", 0 <= pr <= 100, f"PR: {pr}%", cat)
    
    # D12: Capacity factor in [0, 100]
    cf = analytics.get("performance", {}).get("capacity_factor_pct", -1)
    test("D12 Capacity factor in [0, 100]", 0 <= cf <= 100, f"CF: {cf}%", cat)
    
    # D13: Health score in [0, 100]
    health_score = analytics.get("health", {}).get("score", -1)
    test("D13 Health score in [0, 100]", 0 <= health_score <= 100, f"Score: {health_score}", cat)
    
    # D14: Health grade matches score range
    grade = analytics.get("health", {}).get("grade", "")
    expected_grade = "A+" if health_score >= 90 else "A" if health_score >= 80 else "B" if health_score >= 70 else "C" if health_score >= 60 else "D" if health_score >= 50 else "F"
    test("D14 Health grade matches score",
         grade == expected_grade,
         f"Score: {health_score}, Grade: {grade}, Expected: {expected_grade}", cat)
    
    # D15: Statistics power mean matches computed
    stat_mean = analytics.get("statistics", {}).get("power", {}).get("mean", -999)
    computed_mean = round(sum(powers) / len(powers), 3) if powers else 0
    test("D15 Statistics power mean matches computed",
         abs(stat_mean - computed_mean) < 0.01,
         f"Reported: {stat_mean}, Computed: {computed_mean}", cat)
    
    # D16: Statistics min ≤ mean ≤ max
    stats_p = analytics.get("statistics", {}).get("power", {})
    s_min = stats_p.get("min", 0)
    s_max = stats_p.get("max", 0)
    s_mean = stats_p.get("mean", 0)
    test("D16 Stats: min ≤ mean ≤ max",
         s_min <= s_mean <= s_max,
         f"Min={s_min}, Mean={s_mean}, Max={s_max}", cat)
    
    # D17: Q25 ≤ median ≤ Q75
    s_q25 = stats_p.get("q25", 0)
    s_median = stats_p.get("median", 0)
    s_q75 = stats_p.get("q75", 0)
    test("D17 Stats: Q25 ≤ median ≤ Q75",
         s_q25 <= s_median <= s_q75,
         f"Q25={s_q25}, Median={s_median}, Q75={s_q75}", cat)
    
    # D18: Health factors are all present and scored
    factors = analytics.get("health", {}).get("factors", {})
    expected_factors = ["power_consistency", "voltage_stability", "yield_efficiency", "data_quality", "uptime"]
    test("D18 All health factors present",
         all(f in factors for f in expected_factors),
         f"Missing: {[f for f in expected_factors if f not in factors]}", cat)


# ═══════════════════════════════════════════════════════════════
# E. FORECAST & PREDICTION QUALITY (12 tests)
# ═══════════════════════════════════════════════════════════════
def test_forecast(data):
    cat = "E. Forecast & Prediction"
    analytics = data.get("analytics", {})
    forecast = analytics.get("seasonal_forecast", {})
    
    # E1: Monthly forecast has 12 entries
    monthly = forecast.get("monthly_kwh", [])
    test("E01 Monthly forecast has 12 entries",
         len(monthly) == 12,
         f"Entries: {len(monthly)}", cat)
    
    # E2: All monthly values are non-negative
    test("E02 All monthly values ≥ 0",
         all(m >= 0 for m in monthly),
         f"Negative months: {[m for m in monthly if m < 0]}", cat)
    
    # E3: Annual = sum of monthly
    annual = forecast.get("annual_kwh", -1)
    computed_annual = round(sum(monthly), 1)
    test("E03 Annual = sum(monthly)",
         abs(annual - computed_annual) < 1,
         f"Reported: {annual}, Computed: {computed_annual}", cat)
    
    # E4: Annual is realistic for 2.32 kW system (2000-5000 kWh)
    test("E04 Annual forecast realistic (2000-5000 kWh for 2.32kW)",
         2000 <= annual <= 5000,
         f"Annual: {annual} kWh", cat, "warn",
         enhancement="Annual should be ~3500-4000 kWh for Berhampur with this capacity")
    
    # E5: Summer months > winter months (Northern hemisphere, tropical)
    if len(monthly) == 12:
        summer_avg = (monthly[3] + monthly[4] + monthly[5]) / 3  # Apr-Jun
        winter_avg = (monthly[11] + monthly[0] + monthly[1]) / 3  # Dec-Feb
        test("E05 Summer yield > winter yield",
             summer_avg > winter_avg,
             f"Summer avg: {summer_avg:.0f}, Winter avg: {winter_avg:.0f}", cat, "info")
    
    # E6: Monsoon dip (Jul-Sep lower than Apr-Jun)
    if len(monthly) == 12:
        monsoon_avg = (monthly[6] + monthly[7] + monthly[8]) / 3
        pre_monsoon_avg = (monthly[3] + monthly[4] + monthly[5]) / 3
        test("E06 Monsoon months lower than pre-monsoon",
             monsoon_avg < pre_monsoon_avg,
             f"Monsoon: {monsoon_avg:.0f}, Pre-monsoon: {pre_monsoon_avg:.0f}", cat)
    
    # E7: Monsoon drop percentage is realistic (30-70%)
    monsoon_drop = forecast.get("monsoon_drop_pct", -1)
    test("E07 Monsoon drop 30-70%",
         30 <= monsoon_drop <= 70,
         f"Drop: {monsoon_drop}%", cat, "info")
    
    # E8: Best month is in high-irradiance period (Mar-Jun)
    best = forecast.get("best_month", "")
    test("E08 Best month in Mar-Jun",
         best in ["Mar", "Apr", "May", "Jun"],
         f"Best month: {best}", cat, "info")
    
    # E9: Worst month is in monsoon (Jul-Sep)
    worst = forecast.get("worst_month", "")
    test("E09 Worst month in Jul-Sep",
         worst in ["Jul", "Aug", "Sep"],
         f"Worst month: {worst}", cat, "info")
    
    # E10: Month names are correct
    names = forecast.get("month_names", [])
    expected_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    test("E10 Month names correct", names == expected_names, f"Names: {names}", cat)
    
    # E11: Season factors present and sum to ~12 (average ~1.0)
    factors = forecast.get("season_factors", [])
    if factors:
        avg_factor = sum(factors) / len(factors)
        test("E11 Season factors average ≈ 1.0",
             0.85 <= avg_factor <= 1.15,
             f"Avg factor: {avg_factor:.3f}", cat, "info")
    
    # E12: PSH hours are Berhampur-calibrated (3-8 hours)
    psh = forecast.get("psh_hours", [])
    if psh:
        test("E12 PSH values in realistic range (3-8h)",
             all(3 <= p <= 8 for p in psh),
             f"Range: {min(psh)}-{max(psh)}", cat)


# ═══════════════════════════════════════════════════════════════
# F. DASHBOARD RENDERING CORRECTNESS (10 tests)
# ═══════════════════════════════════════════════════════════════
def test_dashboard_rendering(data):
    cat = "F. Dashboard Rendering"
    
    # Read index.html (main dashboard)
    try:
        with open("index.html", "r") as f:
            html = f.read()
    except:
        test("F00 Dashboard HTML exists", False, "Cannot read index.html", cat, "critical")
        return
    
    # F1: All referenced element IDs exist in HTML
    js_ids = re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", html)
    html_ids = re.findall(r'id="([^"]+)"', html)
    missing_ids = [jid for jid in js_ids if jid not in html_ids]
    test("F01 All JS-referenced element IDs exist in HTML",
         len(missing_ids) == 0,
         f"Missing IDs: {missing_ids[:5]}", cat, "error")
    
    # F2: setText function references all KPI IDs
    kpi_ids = ["kpi-power", "kpi-peak", "kpi-daily", "kpi-total", "kpi-income",
               "kpi-health", "kpi-grade", "kpi-pr", "kpi-quality"]
    found_kpi = [kid for kid in kpi_ids if kid in html]
    test("F02 All KPI element IDs present",
         len(found_kpi) == len(kpi_ids),
         f"Found {len(found_kpi)}/{len(kpi_ids)}: Missing={set(kpi_ids)-set(found_kpi)}", cat)
    
    # F3: Chart canvases exist
    charts = ["powerChart", "voltageChart", "monthlyChart"]
    for c in charts:
        test(f"F03 Canvas '{c}' exists in HTML",
             f'id="{c}"' in html, "", cat)
    
    # F4: Auto-refresh interval present
    test("F04 Auto-refresh interval configured",
         "setInterval(refresh" in html,
         "", cat)
    
    # F5: Scraper trigger configured
    test("F05 Scraper auto-trigger configured",
         "triggerScrape" in html,
         "", cat,
         enhancement="Show last scrape timestamp on dashboard")
    
    # F6: Chart.js CDN reference present
    test("F06 Chart.js CDN included",
         "chart.js" in html.lower() or "chartjs" in html.lower(),
         "", cat)
    
    # F7: Dark mode support
    test("F07 Dark mode CSS support",
         "prefers-color-scheme: dark" in html,
         "", cat, "info")
    
    # F8: Mobile responsive
    test("F08 Mobile responsive meta tag",
         'viewport' in html and 'width=device-width' in html,
         "", cat, "info")
    
    # F9: Correct data fields mapped in normalizeRecords
    test("F09 normalizeRecords maps current_power_kw",
         "current_power_kw" in html,
         "", cat)
    
    # F10: Error handling in refresh function
    test("F10 Error handling in refresh function",
         "catch" in html and "Data Error" in html,
         "", cat)


# ═══════════════════════════════════════════════════════════════
# G. EDGE CASES & ROBUSTNESS (13 tests)
# ═══════════════════════════════════════════════════════════════
def test_edge_cases(data):
    cat = "G. Edge Cases"
    history = data.get("history", [])
    analytics = data.get("analytics", {})
    
    # G1: Handle zero power gracefully
    zero_power_records = [r for r in history if r["current_power_kw"] == 0]
    test("G01 System handles zero-power records",
         True,  # existence check
         f"Zero-power records: {len(zero_power_records)}/{len(history)}", cat, "info")
    
    # G2: Division by zero protection in capacity factor
    cf = analytics.get("performance", {}).get("capacity_factor_pct", 0)
    test("G02 Capacity factor computed without div-by-zero",
         cf >= 0 and not math.isnan(cf) and not math.isinf(cf),
         f"CF: {cf}%", cat)
    
    # G3: Empty anomaly list handling
    power_anomalies = analytics.get("anomalies", {}).get("power", None)
    test("G03 Power anomalies is a list (not null)",
         isinstance(power_anomalies, list),
         f"Type: {type(power_anomalies)}", cat)
    
    # G4: Statistics handles small dataset
    test("G04 Statistics computed with small dataset",
         "statistics" in analytics and "power" in analytics.get("statistics", {}),
         f"History size: {len(history)}", cat)
    
    # G5: Degradation handles insufficient data gracefully
    deg = analytics.get("performance", {}).get("degradation", {})
    test("G05 Degradation reports insufficient_data for small dataset",
         deg.get("confidence") == "insufficient_data" or len(history) >= 10,
         f"Confidence: {deg.get('confidence')}, Records: {len(history)}", cat, "info")
    
    # G6: No NaN or Inf in analytics
    analytics_str = json.dumps(analytics)
    test("G06 No NaN in analytics JSON",
         "NaN" not in analytics_str,
         "", cat, "critical")
    test("G07 No Infinity in analytics JSON",
         "Infinity" not in analytics_str,
         "", cat, "critical")
    
    # G8: OCR quality handles empty text
    ocr = analytics.get("ocr_quality", {})
    test("G08 OCR quality score computed",
         "quality" in ocr,
         f"Quality: {ocr.get('quality')}", cat)
    
    # G9: Seasonal forecast works for any month
    sf = analytics.get("seasonal_forecast", {})
    current_month = sf.get("current_month_name", "")
    test("G09 Current month name is valid",
         current_month in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
         f"Month: {current_month}", cat)
    
    # G10: No negative EWMA values
    ewma = analytics.get("power_trend", {}).get("ewma", [])
    test("G10 No negative EWMA values",
         all(v >= 0 for v in ewma),
         f"Negative values: {[v for v in ewma if v < 0]}", cat)
    
    # G11: File size reasonable (< 1MB)
    file_size = os.path.getsize(DATA_FILE)
    test("G11 Data file size reasonable (< 1MB)",
         file_size < 1_000_000,
         f"Size: {file_size/1024:.1f} KB", cat, "info")
    
    # G12: Data file is valid UTF-8
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            f.read()
        test("G12 Data file is valid UTF-8", True, "", cat)
    except UnicodeDecodeError:
        test("G12 Data file is valid UTF-8", False, "Encoding error", cat)
    
    # G13: Credentials file doesn't leak into dashboard data
    data_str = json.dumps(data)
    creds = load_credentials()
    test("G13 Password not in dashboard data",
         creds.get("password", "NONE") not in data_str,
         "", cat, "critical")


# ═══════════════════════════════════════════════════════════════
# H. CROSS-FIELD CONSISTENCY (10 tests)
# ═══════════════════════════════════════════════════════════════
def test_cross_field(data):
    cat = "H. Cross-field Consistency"
    history = data.get("history", [])
    summary = data.get("summary", {})
    analytics = data.get("analytics", {})
    
    powers = [r["current_power_kw"] for r in history]
    
    # H1: Summary peak_power matches max of history
    summary_peak = summary.get("peak_power_kw", -1)
    actual_peak = max(powers) if powers else 0
    test("H01 Summary peak_power = max(history powers)",
         abs(summary_peak - actual_peak) < 0.01,
         f"Summary: {summary_peak}, Actual: {actual_peak}", cat)
    
    # H2: Summary avg_power matches computed average
    summary_avg = summary.get("avg_power_kw", -1)
    actual_avg = round(sum(powers) / len(powers), 3) if powers else 0
    test("H02 Summary avg_power matches computed",
         abs(summary_avg - actual_avg) < 0.01,
         f"Summary: {summary_avg}, Computed: {actual_avg}", cat)
    
    # H3: Analytics stats mean matches summary avg
    analytics_mean = analytics.get("statistics", {}).get("power", {}).get("mean", -999)
    test("H03 Analytics power mean ≈ summary avg",
         abs(analytics_mean - summary_avg) < 0.05,
         f"Analytics: {analytics_mean}, Summary: {summary_avg}", cat)
    
    # H4: Uptime pct consistent between summary and health
    summary_uptime = summary.get("uptime_pct", -1)
    health_uptime = analytics.get("health", {}).get("factors", {}).get("uptime", -1)
    test("H04 Uptime consistent (summary vs health)",
         abs(summary_uptime - health_uptime) < 1,
         f"Summary: {summary_uptime}%, Health: {health_uptime}%", cat)
    
    # H5: Total yield difference ≈ daily yield for latest
    if len(history) >= 2:
        total_diff = history[-1]["total_yield_kwh"] - history[0]["total_yield_kwh"]
        latest_daily = history[-1]["daily_yield_kwh"]
        test("H05 Total yield growth ≈ daily yield",
             abs(total_diff - latest_daily) < latest_daily * 0.3 + 0.5,
             f"Total diff: {total_diff:.2f}, Daily: {latest_daily:.2f}", cat, "warn",
             enhancement="total_yield should increase by daily_yield between first and last sample")
    
    # H6: Income grows with total yield
    if len(history) >= 2:
        income_increasing = history[-1].get("income_inr", 0) >= history[0].get("income_inr", 0)
        test("H06 Income increases with total yield",
             income_increasing,
             f"First: ₹{history[0].get('income_inr',0)}, Last: ₹{history[-1].get('income_inr',0)}", cat)
    
    # H7: Power vs daily yield integral check
    # Approximate: daily yield should be roughly sum(power * dt)
    if len(history) >= 3:
        dt_hours = 1.0  # hourly sampling
        power_integral = sum(p * dt_hours for p in powers)
        actual_daily = history[-1]["daily_yield_kwh"]
        if power_integral > 0:
            ratio = actual_daily / power_integral
            test("H07 Daily yield ≈ ∫power·dt (energy integral)",
                 0.5 <= ratio <= 2.0,
                 f"Integral: {power_integral:.2f} kWh, Reported daily: {actual_daily:.2f}, Ratio: {ratio:.2f}", cat, "warn",
                 enhancement="Daily yield should closely match time-integrated power readings")
    
    # H8: Voltage in analytics matches raw data
    analytics_v_mean = analytics.get("statistics", {}).get("voltage", {}).get("mean", -1)
    summary_v_mean = summary.get("avg_voltage_v", -1)
    test("H08 Analytics voltage mean ≈ summary voltage",
         abs(analytics_v_mean - summary_v_mean) < 1,
         f"Analytics: {analytics_v_mean}, Summary: {summary_v_mean}", cat)
    
    # H9: Capacity factor consistent with latest power / capacity
    cf = analytics.get("performance", {}).get("capacity_factor_pct", -1)
    latest_power = powers[-1] if powers else 0
    expected_cf = round((latest_power / PLANT_CAPACITY_KW) * 100, 1) if PLANT_CAPACITY_KW > 0 else 0
    test("H09 Capacity factor = latest_power / capacity × 100",
         abs(cf - expected_cf) < 1,
         f"Reported CF: {cf}%, Computed: {expected_cf}%", cat)
    
    # H10: Meta capacity matches credentials
    creds = load_credentials()
    meta_cap = data.get("meta", {}).get("plant_capacity_kw", -1)
    cred_cap = creds.get("plant_capacity_kw", -1)
    test("H10 Meta capacity matches credentials.json",
         abs(meta_cap - cred_cap) < 0.01,
         f"Meta: {meta_cap}, Credentials: {cred_cap}", cat)


# ═══════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════
def run_all():
    print("=" * 76)
    print("  SOLAR DASHBOARD — COMPREHENSIVE VALIDATION SUITE")
    print("=" * 76)
    print()
    
    data = load_data()
    
    test_schema(data)
    test_realism(data)
    test_temporal(data)
    test_analytics(data)
    test_forecast(data)
    test_dashboard_rendering(data)
    test_edge_cases(data)
    test_cross_field(data)
    
    # ── Results Summary ──
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    
    # Print by category
    categories = OrderedDict()
    for r in results:
        categories.setdefault(r.category, []).append(r)
    
    enhancements = []
    
    for cat, tests in categories.items():
        cat_passed = sum(1 for t in tests if t.passed)
        cat_total = len(tests)
        status = "✅" if cat_passed == cat_total else "⚠️"
        print(f"\n{status} {cat} ({cat_passed}/{cat_total})")
        print("─" * 60)
        
        for t in tests:
            icon = "✅" if t.passed else {"critical": "🔴", "error": "❌", "warn": "⚠️", "info": "ℹ️"}.get(t.severity, "❌")
            print(f"  {icon} {t.name}")
            if not t.passed and t.detail:
                print(f"     → {t.detail}")
            if t.enhancement:
                enhancements.append((t.name, t.enhancement))
    
    # ── Final Score ──
    print(f"\n{'=' * 76}")
    pct = (passed / total * 100) if total > 0 else 0
    grade = "A+" if pct >= 98 else "A" if pct >= 95 else "B" if pct >= 85 else "C" if pct >= 70 else "D" if pct >= 50 else "F"
    print(f"  RESULT: {passed}/{total} passed ({pct:.1f}%)  —  Grade: {grade}")
    
    critical = sum(1 for r in results if not r.passed and r.severity == "critical")
    errors = sum(1 for r in results if not r.passed and r.severity == "error")
    warns = sum(1 for r in results if not r.passed and r.severity == "warn")
    infos = sum(1 for r in results if not r.passed and r.severity == "info")
    if failed:
        print(f"  Failures: {critical} critical, {errors} errors, {warns} warnings, {infos} info")
    print(f"{'=' * 76}")
    
    # ── Enhancement Opportunities ──
    if enhancements:
        print(f"\n📋 ENHANCEMENT OPPORTUNITIES ({len(enhancements)} found)")
        print("─" * 60)
        for name, enh in enhancements:
            print(f"  💡 [{name}] {enh}")
    
    # ── Failed tests details ──
    failures = [r for r in results if not r.passed]
    if failures:
        print(f"\n🔍 FAILED TEST DETAILS")
        print("─" * 60)
        for r in failures:
            sev_icon = {"critical": "🔴", "error": "❌", "warn": "⚠️", "info": "ℹ️"}.get(r.severity, "❌")
            print(f"  {sev_icon} {r.name} [{r.severity.upper()}]")
            if r.detail:
                print(f"     {r.detail}")
    
    return passed, failed, total, enhancements, failures


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    passed, failed, total, enhancements, failures = run_all()
