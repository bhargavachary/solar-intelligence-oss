#!/usr/bin/env python3
"""
Data Update Pipeline
====================
Orchestrates data generation and analytics for CI/CD or local refresh.
Can optionally attempt a live scrape if credentials are available.

Usage:
    python scripts/update_data.py                # Generate + analyze
    python scripts/update_data.py --scrape       # Attempt live scrape first
"""
import json
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "dashboard_data.json"

sys.path.insert(0, str(ROOT))


def run_generate(days: int = 1):
    """Run the data generator."""
    print("═══ Data Generator ═══")
    from scripts.generate_data import generate_day, build_dashboard_json
    now = datetime.now()
    all_records = []
    for d in range(days):
        day_offset = days - 1 - d
        from datetime import timedelta
        day = now - timedelta(days=day_offset)
        cap = now.hour if day_offset == 0 else 24
        records = generate_day(day, day_offset=d, seed=42 + d, current_hour_cap=cap)
        all_records.extend(records)

    dashboard = build_dashboard_json(all_records)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(dashboard, f, indent=2)
    print(f"  ✓ {len(all_records)} records written")
    return True


def run_analytics():
    """Run the analytics engine."""
    print("═══ Analytics Engine ═══")
    try:
        from solar_analytics import run_analytics as _run
        _run(str(DATA_FILE))
        print("  ✓ Analytics enriched")
        return True
    except Exception as e:
        print(f"  ⚠ Skipped: {e}")
        return False


def run_scrape():
    """Attempt a live scrape (requires credentials.json + Selenium)."""
    print("═══ Live Scrape ═══")
    cred_file = ROOT / "credentials.json"
    if not cred_file.exists():
        print("  ⚠ credentials.json not found — skipping scrape")
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "waaree_deep_crawler.py")],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT)
        )
        if result.returncode == 0:
            print("  ✓ Live scrape completed")
            return True
        else:
            print(f"  ⚠ Scrape failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ⚠ Scrape error: {e}")
        return False


def validate_output():
    """Quick validation of the generated data."""
    print("═══ Validation ═══")
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        checks = {
            "has_meta": "meta" in data,
            "has_history": "history" in data and len(data["history"]) > 0,
            "has_summary": "summary" in data,
            "has_analytics": "analytics" in data,
            "records_count": len(data.get("history", [])),
            "schema_version": data.get("meta", {}).get("schema_version", "?"),
        }
        for k, v in checks.items():
            status = "✓" if v else "✗"
            print(f"  {status} {k}: {v}")
        all_ok = all(v for k, v in checks.items() if isinstance(v, bool))
        return all_ok
    except Exception as e:
        print(f"  ✗ Validation error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Solar data update pipeline")
    parser.add_argument("--scrape", action="store_true", help="Attempt live scrape")
    parser.add_argument("--days", type=int, default=1, help="Days of history")
    args = parser.parse_args()

    print(f"\n☀️  Solar Data Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    if args.scrape:
        run_scrape()

    run_generate(days=args.days)
    run_analytics()
    ok = validate_output()

    print(f"\n{'✅ Pipeline complete' if ok else '⚠️  Pipeline finished with warnings'}\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
