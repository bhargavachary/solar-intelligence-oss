#!/usr/bin/env python3
"""
GitHub Workflow Logic Validator
================================
Validates the workflow logic and configuration without requiring Chrome.
Tests:
1. YAML syntax validity
2. Cron schedule parsing
3. Session file age calculation logic
4. File paths and structure
5. Git operations readiness

This is a lightweight pre-flight check before deployment.
"""

import os
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "update-solar-data.yml"
CREDENTIALS_FILE = ROOT / "credentials.json"
SESSION_FILE = ROOT / "waaree_session.pkl"

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


def test_workflow_yaml():
    """Test if workflow YAML is valid"""
    log("INFO", "Testing workflow YAML syntax...")
    
    if not WORKFLOW_FILE.exists():
        log("ERROR", f"Workflow file not found: {WORKFLOW_FILE}")
        return False
    
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check required keys ('on' is the trigger key in GitHub Actions)
        required = ['name', 'jobs']
        for key in required:
            if key not in workflow:
                log("ERROR", f"Missing required key '{key}' in workflow")
                return False
        
        # Check for 'on' key (GitHub Actions trigger)
        if 'on' not in workflow and True not in workflow:
            log("ERROR", "Missing workflow trigger ('on' key)")
            return False
        
        log("OK", "Workflow YAML is valid")
        
        # Check schedule - handle both 'on' and True as key
        trigger = workflow.get('on') or workflow.get(True)
        if trigger and 'schedule' in trigger:
            crons = trigger['schedule']
            log("INFO", f"Found {len(crons)} scheduled run(s):")
            for cron_spec in crons:
                print(f"    {cron_spec['cron']}")
        
        return True
        
    except yaml.YAMLError as e:
        log("ERROR", f"YAML parsing error: {e}")
        return False
    except Exception as e:
        log("ERROR", f"Unexpected error: {e}")
        return False


def test_cron_schedules():
    """Validate cron schedule makes sense"""
    log("INFO", "Validating cron schedules...")
    
    with open(WORKFLOW_FILE, 'r') as f:
        workflow = yaml.safe_load(f)
    
    # Handle 'on' being parsed as True by PyYAML
    trigger = workflow.get('on') or workflow.get(True)
    
    if not trigger or 'schedule' not in trigger:
        log("WARN", "No schedule found in workflow")
        return True
    
    cron_expr = trigger['schedule'][0]['cron']
    parts = cron_expr.split()
    
    if len(parts) != 5:
        log("ERROR", f"Invalid cron expression: {cron_expr}")
        return False
    
    minutes, hours, day_of_month, month, day_of_week = parts
    
    log("OK", f"Cron schedule valid: {cron_expr}")
    
    # Parse hours
    if ',' in hours:
        hour_list = [int(h) for h in hours.split(',')]
        log("INFO", f"Runs at UTC hours: {hour_list}")
        ist_hours = [(h + 5) % 24 + (1 if (h + 5) >= 24 else 0) for h in hour_list]
        log("INFO", f"Corresponding IST hours (UTC+5:30): {ist_hours}")
    
    return True


def test_session_age_logic():
    """Test session age calculation logic"""
    log("INFO", "Testing session age logic...")
    
    if not SESSION_FILE.exists():
        log("WARN", "Session file doesn't exist (this is OK for first run)")
        return True
    
    file_age_seconds = datetime.now().timestamp() - SESSION_FILE.stat().st_mtime
    age_hours = file_age_seconds / 3600
    
    log("INFO", f"Current session age: {age_hours:.1f} hours")
    
    if age_hours > 4:
        log("OK", "Session correctly identified as expired (>4 hours)")
        recommended_action = "fresh login"
    else:
        log("OK", "Session valid (<4 hours) - can reuse")
        recommended_action = "session reuse"
    
    log("INFO", f"Recommended action: {recommended_action}")
    return True


def test_file_structure():
    """Test if required files and directories exist"""
    log("INFO", "Testing file structure...")
    
    required_files = [
        ROOT / "waaree_deep_crawler.py",
        ROOT / "requirements.txt",
        ROOT / ".gitignore",
    ]
    
    required_dirs = [
        ROOT / ".github" / "workflows",
        ROOT / "data",
        ROOT / "diagnostics",
    ]
    
    all_good = True
    
    for file_path in required_files:
        if not file_path.exists():
            log("ERROR", f"Missing: {file_path.relative_to(ROOT)}")
            all_good = False
    
    for dir_path in required_dirs:
        if not dir_path.exists():
            log("WARN", f"Missing directory: {dir_path.relative_to(ROOT)}")
            dir_path.mkdir(parents=True, exist_ok=True)
            log("INFO", f"Created: {dir_path.relative_to(ROOT)}")
    
    if all_good:
        log("OK", "File structure is correct")
    
    return all_good


def test_git_readiness():
    """Test if repository is ready for automated commits"""
    log("INFO", "Testing Git configuration...")
    
    import subprocess
    
    try:
        # Check if it's a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=ROOT
        )
        
        if result.returncode != 0:
            log("ERROR", "Not a Git repository")
            return False
        
        # Check if there's a remote
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            cwd=ROOT
        )
        
        if not result.stdout.strip():
            log("WARN", "No Git remote configured")
            return False
        
        # Get remote URL
        lines = result.stdout.strip().split('\n')
        origin = [l for l in lines if l.startswith('origin')]
        if origin:
            remote_url = origin[0].split()[1]
            log("OK", f"Git remote: {remote_url}")
        
        # Check current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=ROOT
        )
        
        branch = result.stdout.strip()
        log("INFO", f"Current branch: {branch}")
        
        return True
        
    except Exception as e:
        log("ERROR", f"Git check failed: {e}")
        return False


def test_secrets_needed():
    """List secrets that need to be configured in GitHub"""
    log("INFO", "Checking required GitHub secrets...")
    
    required_secrets = [
        "WAAREE_USERNAME",
        "WAAREE_PASSWORD",
        "WAAREE_PLANT_ID"
    ]
    
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                creds = json.load(f)
            
            log("OK", "credentials.json found locally")
            log("INFO", "GitHub Secrets needed:")
            for secret in required_secrets:
                key = secret.replace("WAAREE_", "").lower()
                if key in creds:
                    value = creds[key]
                    masked = value[:2] + "***" if len(value) > 2 else "***"
                    print(f"    {secret}: {masked}")
                else:
                    print(f"    {secret}: NOT FOUND")
                    log("WARN", f"  Missing in credentials.json: {key}")
            
            return True
        except Exception as e:
            log("ERROR", f"Error reading credentials: {e}")
            return False
    else:
        log("ERROR", "credentials.json not found")
        log("INFO", "You need to configure these GitHub Secrets:")
        for secret in required_secrets:
            print(f"    {secret}")
        return False


def main():
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  GITHUB WORKFLOW PRE-FLIGHT VALIDATOR{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")
    
    tests = [
        ("Workflow YAML", test_workflow_yaml),
        ("Cron Schedules", test_cron_schedules),
        ("Session Age Logic", test_session_age_logic),
        ("File Structure", test_file_structure),
        ("Git Configuration", test_git_readiness),
        ("GitHub Secrets", test_secrets_needed),
    ]
    
    results = []
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
    print(f"  Score: {passed}/{total} tests passed\n")
    
    if passed == total:
        log("OK", "✅ All checks passed! Workflow is ready for deployment.")
        print(f"\n{YELLOW}Next steps:{RESET}")
        print("  1. Configure GitHub Secrets (if not already done)")
        print("  2. git add .github/workflows/update-solar-data.yml")
        print("  3. git commit -m 'Add automated data scraping workflow'")
        print("  4. git push")
        print("  5. Monitor GitHub Actions tab for first run\n")
        return 0
    else:
        log("ERROR", "❌ Some checks failed. Fix issues before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
