#!/usr/bin/env python3
"""Quick data validation check."""
import json
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=== Energy Log (Feb 16) ===")
with open("data/energy_logs/solar_energy_2026-02-16.json") as f:
    log = json.load(f)
print(f"Records: {log['meta']['record_count']}")
for r in log["records"]:
    print(f"  {r['timestamp']} - Power: {r['current_power_kw']} kW, "
          f"Daily: {r['daily_yield_kwh']} kWh, Method: {r['extraction_method']}")
print(f"Summary: peak={log['daily_summary']['peak_power_kw']} kW, "
      f"total={log['daily_summary']['total_yield_kwh']} kWh")

print("\n=== Dashboard Data ===")
with open("data/dashboard_data.json") as f:
    dash = json.load(f)
print(f"Schema: {dash['meta']['schema_version']}")
live = dash["live"]
print(f"Live: power={live['power_kw']} kW, daily={live['daily_yield_kwh']} kWh, "
      f"monthly={live['monthly_yield_kwh']} kWh, total={live['total_yield_kwh']} kWh")
print("Last 7 days:")
for d in dash["last_7_days"]:
    print(f"  {d['date']}: {d['yield_kwh']} kWh, {d['record_count']} records, peak={d['peak_power_kw']} kW")

analytics = dash.get("analytics", {})
health = analytics.get("health", {})
print(f"\nHealth: grade={health.get('grade', '?')}, score={health.get('overall_score', '?')}")
print(f"Performance ratio: {analytics.get('performance_ratio_pct', '?')}%")
print(f"Capacity factor: {analytics.get('capacity_factor_pct', '?')}%")

# Sanity checks
errors = []
if live["power_kw"] < 0 or live["power_kw"] > 5:
    errors.append(f"Power out of range: {live['power_kw']}")
if live["daily_yield_kwh"] < 0 or live["daily_yield_kwh"] > 25:
    errors.append(f"Daily yield out of range: {live['daily_yield_kwh']}")
if live["total_yield_kwh"] < 0:
    errors.append(f"Total yield negative: {live['total_yield_kwh']}")
if len(dash["last_7_days"]) < 1:
    errors.append("No days in last_7_days")

if errors:
    print(f"\n!! VALIDATION ERRORS: {errors}")
    sys.exit(1)
else:
    print("\n✓ All data validation checks passed")
