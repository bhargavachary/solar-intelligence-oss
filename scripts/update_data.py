#!/usr/bin/env python3
"""
Solar Data Update Pipeline — PRODUCTION (Live Portal Only)
===========================================================
Fetches REAL data from the Waaree digital portal.
No simulation fallback — all data must come from the live portal.

The crawler (waaree_deep_crawler.py) writes to root `dashboard_data.json`.
This script copies the result to `data/dashboard_data.json` (consumed by
the GitHub Pages dashboard), then runs the analytics engine for enrichment.

Priority:
  1. Scraper API  →  POST http://localhost:8006/trigger_scrape  (if running)
  2. Live scrape  →  waaree_deep_crawler.py  (Chrome + undetected-chromedriver)

Usage:
    python scripts/update_data.py                 # auto: try API → live scrape
    python scripts/update_data.py --source live   # live only (explicit)
"""
import json
import shutil
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "dashboard_data.json"           # dashboard reads this
CRAWLER_OUTPUT = ROOT / "dashboard_data.json"                # crawler writes here
CRAWLER = ROOT / "waaree_deep_crawler.py"
SCRAPER_API_URL = "http://localhost:8006/trigger_scrape"

sys.path.insert(0, str(ROOT))


# ─── Data source: Scraper API ──────────────────────────────
def try_scraper_api() -> bool:
    """Trigger the scraper via its HTTP API (if the Flask server is running)."""
    try:
        import urllib.request
        req = urllib.request.Request(SCRAPER_API_URL, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            print(f"  ✓ Scraper API: {body.get('message', 'OK')}")
            return True
    except Exception:
        return False


# ─── Data source: Live scrape ──────────────────────────────
def try_live_scrape() -> bool:
    """Run waaree_deep_crawler.py directly (needs Chrome + credentials)."""
    if not CRAWLER.exists():
        print("  ✗ waaree_deep_crawler.py not found")
        return False
    cred_file = ROOT / "credentials.json"
    if not cred_file.exists():
        print("  ✗ credentials.json not found — cannot scrape")
        return False
    print("  🔄 Starting live scrape from Waaree portal…")
    try:
        result = subprocess.run(
            [sys.executable, str(CRAWLER),
             "--validate", "--fresh-cycles", "1", "--reuse-cycles", "0"],
            capture_output=True, text=True, timeout=300, cwd=str(ROOT)
        )
        if result.returncode == 0:
            print("  ✓ Live scrape succeeded")
            for line in (result.stdout or "").strip().split("\n")[-5:]:
                print(f"    {line}")
            return True
        else:
            print(f"  ✗ Scrape exited with code {result.returncode}")
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            for line in (stderr or stdout).split("\n")[-5:]:
                print(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        print("  ✗ Live scrape timed out (5 min)")
        return False
    except Exception as e:
        print(f"  ✗ Scrape error: {e}")
        return False


# ─── Copy crawler output to data/ ──────────────────────────
def sync_crawler_output() -> bool:
    """Copy root dashboard_data.json → data/dashboard_data.json."""
    if CRAWLER_OUTPUT.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CRAWLER_OUTPUT, DATA_FILE)
        print(f"  ✓ Synced crawler output → {DATA_FILE.relative_to(ROOT)}")
        return True
    else:
        print(f"  ✗ Crawler output not found at {CRAWLER_OUTPUT.relative_to(ROOT)}")
        return False


# ─── Analytics & Validation ──────────────────────────────
def enrich_analytics():
    """Run the analytics engine to enrich the dashboard JSON."""
    try:
        from solar_analytics import run_analytics as _run
        _run(str(DATA_FILE))
        print("  ✓ Analytics engine enriched data")
        return True
    except ImportError:
        print("  ⚠ solar_analytics.py not found — skipping enrichment")
        return False
    except Exception as e:
        print(f"  ⚠ Analytics error: {e}")
        return False


def tag_data_source(source: str):
    """Stamp the data source and timestamp into meta."""
    if not DATA_FILE.exists():
        return
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        data.setdefault("meta", {})["data_source"] = source
        data["meta"]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"  ⚠ Could not tag data source: {e}")


def validate_output() -> bool:
    """Validate the dashboard data has expected structure and sane values."""
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        history = data.get("history", [])
        meta = data.get("meta", {})
        checks = {
            "has_meta": bool(meta),
            "has_history": len(history) > 0,
            "has_summary": "summary" in data,
        }
        n = len(history)
        source = meta.get("data_source", "?")

        # Sanity checks on values
        if history:
            latest = history[-1]
            total = latest.get("total_yield_kwh", 0)
            daily = latest.get("daily_yield_kwh", 0)
            power = latest.get("current_power_kw", 0)
            checks["total_yield_reasonable"] = 0 <= total <= 50000  # under 50 MWh for a 2kW system
            checks["daily_yield_reasonable"] = 0 <= daily <= 25     # max ~20 kWh/day for 2.32kW
            checks["power_reasonable"] = 0 <= power <= 5            # under 5 kW

        all_ok = all(checks.values())
        status = "✓" if all_ok else "✗"
        failed = [k for k, v in checks.items() if not v]
        print(f"  {status} Validation: {n} records, source={source}")
        if failed:
            print(f"    Failed checks: {', '.join(failed)}")
        return all_ok
    except Exception as e:
        print(f"  ✗ Validation error: {e}")
        return False


# ─── Main ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Solar data update — live portal only")
    parser.add_argument("--source", choices=["live", "auto"], default="auto",
                        help="Data source (both try live portal)")
    args = parser.parse_args()

    print(f"\n{'═'*50}")
    print(f"☀️  Solar Data Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'═'*50}\n")

    # Try scraper API first, then direct live scrape
    print("═══ Fetching Live Portal Data ═══")
    success = try_scraper_api()
    if not success:
        success = try_live_scrape()

    if not success:
        print("\n❌ Could not fetch live data from Waaree portal.")
        print("   Ensure Chrome is available and credentials.json is valid.")
        sys.exit(1)

    # Sync crawler output to data/ directory
    print("\n═══ Syncing Data ═══")
    if not sync_crawler_output():
        # Crawler may have written directly to data/ via modified path
        if not DATA_FILE.exists():
            print("\n❌ No data file found after scrape")
            sys.exit(1)

    # Tag source
    tag_data_source("live_portal")

    # Enrich with analytics
    print("\n═══ Analytics Engine ═══")
    enrich_analytics()
    
    # Archive today's data (immutable daily snapshot)
    print("\n═══ Daily Archive ═══")
    try:
        archive_cmd = [sys.executable, str(ROOT / "scripts" / "archive_daily_data.py")]
        result = subprocess.run(archive_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            for line in (result.stdout or "").strip().split("\n")[-3:]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"  ⚠️  Archive failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠️  Archive error: {e}")
    
    # Build lightweight dashboard summary
    print("\n═══ Dashboard Summary ═══")
    try:
        builder_cmd = [sys.executable, str(ROOT / "scripts" / "build_dashboard_summary.py")]
        result = subprocess.run(builder_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            for line in (result.stdout or "").strip().split("\n")[-3:]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"  ⚠️  Builder failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠️  Builder error: {e}")

    # Validate
    print("\n═══ Validation ═══")
    ok = validate_output()

    # Summary
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            data = json.load(f)
        latest = data.get("history", [{}])[-1]
        source = data.get("meta", {}).get("data_source", "unknown")
        total = latest.get("total_yield_kwh", 0)
        daily = latest.get("daily_yield_kwh", 0)
        print(f"\n{'═'*50}")
        print(f"📊 Dashboard updated  •  Source: {source}")
        print(f"   {len(data.get('history', []))} records  •  "
              f"Latest: {latest.get('timestamp', '--')}")
        print(f"   Power: {latest.get('current_power_kw', '--')} kW  •  "
              f"Daily: {daily} kWh  •  "
              f"Lifetime: {total} kWh")
        print(f"{'═'*50}\n")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
