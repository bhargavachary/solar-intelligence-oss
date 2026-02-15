#!/usr/bin/env python3
"""
Solar Data Update Pipeline — PRODUCTION
========================================
Tries to fetch REAL data from the Waaree digital portal first.
Falls back to simulated data only if the live scrape is unavailable.

Priority order:
  1. Scraper API  →  POST http://localhost:8006/trigger_scrape  (if running)
  2. Live scrape  →  waaree_deep_crawler.py  (Chrome + undetected-chromedriver)
  3. Simulation   →  scripts/generate_data.py  (tagged as "simulated" in output)

After data is fetched (by any method), the analytics engine runs to enrich
data/dashboard_data.json with statistics, forecasts, and health scores.

Usage:
    python scripts/update_data.py                      # auto: live → fallback sim
    python scripts/update_data.py --source live        # live only (fail if unavailable)
    python scripts/update_data.py --source simulate    # simulation only (for testing)
    python scripts/update_data.py --days 7             # simulation days (fallback only)
"""
import json
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "dashboard_data.json"
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
        print("  ⚠ waaree_deep_crawler.py not found")
        return False
    cred_file = ROOT / "credentials.json"
    if not cred_file.exists():
        print("  ⚠ credentials.json not found — skipping live scrape")
        return False
    print("  🔄 Starting live scrape from Waaree portal…")
    try:
        result = subprocess.run(
            [sys.executable, str(CRAWLER), "--validate", "--fresh-cycles", "1", "--reuse-cycles", "0"],
            capture_output=True, text=True, timeout=300, cwd=str(ROOT)
        )
        if result.returncode == 0:
            print("  ✓ Live scrape succeeded")
            for line in (result.stdout or "").strip().split("\n")[-3:]:
                print(f"    {line}")
            return True
        else:
            print(f"  ⚠ Scrape exited with code {result.returncode}")
            for line in (result.stderr or "").strip().split("\n")[-3:]:
                print(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        print("  ⚠ Live scrape timed out (5 min)")
        return False
    except Exception as e:
        print(f"  ⚠ Scrape error: {e}")
        return False


# ─── Data source: Simulation ──────────────────────────────
def run_simulation(days: int = 1) -> bool:
    """Generate synthetic data with scripts/generate_data.py."""
    gen_script = ROOT / "scripts" / "generate_data.py"
    if not gen_script.exists():
        print("  ⚠ generate_data.py not found")
        return False
    print(f"  🧪 Generating simulated data ({days} day{'s' if days > 1 else ''})…")
    result = subprocess.run(
        [sys.executable, str(gen_script), "--days", str(days)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if result.returncode == 0:
        print("  ✓ Simulation complete")
        for line in (result.stdout or "").strip().split("\n")[-3:]:
            print(f"    {line}")
        return True
    else:
        print(f"  ⚠ Simulation failed: {(result.stderr or '')[:200]}")
        return False


# ─── Analytics & Validation ──────────────────────────────
def run_analytics():
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
    """Quick validation of the generated data."""
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        checks = {
            "has_meta": "meta" in data,
            "has_history": "history" in data and len(data["history"]) > 0,
            "has_summary": "summary" in data,
            "has_analytics": "analytics" in data,
        }
        n = len(data.get("history", []))
        source = data.get("meta", {}).get("data_source", "?")
        all_ok = all(checks.values())
        status = "✓" if all_ok else "✗"
        print(f"  {status} Validation: {n} records, source={source}, "
              f"schema={data.get('meta', {}).get('schema_version', '?')}")
        return all_ok
    except Exception as e:
        print(f"  ✗ Validation error: {e}")
        return False


# ─── Main ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Solar data update pipeline")
    parser.add_argument("--source", choices=["live", "simulate", "auto"], default="auto",
                        help="Data source: live (portal only), simulate (test data), auto (try live → fallback)")
    parser.add_argument("--days", type=int, default=1,
                        help="Days of simulated data (only used in simulate/fallback)")
    args = parser.parse_args()

    print(f"\n{'═'*50}")
    print(f"☀️  Solar Data Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'═'*50}\n")

    success = False

    if args.source == "live":
        print("═══ Live Data (portal only) ═══")
        success = try_scraper_api() or try_live_scrape()
        if success:
            tag_data_source("live_portal")
        else:
            print("\n❌ Live scrape failed and --source=live was specified. No fallback.")
            sys.exit(1)

    elif args.source == "simulate":
        print("═══ Simulated Data (testing) ═══")
        success = run_simulation(args.days)
        if success:
            tag_data_source("simulated")

    else:  # auto
        print("═══ Attempting Live Data ═══")
        success = try_scraper_api()
        if success:
            tag_data_source("live_portal")
        if not success:
            success = try_live_scrape()
            if success:
                tag_data_source("live_portal")
        if not success:
            print("\n  📡 Live scrape unavailable — falling back to simulation\n")
            print("═══ Fallback: Simulated Data ═══")
            success = run_simulation(args.days)
            if success:
                tag_data_source("simulated")

    if not success:
        print("\n❌ All data sources failed")
        sys.exit(1)

    # Always enrich with analytics
    print("\n═══ Analytics Engine ═══")
    run_analytics()

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
        total_str = f"{total/1000:.2f} MWh" if total >= 1000 else f"{total:.1f} kWh"
        print(f"\n{'═'*50}")
        print(f"📊 Dashboard updated  •  Source: {source}")
        print(f"   {len(data.get('history', []))} records  •  "
              f"Latest: {latest.get('timestamp', '--')}")
        print(f"   Power: {latest.get('current_power_kw', '--')} kW  •  "
              f"Daily: {latest.get('daily_yield_kwh', '--')} kWh  •  "
              f"Lifetime: {total_str}")
        print(f"{'═'*50}\n")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
