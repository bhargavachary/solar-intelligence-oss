#!/usr/bin/env python3
"""
Daily Data Archiver — Immutable Solar Telemetry Storage
========================================================
Extracts minute/hour-level data for a given date and writes an immutable
archive file: `solar_energy_<date>.json`

Archives are the SOURCE OF TRUTH and must never be modified after creation.

Usage:
    python scripts/archive_daily_data.py                # archive today
    python scripts/archive_daily_data.py 2026-02-14    # archive specific date
    python scripts/archive_daily_data.py --backfill    # archive all dates in current data
"""
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "dashboard_data.json"
ARCHIVE_DIR = ROOT / "data" / "archives"


def parse_args():
    parser = argparse.ArgumentParser(description="Archive daily solar data")
    parser.add_argument("date", nargs="?", help="Date to archive (YYYY-MM-DD), default: today")
    parser.add_argument("--backfill", action="store_true", help="Archive all dates in dashboard_data.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing archive (use with caution)")
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


def create_archive(data, target_date, force=False):
    """
    Create an immutable archive file for the given date.
    Returns True if archive was created, False if skipped.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    archive_file = ARCHIVE_DIR / f"solar_energy_{target_date}.json"
    
    # Check if archive already exists
    if archive_file.exists() and not force:
        print(f"  ⚠️  Archive already exists: {archive_file.name} (use --force to overwrite)")
        return False
    
    # Extract records
    records, daily_summary = extract_records_for_date(data, target_date)
    
    if not records:
        print(f"  ⚠️  No data found for {target_date}")
        return False
    
    # Build archive structure
    meta = data.get("meta", {})
    archive = {
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
    
    # Write archive (immutable)
    with open(archive_file, "w") as f:
        json.dump(archive, f, indent=2)
    
    size_kb = archive_file.stat().st_size / 1024
    print(f"  ✅ Created: {archive_file.name} ({size_kb:.1f} KB, {len(records)} records)")
    return True


def backfill_archives(data, force=False):
    """Archive all dates found in the current dashboard_data.json."""
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
    print(f"📦 Found {len(dates)} unique dates to archive")
    
    created = 0
    skipped = 0
    
    for date in dates:
        if create_archive(data, date, force):
            created += 1
        else:
            skipped += 1
    
    print(f"\n✅ Backfill complete: {created} created, {skipped} skipped")


def main():
    args = parse_args()
    
    print("=" * 60)
    print("📁 Daily Data Archiver")
    print("=" * 60)
    
    data = load_dashboard_data()
    
    if args.backfill:
        backfill_archives(data, args.force)
    else:
        # Archive specific date
        if args.date:
            target_date = args.date
        else:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"📅 Target date: {target_date}")
        create_archive(data, target_date, args.force)
    
    print("=" * 60)


if __name__ == "__main__":
    main()
