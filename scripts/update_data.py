#!/usr/bin/env python3
"""
Solar Data Update Pipeline — PRODUCTION (Live Portal Only)
===========================================================
Fetches REAL data from the Waaree digital portal.
No simulation fallback — all data must come from the live portal.

The crawler (waaree_deep_crawler.py) writes to root `dashboard_data.json`.
This script copies the result to `data/dashboard_data.json` (consumed by
the GitHub Pages dashboard), then runs the analytics engine for enrichment.

Fallback chain (5 levels, tried in order until one succeeds):
  1. Scraper API      →  POST to local Flask server (if running)
  2. Session reuse    →  waaree_deep_crawler.py with cached session cookies
  3. Fresh login      →  waaree_deep_crawler.py with full login flow
  4. Browser restart  →  Kill browser, restart with fresh profile, fresh login
  5. Extended timeout  →  Longer timeout, extra retries inside crawler

Each level uses exponential backoff between attempts.

Usage:
    python scripts/update_data.py                 # auto: full fallback chain
    python scripts/update_data.py --source live   # live only (skip API)
"""
import json
import shutil
import sys
import os
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "dashboard_data.json"           # dashboard reads this
CRAWLER_OUTPUT = ROOT / "dashboard_data.json"                # crawler writes here
CRAWLER = ROOT / "waaree_deep_crawler.py"
SESSION_FILE = ROOT / "waaree_session.pkl"
SCRAPER_API_URL = "http://localhost:8006/trigger_scrape"

sys.path.insert(0, str(ROOT))


def _crawler_available() -> bool:
    """Check that the crawler script and credentials exist."""
    if not CRAWLER.exists():
        print("  ✗ waaree_deep_crawler.py not found")
        return False
    cred_file = ROOT / "credentials.json"
    if not cred_file.exists():
        print("  ✗ credentials.json not found — cannot scrape")
        return False
    return True


def _run_crawler(args_list, timeout=300, label="scrape") -> bool:
    """Run the crawler with the given arguments and return success status."""
    print(f"  🔄 Starting {label}…")
    try:
        result = subprocess.run(
            [sys.executable, str(CRAWLER)] + args_list,
            capture_output=True, text=True, timeout=timeout, cwd=str(ROOT)
        )
        if result.returncode == 0:
            print(f"  ✓ {label} succeeded")
            for line in (result.stdout or "").strip().split("\n")[-5:]:
                if line.strip():
                    print(f"    {line}")
            return True
        else:
            print(f"  ✗ {label} exited with code {result.returncode}")
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            for line in (stderr or stdout).split("\n")[-5:]:
                if line.strip():
                    print(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ✗ {label} timed out ({timeout}s)")
        return False
    except Exception as e:
        print(f"  ✗ {label} error: {e}")
        return False


# ─── Fallback 1: Scraper API ──────────────────────────────
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


# ─── Fallback 2: Session reuse scrape ─────────────────────
def try_session_reuse_scrape() -> bool:
    """Run crawler reusing a cached session (faster, avoids fresh login)."""
    if not _crawler_available():
        return False
    if not SESSION_FILE.exists():
        print("  ⚠ No cached session found — skipping session reuse")
        return False
    # Check session age (skip if older than 4 hours)
    try:
        age_hours = (time.time() - SESSION_FILE.stat().st_mtime) / 3600
        if age_hours > 4:
            print(f"  ⚠ Session expired ({age_hours:.1f}h old) — skipping reuse")
            return False
        print(f"  ℹ Session is {age_hours:.1f}h old — attempting reuse")
    except Exception:
        pass
    return _run_crawler(
        ["--validate", "--fresh-cycles", "0", "--reuse-cycles", "1"],
        timeout=180, label="session reuse scrape"
    )


# ─── Fallback 3: Fresh login scrape ──────────────────────
def try_fresh_login_scrape() -> bool:
    """Run crawler with a full fresh login (standard approach)."""
    if not _crawler_available():
        return False
    return _run_crawler(
        ["--validate", "--fresh-cycles", "1", "--reuse-cycles", "0"],
        timeout=300, label="fresh login scrape"
    )


# ─── Fallback 4: Browser restart + fresh login ───────────
def try_browser_restart_scrape() -> bool:
    """Invalidate session, then run crawler with fresh login.

    This clears any stale session state that might be causing failures,
    forcing a completely clean browser start.
    """
    if not _crawler_available():
        return False
    # Remove stale session to force a truly clean start
    if SESSION_FILE.exists():
        try:
            SESSION_FILE.unlink()
            print("  ℹ Cleared stale session file")
        except Exception:
            pass
    # Also clear diagnostics that might confuse the crawler
    diag_dir = ROOT / "diagnostics"
    if diag_dir.exists():
        try:
            for f in list(diag_dir.glob("*.html"))[-20:]:
                f.unlink(missing_ok=True)
            print("  ℹ Cleared recent diagnostic files")
        except Exception:
            pass
    return _run_crawler(
        ["--validate", "--fresh-cycles", "1", "--reuse-cycles", "0"],
        timeout=300, label="browser restart scrape"
    )


# ─── Fallback 5: Extended timeout with extra retries ─────
def try_extended_scrape() -> bool:
    """Run crawler with extended timeout and multiple fresh+reuse cycles.

    This is the last-resort scrape: gives the crawler the maximum number
    of internal retries and a longer timeout to handle slow networks,
    portal rate-limiting, or WAF back-off delays.
    """
    if not _crawler_available():
        return False
    # Clear session again to start truly fresh
    if SESSION_FILE.exists():
        try:
            SESSION_FILE.unlink()
        except Exception:
            pass
    return _run_crawler(
        ["--validate", "--fresh-cycles", "2", "--reuse-cycles", "1"],
        timeout=480, label="extended scrape (last resort)"
    )


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
        
        schema = data.get("meta", {}).get("schema_version", "unknown")
        
        # Handle both v4.0 (crawler) and v5.0 (build_dashboard_summary) schemas
        if schema == "5.0":
            # v5.0 schema: live, last_7_days, monthly, analytics
            live = data.get("live", {})
            last7 = data.get("last_7_days", [])
            checks = {
                "has_meta": bool(data.get("meta")),
                "has_live": bool(live),
                "has_last_7_days": len(last7) > 0,
            }
            if live:
                checks["power_reasonable"] = 0 <= live.get("power_kw", 0) <= 5
                checks["daily_reasonable"] = 0 <= live.get("daily_yield_kwh", 0) <= 25
                checks["total_reasonable"] = 0 <= live.get("total_yield_kwh", 0) <= 50000
            n = len(last7)
            source = data.get("meta", {}).get("data_source", "?")
        else:
            # v4.0 schema: meta, summary, history
            history = data.get("history", [])
            checks = {
                "has_meta": bool(data.get("meta")),
                "has_history": len(history) > 0,
                "has_summary": "summary" in data,
            }
            n = len(history)
            source = data.get("meta", {}).get("data_source", "?")
            if history:
                latest = history[-1]
                checks["total_yield_reasonable"] = 0 <= latest.get("total_yield_kwh", 0) <= 50000
                checks["daily_yield_reasonable"] = 0 <= latest.get("daily_yield_kwh", 0) <= 25
                checks["power_reasonable"] = 0 <= latest.get("current_power_kw", 0) <= 5

        all_ok = all(checks.values())
        status = "✓" if all_ok else "✗"
        failed = [k for k, v in checks.items() if not v]
        print(f"  {status} Validation: schema={schema}, {n} records/days, source={source}")
        if failed:
            print(f"    Failed checks: {', '.join(failed)}")
        return all_ok
    except Exception as e:
        print(f"  ✗ Validation error: {e}")
        return False


# ─── Fallback chain executor ─────────────────────────────
def fetch_with_fallbacks(skip_api=False) -> tuple:
    """Execute the 5-level fallback chain with exponential backoff.

    Returns (success: bool, source_label: str) indicating which
    fallback level succeeded (or that all failed).
    """
    # Define fallback levels in priority order.
    # Each entry: (label, function, backoff_seconds_before_next)
    fallbacks = [
        ("Scraper API",          try_scraper_api,           5),
        ("Session reuse",        try_session_reuse_scrape, 10),
        ("Fresh login",          try_fresh_login_scrape,   15),
        ("Browser restart",      try_browser_restart_scrape, 20),
        ("Extended (last resort)", try_extended_scrape,      0),
    ]

    if skip_api:
        fallbacks = [f for f in fallbacks if f[0] != "Scraper API"]

    total = len(fallbacks)
    for idx, (label, func, backoff) in enumerate(fallbacks, 1):
        print(f"\n  ── Fallback {idx}/{total}: {label} ──")
        try:
            success = func()
        except Exception as e:
            print(f"  ✗ {label} raised exception: {e}")
            success = False

        if success:
            return True, label

        if idx < total and backoff > 0:
            print(f"  ⏳ Waiting {backoff}s before next fallback…")
            time.sleep(backoff)

    return False, "none"


# ─── Main ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Solar data update — live portal only")
    parser.add_argument("--source", choices=["live", "auto"], default="auto",
                        help="Data source (both try live portal)")
    args = parser.parse_args()

    skip_api = (args.source == "live")

    print(f"\n{'═'*50}")
    print(f"☀️  Solar Data Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'═'*50}\n")

    print("═══ Fetching Live Portal Data (5-level fallback) ═══")
    success, source_label = fetch_with_fallbacks(skip_api=skip_api)

    if not success:
        print("\n❌ Could not fetch live data from Waaree portal.")
        print("   All 5 fallback levels exhausted:")
        print("     1. Scraper API")
        print("     2. Session reuse scrape")
        print("     3. Fresh login scrape")
        print("     4. Browser restart scrape")
        print("     5. Extended timeout scrape")
        print("   Ensure Chrome is available and credentials.json is valid.")
        sys.exit(1)

    print(f"\n  ✓ Data fetched via: {source_label}")

    # Sync crawler output to data/ directory
    print("\n═══ Syncing Data ═══")
    if not sync_crawler_output():
        # Crawler may have written directly to data/ via modified path
        if not DATA_FILE.exists():
            print("\n❌ No data file found after scrape")
            sys.exit(1)

    # Tag source
    tag_data_source(f"live_portal/{source_label}")

    # Log today's data FIRST (merge records into daily energy log)
    # This must happen BEFORE build_dashboard_summary so the fresh data
    # is available in energy_logs for the v5.0 rebuild.
    print("\n═══ Daily Energy Log ═══")
    try:
        log_cmd = [sys.executable, str(ROOT / "scripts" / "archive_daily_data.py")]
        result = subprocess.run(log_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            for line in (result.stdout or "").strip().split("\n")[-3:]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"  ⚠️  Logging failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠️  Logging error: {e}")

    # Rebuild dashboard summary (v5.0 schema) from all energy_logs
    # This aggregates all days including today's freshly archived data
    # and writes the proper v5.0 format to data/dashboard_data.json
    print("\n═══ Dashboard Summary (v5.0) ═══")
    try:
        build_cmd = [sys.executable, str(ROOT / "scripts" / "build_dashboard_summary.py")]
        result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            for line in (result.stdout or "").strip().split("\n")[-3:]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"  ⚠️  Summary build failed: {result.stderr[:200]}")
            print("  ℹ️  Keeping v4.0 crawler output as dashboard data")
    except Exception as e:
        print(f"  ⚠️  Summary build error: {e}")
        print("  ℹ️  Keeping v4.0 crawler output as dashboard data")

    # Enrich with analytics
    print("\n═══ Analytics Engine ═══")
    enrich_analytics()

    # Validate
    print("\n═══ Validation ═══")
    ok = validate_output()

    # Summary
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            data = json.load(f)
        schema = data.get("meta", {}).get("schema_version", "?")
        source = data.get("meta", {}).get("data_source", "unknown")
        
        if schema == "5.0":
            live = data.get("live", {})
            n_days = len(data.get("last_7_days", []))
            print(f"\n{'═'*50}")
            print(f"📊 Dashboard updated (v5.0)  •  Source: {source}")
            print(f"   {n_days} days  •  Latest: {live.get('timestamp', '--')}")
            print(f"   Power: {live.get('power_kw', '--')} kW  •  "
                  f"Daily: {live.get('daily_yield_kwh', 0)} kWh  •  "
                  f"Lifetime: {live.get('total_yield_kwh', 0)} kWh")
            print(f"{'═'*50}\n")
        else:
            latest = data.get("history", [{}])[-1]
            print(f"\n{'═'*50}")
            print(f"📊 Dashboard updated (v{schema})  •  Source: {source}")
            print(f"   {len(data.get('history', []))} records  •  "
                  f"Latest: {latest.get('timestamp', '--')}")
            print(f"   Power: {latest.get('current_power_kw', '--')} kW  •  "
                  f"Daily: {latest.get('daily_yield_kwh', 0)} kWh  •  "
                  f"Lifetime: {latest.get('total_yield_kwh', 0)} kWh")
            print(f"{'═'*50}\n")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
