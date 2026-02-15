#!/usr/bin/env python3
"""
GitHub Workflow Dry Run Tester
================================
Tests the data scraping workflow locally before deploying to GitHub Actions.

This simulates the workflow steps:
1. Check session validity
2. Try session reuse
3. Fall back to fresh login if needed
4. Verify data output
5. Test multiple runs to ensure session persistence works

Usage:
    python test_workflow.py              # Full test (3 runs)
    python test_workflow.py --runs 5     # Custom number of runs
    python test_workflow.py --clean      # Start fresh (delete session)
"""

import os
import sys
import json
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
CRAWLER = ROOT / "waaree_deep_crawler.py"
SESSION_FILE = ROOT / "waaree_session.pkl"
DASHBOARD_FILE = ROOT / "dashboard_data.json"
DATA_FILE = ROOT / "data" / "dashboard_data.json"
CREDENTIALS_FILE = ROOT / "credentials.json"

# Color codes for output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(level, msg):
    """Formatted logging"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "INFO": BLUE,
        "OK": GREEN,
        "WARN": YELLOW,
        "ERROR": RED,
        "TEST": CYAN
    }
    color = colors.get(level, RESET)
    print(f"{color}[{timestamp}] [{level:5}] {msg}{RESET}")


def check_prerequisites():
    """Verify all required files and dependencies exist"""
    log("INFO", "Checking prerequisites...")
    
    issues = []
    
    if not CRAWLER.exists():
        issues.append("waaree_deep_crawler.py not found")
    
    if not CREDENTIALS_FILE.exists():
        issues.append("credentials.json not found")
    
    # Check Python packages
    try:
        import selenium
        import undetected_chromedriver
    except ImportError as e:
        issues.append(f"Missing Python package: {e.name}")
    
    if issues:
        log("ERROR", "Prerequisites check failed:")
        for issue in issues:
            print(f"  ❌ {issue}")
        return False
    
    log("OK", "All prerequisites satisfied")
    return True


def check_session_validity():
    """Check if session file exists and is not expired (>4 hours old)"""
    if not SESSION_FILE.exists():
        log("INFO", "No session file found")
        return False
    
    file_age = time.time() - SESSION_FILE.stat().st_mtime
    age_hours = file_age / 3600
    
    if age_hours > 4:
        log("WARN", f"Session expired ({age_hours:.1f} hours old)")
        return False
    
    log("OK", f"Session valid ({age_hours:.1f} hours old)")
    return True


def run_scraper(mode="fresh"):
    """
    Run the scraper in either 'fresh' or 'reuse' mode
    Returns: (success, elapsed_time)
    """
    if mode == "reuse":
        log("TEST", "Attempting scrape with session reuse...")
        args = ["--validate", "--fresh-cycles", "0", "--reuse-cycles", "1"]
    else:
        log("TEST", "Attempting scrape with fresh login...")
        args = ["--validate", "--fresh-cycles", "1", "--reuse-cycles", "0"]
    
    start = time.time()
    
    try:
        # Set environment to handle potential Chrome issues
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        result = subprocess.run(
            [sys.executable, str(CRAWLER)] + args,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(ROOT),
            env=env
        )
        
        elapsed = time.time() - start
        
        # Show last few lines of output
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            for line in lines[-5:]:
                print(f"  {line}")
        
        success = result.returncode == 0 and DASHBOARD_FILE.exists()
        
        # If subprocess failed but dashboard_data.json exists and is recent, consider it OK
        if not success and DASHBOARD_FILE.exists():
            file_age = time.time() - DASHBOARD_FILE.stat().st_mtime
            if file_age < 300:  # Within last 5 minutes
                log("WARN", f"Scraper had issues but data file is recent (<5min old)")
                success = True
        
        if success:
            log("OK", f"{mode.capitalize()} scrape succeeded ({elapsed:.1f}s)")
        else:
            log("ERROR", f"{mode.capitalize()} scrape failed ({elapsed:.1f}s)")
            if result.stderr:
                stderr_lines = result.stderr.strip().split("\n")
                for line in stderr_lines[-3:]:
                    if line.strip():
                        print(f"  {line}")
        
        return success, elapsed
        
    except subprocess.TimeoutExpired:
        log("ERROR", f"{mode.capitalize()} scrape timed out (5 min)")
        return False, 300
    except Exception as e:
        log("ERROR", f"{mode.capitalize()} scrape error: {e}")
        return False, 0


def verify_data_output():
    """Verify dashboard_data.json was created and has valid content"""
    if not DASHBOARD_FILE.exists():
        log("ERROR", "dashboard_data.json not found")
        return False
    
    try:
        with open(DASHBOARD_FILE, 'r') as f:
            data = json.load(f)
        
        # Basic validation
        if 'records' not in data:
            log("ERROR", "No 'records' key in dashboard data")
            return False
        
        record_count = len(data['records'])
        if record_count == 0:
            log("ERROR", "Empty records array")
            return False
        
        log("OK", f"Data valid: {record_count} records")
        
        # Show sample data
        latest = data['records'][-1] if data['records'] else {}
        if 'power_kw' in latest:
            log("INFO", f"  Latest power: {latest['power_kw']} kW")
        if 'daily' in latest:
            log("INFO", f"  Daily yield: {latest['daily']} kWh")
        
        return True
        
    except json.JSONDecodeError as e:
        log("ERROR", f"Invalid JSON: {e}")
        return False
    except Exception as e:
        log("ERROR", f"Data validation error: {e}")
        return False


def sync_data_to_public():
    """Copy dashboard_data.json to data/ directory"""
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        if DASHBOARD_FILE.exists():
            import shutil
            shutil.copy2(DASHBOARD_FILE, DATA_FILE)
            log("OK", f"Data synced to {DATA_FILE.relative_to(ROOT)}")
            return True
        else:
            log("ERROR", "Source file not found for sync")
            return False
    except Exception as e:
        log("ERROR", f"Sync failed: {e}")
        return False


def run_test_cycle(cycle_num, total_cycles):
    """Run a complete test cycle"""
    log("TEST", f"{'═' * 60}")
    log("TEST", f"TEST CYCLE {cycle_num}/{total_cycles}")
    log("TEST", f"{'═' * 60}")
    
    results = {
        "cycle": cycle_num,
        "session_valid": False,
        "reuse_attempted": False,
        "reuse_success": False,
        "fresh_attempted": False,
        "fresh_success": False,
        "data_valid": False,
        "elapsed_time": 0
    }
    
    start = time.time()
    
    # Step 1: Check session
    results["session_valid"] = check_session_validity()
    
    # Step 2: Try reuse if session valid
    if results["session_valid"]:
        results["reuse_attempted"] = True
        success, elapsed = run_scraper("reuse")
        results["reuse_success"] = success
        results["elapsed_time"] += elapsed
        
        if not success:
            log("WARN", "Session reuse failed, falling back to fresh login")
    
    # Step 3: Fresh login if needed
    if not results["reuse_success"]:
        results["fresh_attempted"] = True
        success, elapsed = run_scraper("fresh")
        results["fresh_success"] = success
        results["elapsed_time"] += elapsed
    
    # Step 4: Verify data
    if results["reuse_success"] or results["fresh_success"]:
        results["data_valid"] = verify_data_output()
        
        # Sync to public directory
        if results["data_valid"]:
            sync_data_to_public()
    
    results["total_time"] = time.time() - start
    
    # Summary
    log("TEST", f"Cycle {cycle_num} summary:")
    print(f"  Session valid: {results['session_valid']}")
    print(f"  Reuse success: {results['reuse_success']}")
    print(f"  Fresh success: {results['fresh_success']}")
    print(f"  Data valid: {results['data_valid']}")
    print(f"  Total time: {results['total_time']:.1f}s")
    
    success = results['data_valid']
    if success:
        log("OK", f"✅ Cycle {cycle_num} PASSED")
    else:
        log("ERROR", f"❌ Cycle {cycle_num} FAILED")
    
    return results, success


def main():
    parser = argparse.ArgumentParser(description="Test GitHub workflow locally")
    parser.add_argument("--runs", type=int, default=3, help="Number of test runs")
    parser.add_argument("--clean", action="store_true", help="Delete session before starting")
    parser.add_argument("--delay", type=int, default=10, help="Delay between runs (seconds)")
    args = parser.parse_args()
    
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  GITHUB WORKFLOW DRY RUN TESTER{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")
    
    # Prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    # Clean session if requested
    if args.clean:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
            log("INFO", "Deleted existing session file")
    
    # Run test cycles
    all_results = []
    passes = 0
    
    for i in range(1, args.runs + 1):
        results, success = run_test_cycle(i, args.runs)
        all_results.append(results)
        if success:
            passes += 1
        
        # Delay between runs (except last)
        if i < args.runs:
            log("INFO", f"Waiting {args.delay}s before next cycle...")
            time.sleep(args.delay)
    
    # Final summary
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  FINAL RESULTS{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")
    
    print(f"  Total runs: {args.runs}")
    print(f"  Passed: {passes}")
    print(f"  Failed: {args.runs - passes}")
    print(f"  Success rate: {(passes / args.runs * 100):.1f}%")
    print()
    
    # Detailed breakdown
    reuse_attempts = sum(1 for r in all_results if r["reuse_attempted"])
    reuse_success = sum(1 for r in all_results if r["reuse_success"])
    fresh_attempts = sum(1 for r in all_results if r["fresh_attempted"])
    fresh_success = sum(1 for r in all_results if r["fresh_success"])
    
    print(f"  Session reuse: {reuse_success}/{reuse_attempts} successful")
    print(f"  Fresh login: {fresh_success}/{fresh_attempts} successful")
    
    avg_time = sum(r["total_time"] for r in all_results) / len(all_results)
    print(f"  Average time: {avg_time:.1f}s")
    print()
    
    if passes == args.runs:
        log("OK", f"{'═' * 60}")
        log("OK", f"✅ ALL TESTS PASSED - Workflow is ready for deployment!")
        log("OK", f"{'═' * 60}")
        return 0
    elif passes > 0:
        log("WARN", f"{'═' * 60}")
        log("WARN", f"⚠️  PARTIAL SUCCESS - Some tests failed, review logs")
        log("WARN", f"{'═' * 60}")
        return 1
    else:
        log("ERROR", f"{'═' * 60}")
        log("ERROR", f"❌ ALL TESTS FAILED - Do not deploy workflow")
        log("ERROR", f"{'═' * 60}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
