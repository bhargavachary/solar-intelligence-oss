#!/usr/bin/env python3
from __future__ import annotations
"""
Solar Intelligence — Data Update Pipeline
==========================================
Fetches real data from Waaree/FoxESS Cloud API, writes:
  - data/dashboard.json   (schema v5.0 — consumed by index.html)
  - data/energy_history.csv  (daily table with hourly power columns)
  - data/energy_logs/solar_energy_YYYY-MM-DD.json  (daily archive)

Usage:
    python3 update_data.py              # fetch, save, no git
    python3 update_data.py --push       # fetch, save, commit, push
"""

import json
import csv
import os
import sys
import subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from waaree_api_client import WaareeAPIClient
from scraper_api import build_dashboard_json


def load_credentials():
    creds_path = os.path.join(BASE, "credentials.json")
    if not os.path.exists(creds_path):
        print("❌ credentials.json not found")
        sys.exit(1)
    with open(creds_path) as f:
        return json.load(f)


def fetch_dashboard(client):
    """Fetch all API data and build schema v5.0 dashboard payload."""
    data = build_dashboard_json(client)
    out = os.path.join(BASE, "data", "dashboard.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp_out = out + ".tmp"
    with open(tmp_out, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_out, out)
    print(f"✅ data/dashboard.json updated ({data['meta']['generated_at']})")
    return data


def save_energy_log(data):
    """Save today's energy log with hourly breakdown."""
    live = data.get("live", {})
    meta = data.get("meta", {})
    today = meta.get("generated_at", "").split(" ")[0] or datetime.now().strftime("%Y-%m-%d")

    log = {
        "date": today,
        "daily_kwh": live.get("daily_yield_kwh", 0),
        "monthly_kwh": live.get("monthly_yield_kwh", 0),
        "total_kwh": live.get("total_yield_kwh", 0),
        "peak_power_kw": data.get("summary", {}).get("peak_power_kw", 0),
        "status": live.get("status", "Unknown"),
        "source": "api",
        "logged_at": datetime.now().isoformat(),
        "hourly": [],
    }
    for rec in data.get("today_records", []):
        ts = rec.get("timestamp", "")
        if ts:
            hour = int(ts.split(" ")[1].split(":")[0])
            log["hourly"].append({
                "hour": hour,
                "power_kw": round(rec.get("current_power_kw", 0), 3),
                "cumulative_kwh": round(rec.get("daily_yield_kwh", 0), 2),
            })

    log_dir = os.path.join(BASE, "data", "energy_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"solar_energy_{today}.json")
    tmp_file = log_file + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(log, f, indent=2)
    os.replace(tmp_file, log_file)
    print(f"✅ Energy log: data/energy_logs/solar_energy_{today}.json")


def build_csv(data):
    """Build/update data/energy_history.csv — one row per day, hourly power columns."""
    daily_rows = {}
    hour_cols = [f"h{h:02d}_kw" for h in range(5, 20)]
    empty_hours = {c: "" for c in hour_cols}

    # From dashboard last_7_days
    for day in data.get("last_7_days", []):
        dt = day["date"]
        daily_rows[dt] = {
            "date": dt,
            "yield_kwh": round(day.get("yield_kwh", 0), 2),
            "peak_power_kw": round(day.get("peak_power_kw", 0), 3),
            "avg_power_kw": round(day.get("avg_power_kw", 0), 3),
            "source": "api",
            **empty_hours,
        }

    # Fill today's hourly from today_records
    today = data.get("meta", {}).get("generated_at", "").split(" ")[0]
    for rec in data.get("today_records", []):
        ts = rec.get("timestamp", "")
        if ts and today in daily_rows:
            hour = int(ts.split(" ")[1].split(":")[0])
            col = f"h{hour:02d}_kw"
            if col in daily_rows[today]:
                daily_rows[today][col] = round(rec.get("current_power_kw", 0), 3)

    # Merge with existing CSV
    csv_path = os.path.join(BASE, "data", "energy_history.csv")
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                dt = row.get("date", "")
                if dt and dt not in daily_rows:
                    daily_rows[dt] = row

    # Also incorporate real energy logs
    log_dir = os.path.join(BASE, "data", "energy_logs")
    if os.path.isdir(log_dir):
        for fn in sorted(os.listdir(log_dir)):
            if not fn.endswith(".json"):
                continue
            try:
                log = json.load(open(os.path.join(log_dir, fn)))
            except Exception:
                continue
            src = log.get("meta", {}).get("data_source", log.get("source", ""))
            if src == "simulated_realistic":
                continue
            dt = log.get("date", "")
            if not dt:
                continue
            if dt not in daily_rows:
                daily_rows[dt] = {
                    "date": dt,
                    "yield_kwh": round(float(log.get("daily_kwh") or log.get("daily_summary", {}).get("total_yield_kwh", 0) or 0), 2),
                    "peak_power_kw": round(float(log.get("peak_power_kw") or log.get("daily_summary", {}).get("peak_power_kw", 0) or 0), 3),
                    "avg_power_kw": round(float(log.get("daily_summary", {}).get("avg_power_kw", 0) or 0), 3),
                    "source": src or "log",
                    **empty_hours,
                }
            # Fill hourly from log records
            for rec in log.get("records", []) + log.get("hourly", []):
                ts = rec.get("timestamp", "")
                h = rec.get("hour")
                if ts:
                    h = int(ts.split(" ")[1].split(":")[0])
                if h is not None:
                    col = f"h{h:02d}_kw"
                    pw = rec.get("current_power_kw") or rec.get("power_kw", 0)
                    if col in daily_rows.get(dt, {}):
                        daily_rows[dt][col] = round(float(pw), 3)

    # Reconcile peak_power_kw and avg_power_kw from actual measured hourly power if available
    for dt, row in daily_rows.items():
        measured_powers = []
        for col in hour_cols:
            val = row.get(col)
            if val is not None and val != "":
                try:
                    p = float(val)
                    if p > 0:
                        measured_powers.append(p)
                except (ValueError, TypeError):
                    pass
        if measured_powers:
            actual_peak = max(measured_powers)
            curr_peak = float(row.get("peak_power_kw", 0) or 0)
            if actual_peak > curr_peak:
                row["peak_power_kw"] = round(actual_peak, 3)
            curr_avg = float(row.get("avg_power_kw", 0) or 0)
            if curr_avg == 0:
                row["avg_power_kw"] = round(sum(measured_powers) / len(measured_powers), 3)

    # Write sorted atomically
    fieldnames = ["date", "yield_kwh", "peak_power_kw", "avg_power_kw"] + hour_cols + ["source"]
    tmp_csv = csv_path + ".tmp"
    with open(tmp_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for dt in sorted(daily_rows.keys()):
            row = daily_rows[dt]
            for col in fieldnames:
                if col not in row:
                    row[col] = ""
            writer.writerow(row)
    os.replace(tmp_csv, csv_path)

    print(f"✅ CSV table: data/energy_history.csv ({len(daily_rows)} days)")


def git_push():
    """Commit data changes and push to GitHub."""
    os.chdir(BASE)
    subprocess.run(["git", "add", "data/"], check=True)
    result = subprocess.run(
        ["git", "commit", "-m", f"📊 Data update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"✅ Committed: {result.stdout.strip().splitlines()[0]}")
        subprocess.run(["git", "push"], check=True)
        print("✅ Pushed to GitHub — Pages will auto-deploy")
    else:
        print("ℹ️  No data changes to commit")


def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Solar Intelligence — Data Update")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    creds = load_credentials()
    token_file = os.path.join(BASE, ".waaree_token.json")
    client = WaareeAPIClient(creds["username"], creds["password"], token_file=token_file)
    client.login()

    data = fetch_dashboard(client)
    save_energy_log(data)
    build_csv(data)

    if "--push" in sys.argv:
        git_push()

    print("\n━━━ Done ━━━")


if __name__ == "__main__":
    main()
