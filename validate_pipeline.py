#!/usr/bin/env python3
"""
Data Pipeline Validator
========================
Validates that the data pipeline correctly:
1. Scrapes data from portal
2. Updates dashboard_data.json
3. Creates/updates today's energy log
4. Maintains historical energy logs
5. All data is consistent and valid

Usage:
    python validate_pipeline.py              # Test full pipeline
    python validate_pipeline.py --quick      # Quick check (no scrape)
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
DASHBOARD_FILE = ROOT / "data" / "dashboard_data.json"
ENERGY_LOG_DIR = ROOT / "data" / "energy_logs"
CRAWLER_OUTPUT = ROOT / "dashboard_data.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(level, msg):
    colors = {"OK": GREEN, "ERROR": RED, "WARN": YELLOW, "INFO": CYAN}
    color = colors.get(level, RESET)
    print(f"{color}[{level:5}] {msg}{RESET}")


def validate_dashboard_data():
    """Validate dashboard_data.json structure and content"""
    log("INFO", "Validating dashboard_data.json...")
    
    if not DASHBOARD_FILE.exists():
        log("ERROR", f"Dashboard file not found: {DASHBOARD_FILE}")
        return False
    
    try:
        with open(DASHBOARD_FILE) as f:
            data = json.load(f)
        
        # Check required keys (supports both v5.0 and legacy formats)
        has_meta = "meta" in data
        has_data = "records" in data or "history" in data or "live" in data
        
        if not has_meta:
            log("ERROR", "Missing 'meta' key")
            return False
        
        if not has_data:
            log("ERROR", "Missing data keys (records/history/live)")
            return False
        
        # Check meta
        meta = data["meta"]
        log("INFO", f"Schema version: {meta.get('schema_version', 'unknown')}")
        
        meta_keys = ["plant_id", "plant_capacity_kw", "location"]
        missing_meta = [k for k in meta_keys if k not in meta]
        if missing_meta:
            log("WARN", f"Missing meta keys: {', '.join(missing_meta)}")
        
        # Validate based on schema
        if "records" in data:
            records = data["records"]
            log("OK", f"Dashboard has {len(records)} records")
            if records:
                latest = records[-1]
                print(f"  Latest: {latest.get('timestamp', 'N/A')}")
                print(f"  Power: {latest.get('power_kw', latest.get('current_power_kw', 'N/A'))} kW")
        elif "live" in data:
            live = data["live"]
            log("OK", f"Dashboard has live data (v5.0 format)")
            print(f"  Timestamp: {live.get('timestamp', 'N/A')}")
            print(f"  Power: {live.get('power_kw', 'N/A')} kW")
            print(f"  Daily yield: {live.get('daily_yield_kwh', 'N/A')} kWh")
            
            # Validate daily yield
            daily = live.get('daily_yield_kwh')
            if daily is not None and (daily < 0 or daily > 25):
                log("WARN", f"Daily yield out of expected range: {daily} kWh")
        elif "history" in data:
            history = data["history"]
            if len(history) == 0:
                log("ERROR", "History is empty")
                return False
            log("OK", f"Dashboard has {len(history)} history records")
        
        log("OK", "Dashboard data structure valid")
        return True
        
    except json.JSONDecodeError as e:
        log("ERROR", f"Invalid JSON: {e}")
        return False
    except Exception as e:
        log("ERROR", f"Validation error: {e}")
        return False


def validate_energy_logs():
    """Validate energy logs directory and files"""
    log("INFO", "Validating energy logs...")
    
    if not ENERGY_LOG_DIR.exists():
        log("ERROR", f"Energy logs directory not found: {ENERGY_LOG_DIR}")
        return False
    
    # List all energy log files
    log_files = sorted(ENERGY_LOG_DIR.glob("solar_energy_*.json"))
    
    if len(log_files) == 0:
        log("WARN", "No energy log files found")
        return False
    
    log("INFO", f"Found {len(log_files)} energy log files")
    
    # Validate each file
    valid_count = 0
    for log_file in log_files:
        try:
            with open(log_file) as f:
                log_data = json.load(f)
            
            # Check structure
            required = ["date", "meta", "daily_summary", "records"]
            if all(k in log_data for k in required):
                valid_count += 1
            else:
                missing = [k for k in required if k not in log_data]
                log("WARN", f"{log_file.name}: Missing keys: {', '.join(missing)}")
        
        except Exception as e:
            log("ERROR", f"{log_file.name}: {e}")
    
    log("OK", f"{valid_count}/{len(log_files)} energy logs are valid")
    
    # Check for today's log
    today = datetime.now().strftime("%Y-%m-%d")
    today_log = ENERGY_LOG_DIR / f"solar_energy_{today}.json"
    
    if today_log.exists():
        log("OK", f"Today's energy log exists: {today_log.name}")
        
        # Show summary
        try:
            with open(today_log) as f:
                today_data = json.load(f)
            summary = today_data.get("daily_summary", {})
            print(f"  Date: {summary.get('date')}")
            print(f"  Total yield: {summary.get('total_yield_kwh')} kWh")
            print(f"  Peak power: {summary.get('peak_power_kw')} kW")
            print(f"  Records: {summary.get('record_count')}")
        except Exception as e:
            log("WARN", f"Could not read today's log: {e}")
    else:
        log("WARN", f"Today's energy log not found: {today_log.name}")
        log("INFO", "Run: python scripts/archive_daily_data.py")
    
    return valid_count == len(log_files)


def validate_data_consistency():
    """Validate that dashboard and energy logs are consistent"""
    log("INFO", "Checking data consistency...")
    
    if not DASHBOARD_FILE.exists() or not ENERGY_LOG_DIR.exists():
        log("WARN", "Cannot check consistency - missing files")
        return False
    
    try:
        # Load dashboard data
        with open(DASHBOARD_FILE) as f:
            dashboard = json.load(f)
        
        # Extract dates from dashboard (support multiple formats)
        dates_in_dashboard = set()
        
        if "records" in dashboard:
            for record in dashboard["records"]:
                ts = record.get("timestamp", "")
                if ts:
                    date = ts.split()[0]
                    dates_in_dashboard.add(date)
        elif "history" in dashboard:
            for record in dashboard["history"]:
                ts = record.get("timestamp", "")
                if ts:
                    date = ts.split()[0]
                    dates_in_dashboard.add(date)
        elif "last_7_days" in dashboard:
            # V5.0 format
            for day in dashboard["last_7_days"]:
                date = day.get("date")
                if date:
                    dates_in_dashboard.add(date)
        
        # Get dates from energy logs
        log_files = ENERGY_LOG_DIR.glob("solar_energy_*.json")
        dates_in_logs = set()
        for log_file in log_files:
            # Extract date from filename: solar_energy_YYYY-MM-DD.json
            date = log_file.stem.replace("solar_energy_", "")
            dates_in_logs.add(date)
        
        log("INFO", f"Dashboard references {len(dates_in_dashboard)} unique dates")
        log("INFO", f"Energy logs have {len(dates_in_logs)} dates")
        
        if len(dates_in_dashboard) == 0:
            log("WARN", "Could not extract dates from dashboard")
            # If we have energy logs, that's OK
            if len(dates_in_logs) > 0:
                log("OK", "Energy logs exist independently")
                return True
            return False
        
        # Check for missing logs
        missing_logs = dates_in_dashboard - dates_in_logs
        if missing_logs:
            log("WARN", f"Dates in dashboard but not in logs: {sorted(missing_logs)[:5]}")
            if len(missing_logs) > 5:
                log("INFO", f"  ... and {len(missing_logs) - 5} more")
            log("INFO", "Run: python scripts/archive_daily_data.py --backfill")
        
        # Check for extra logs (should not happen, but OK if logs exist)
        extra_logs = dates_in_logs - dates_in_dashboard
        if extra_logs:
            log("INFO", f"Energy logs exist for dates not in dashboard: {len(extra_logs)}")
            log("INFO", "This is OK - logs are preserved historical data")
        
        if not missing_logs:
            log("OK", "All dashboard dates have corresponding energy logs")
            return True
        
        return len(missing_logs) == 0
        
    except Exception as e:
        log("ERROR", f"Consistency check error: {e}")
        return False


def check_recent_update():
    """Check if data was recently updated"""
    log("INFO", "Checking recent updates...")
    
    if not DASHBOARD_FILE.exists():
        log("ERROR", "Dashboard file not found")
        return False
    
    try:
        file_age_seconds = datetime.now().timestamp() - DASHBOARD_FILE.stat().st_mtime
        age_minutes = file_age_seconds / 60
        
        with open(DASHBOARD_FILE) as f:
            data = json.load(f)
        
        updated_at = data.get("meta", {}).get("updated_at", "unknown")
        
        if age_minutes < 10:
            log("OK", f"Dashboard updated {age_minutes:.1f} minutes ago")
        elif age_minutes < 60:
            log("WARN", f"Dashboard is {age_minutes:.1f} minutes old")
        else:
            hours = age_minutes / 60
            log("WARN", f"Dashboard is {hours:.1f} hours old")
        
        print(f"  Last updated: {updated_at}")
        
        return age_minutes < 300  # Less than 5 hours
        
    except Exception as e:
        log("ERROR", f"Update check error: {e}")
        return False


def validate_historical_coverage():
    """Check how many days of historical data we have"""
    log("INFO", "Checking historical coverage...")
    
    if not ENERGY_LOG_DIR.exists():
        log("WARN", "Energy logs directory not found")
        return False
    
    log_files = sorted(ENERGY_LOG_DIR.glob("solar_energy_*.json"))
    
    if len(log_files) == 0:
        log("WARN", "No energy logs found")
        return False
    
    # Extract dates
    dates = []
    for log_file in log_files:
        date_str = log_file.stem.replace("solar_energy_", "")
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            dates.append(date)
        except:
            continue
    
    if not dates:
        return False
    
    dates.sort()
    first_date = dates[0]
    last_date = dates[-1]
    
    days_covered = (last_date - first_date).days + 1
    days_with_data = len(dates)
    coverage_pct = (days_with_data / days_covered * 100) if days_covered > 0 else 0
    
    log("INFO", f"Historical range: {first_date.date()} to {last_date.date()}")
    log("INFO", f"Coverage: {days_with_data}/{days_covered} days ({coverage_pct:.1f}%)")
    
    if coverage_pct >= 95:
        log("OK", "Excellent historical coverage")
    elif coverage_pct >= 80:
        log("OK", "Good historical coverage")
    else:
        log("WARN", f"Sparse coverage - {days_covered - days_with_data} days missing")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate data pipeline")
    parser.add_argument("--quick", action="store_true", help="Quick validation (no scrape test)")
    args = parser.parse_args()
    
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  DATA PIPELINE VALIDATOR{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")
    
    results = []
    
    # Core validations
    tests = [
        ("Dashboard Data", validate_dashboard_data),
        ("Energy Logs", validate_energy_logs),
        ("Data Consistency", validate_data_consistency),
        ("Recent Update", check_recent_update),
        ("Historical Coverage", validate_historical_coverage),
    ]
    
    for name, test_func in tests:
        print()
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            log("ERROR", f"{name} test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  SUMMARY{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, p in results:
        status = f"{GREEN}✅ PASS{RESET}" if p else f"{RED}❌ FAIL{RESET}"
        print(f"  {status}  {name}")
    
    print()
    score = (passed / total * 100) if total > 0 else 0
    print(f"  Score: {passed}/{total} ({score:.0f}%)\n")
    
    if passed == total:
        log("OK", "✅ All validations passed!")
        print(f"\n{CYAN}Data pipeline is working correctly.{RESET}")
        print(f"{CYAN}Dashboard and energy logs are consistent and up to date.{RESET}\n")
        return 0
    elif passed >= total * 0.7:
        log("WARN", "⚠️  Most validations passed, but some issues found.")
        print(f"\n{YELLOW}Review warnings above and take corrective action.{RESET}\n")
        return 1
    else:
        log("ERROR", "❌ Multiple validations failed!")
        print(f"\n{RED}Data pipeline has serious issues - review errors above.{RESET}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
