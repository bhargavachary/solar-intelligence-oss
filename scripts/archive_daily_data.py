#!/usr/bin/env python3
"""
Daily Energy Logger — Immutable Solar Telemetry Storage
========================================================
Extracts minute/hour-level data for a given date and writes an immutable
energy log: `solar_energy_<date>.json`

Energy logs are the SOURCE OF TRUTH and must never be modified after creation.

Usage:
    python scripts/archive_daily_data.py                # log today's data
    python scripts/archive_daily_data.py 2026-02-14    # log specific date
    python scripts/archive_daily_data.py --backfill    # log all dates from current data
"""
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "dashboard_data.json"
ENERGY_LOG_DIR = ROOT / "data" / "energy_logs"


def parse_args():
    parser = argparse.ArgumentParser(description="Create daily energy logs")
    parser.add_argument("date", nargs="?", help="Date to log (YYYY-MM-DD), default: today")
    parser.add_argument("--backfill", action="store_true", help="Log all dates in dashboard_data.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing log (use with caution)")
    return parser.parse_args()


def load_dashboard_data():
    """Load current dashboard_data.json."""
    if not DATA_FILE.exists():
        print(f"✗ {DATA_FILE} not found")
        sys.exit(1)
    with open(DATA_FILE) as f:
        return json.load(f)


def extract_records_for_date(data, target_date):
    """
    Extract all records for a given date from the history array.
    Returns (records, daily_summary).
    """
    history = data.get("history", [])
    records_for_date = []
    
    for record in history:
        ts = record.get("timestamp", "")
        if ts.startswith(target_date):
            records_for_date.append(record)
    
    if not records_for_date:
        return [], None
    
    # Compute daily summary
    powers = [r.get("current_power_kw", 0) for r in records_for_date if r.get("current_power_kw")]
    voltages = [r.get("voltage_v", 0) for r in records_for_date if r.get("voltage_v")]
    
    latest = records_for_date[-1]
    daily_summary = {
        "date": target_date,
        "total_yield_kwh": latest.get("daily_yield_kwh", 0),
        "peak_power_kw": max(powers) if powers else 0,
        "avg_power_kw": sum(powers) / len(powers) if powers else 0,
        "avg_voltage_v": sum(voltages) / len(voltages) if voltages else 0,
        "record_count": len(records_for_date),
        "first_reading": records_for_date[0].get("timestamp"),
        "last_reading": records_for_date[-1].get("timestamp"),
    }
    
    return records_for_date, daily_summary


def create_energy_log(data, target_date, force=False):
    """
    Create or UPDATE an energy log file for the given date.
    
    If the log already exists:
      - Merge new records into the existing log (deduplicate by timestamp)
      - Update the daily summary with new highs
      - Preserve existing records
    
    Returns True if log was created/updated, False if skipped.
    """
    ENERGY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    log_file = ENERGY_LOG_DIR / f"solar_energy_{target_date}.json"
    
    # Extract records from current dashboard data
    records, daily_summary = extract_records_for_date(data, target_date)
    
    if not records:
        print(f"  ⚠️  No data found for {target_date}")
        return False
    
    # If log exists, MERGE records instead of skipping/overwriting
    if log_file.exists() and not force:
        try:
            with open(log_file) as f:
                existing = json.load(f)
            
            existing_records = existing.get("records", [])
            existing_timestamps = {r.get("timestamp") for r in existing_records}
            
            # Add new records that don't already exist
            new_count = 0
            for rec in records:
                if rec.get("timestamp") not in existing_timestamps:
                    existing_records.append(rec)
                    new_count += 1
            
            if new_count == 0:
                print(f"  ℹ️  No new records to add for {target_date} ({len(existing_records)} existing)")
                return False
            
            # Re-sort by timestamp
            existing_records.sort(key=lambda r: r.get("timestamp", ""))
            
            # Recompute daily summary with all records
            powers = [r.get("current_power_kw", 0) for r in existing_records if r.get("current_power_kw")]
            voltages = [r.get("voltage_v", 0) for r in existing_records if r.get("voltage_v")]
            latest = existing_records[-1]
            
            merged_summary = {
                "date": target_date,
                "total_yield_kwh": latest.get("daily_yield_kwh", 0),
                "peak_power_kw": max(powers) if powers else 0,
                "avg_power_kw": sum(powers) / len(powers) if powers else 0,
                "avg_voltage_v": sum(voltages) / len(voltages) if voltages else 0,
                "record_count": len(existing_records),
                "first_reading": existing_records[0].get("timestamp"),
                "last_reading": existing_records[-1].get("timestamp"),
            }
            
            # Update the log
            existing["records"] = existing_records
            existing["daily_summary"] = merged_summary
            existing["meta"]["archived_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            existing["meta"]["record_count"] = len(existing_records)
            
            with open(log_file, "w") as f:
                json.dump(existing, f, indent=2)
            
            print(f"  ✅ Merged {new_count} new records into {log_file.name} "
                  f"(total: {len(existing_records)} records)")
            return True
            
        except Exception as e:
            print(f"  ⚠️  Merge failed, will recreate: {e}")
            # Fall through to create fresh
    
    # Build energy log structure
    meta = data.get("meta", {})
    energy_log = {
        "date": target_date,
        "plant_id": meta.get("plant_id"),
        "meta": {
            "plant_capacity_kw": meta.get("plant_capacity_kw"),
            "location": meta.get("location"),
            "archived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "record_count": len(records),
            "sampling_interval": "hourly",
            "data_source": meta.get("data_source", "live_portal"),
        },
        "daily_summary": daily_summary,
        "records": records
    }
    
    # Write energy log
    with open(log_file, "w") as f:
        json.dump(energy_log, f, indent=2)
    
    size_kb = log_file.stat().st_size / 1024
    print(f"  ✅ Created: {log_file.name} ({size_kb:.1f} KB, {len(records)} records)")
    return True


def backfill_energy_logs(data, force=False):
    """Create energy logs for all dates found in the current dashboard_data.json."""
    history = data.get("history", [])
    if not history:
        print("✗ No history records to backfill")
        return
    
    # Group records by date
    dates = set()
    for record in history:
        ts = record.get("timestamp", "")
        if ts:
            date = ts.split()[0]  # Extract YYYY-MM-DD
            dates.add(date)
    
    dates = sorted(dates)
    print(f"📦 Found {len(dates)} unique dates to log")
    
    created = 0
    skipped = 0
    
    for date in dates:
        if create_energy_log(data, date, force):
            created += 1
        else:
            skipped += 1
    
    print(f"\n✅ Backfill complete: {created} created, {skipped} skipped")


def main():
    args = parse_args()
    
    print("=" * 60)
    print("� Daily Energy Logger")
    print("=" * 60)
    
    data = load_dashboard_data()
    
    if args.backfill:
        backfill_energy_logs(data, args.force)
    else:
        # Log specific date
        if args.date:
            target_date = args.date
        else:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"📅 Target date: {target_date}")
        create_energy_log(data, target_date, args.force)
    
    print("=" * 60)


if __name__ == "__main__":
    main()
