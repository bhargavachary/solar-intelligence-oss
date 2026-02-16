# 🤖 Local Automation Setup - Complete Guide

## ✅ Status: FIXED AND ACTIVE

**Issue:** Cron jobs were pointing to wrong directory (`waaree_api_access` → `solar_intelligence`)
**Fixed:** All paths corrected, two automation options now available.

---

## 📋 Two Options Available

You can choose **cron** (simple) or **launchd** (recommended for macOS).

### Option 1: Cron (Currently Active ✅)

**Status:** Already installed and running

Traditional UNIX scheduler - simple and works well.

**Check if running:**
```bash
crontab -l
```

**Schedule:**
- 7:00 AM IST
- 10:00 AM IST
- 1:00 PM IST
- 4:00 PM IST
- 7:00 PM IST

**Logs:**
```bash
tail -f /tmp/solar-update.log
```

**Reinstall if needed:**
```bash
crontab /Users/bhargav/repos/solar_intelligence/solar-crontab.txt
```

**Remove:**
```bash
crontab -r
```
⚠️ Warning: This removes ALL cron jobs.

---

### Option 2: launchd (Recommended for macOS)

**Status:** Ready to install

macOS-native scheduler with better:
- Reliability and logging
- System integration
- Battery/power management
- Wake from sleep handling

**Install:**
```bash
cd /Users/bhargav/repos/solar_intelligence
./launchd-manager.sh install
```

**Check status:**
```bash
./launchd-manager.sh status
```

**View logs:**
```bash
./launchd-manager.sh logs
```

**Test manually:**
```bash
./launchd-manager.sh test
```

**Uninstall:**
```bash
./launchd-manager.sh uninstall
```

---

## 🔄 How It Works

```
Scheduled Time (7am, 10am, 1pm, 4pm, 7pm)
             ↓
    Cron/launchd triggers
             ↓
    update-local.sh executes:
             ↓
    ┌─────────────────────────────────────┐
    │ 1. waaree_deep_crawler.py           │ ← Fetch live portal data
    │ 2. scripts/update_data.py           │ ← Process into dashboard JSON
    │ 3. git commit + push                │ ← Upload to GitHub
    └─────────────────────────────────────┘
             ↓
    GitHub Actions deploys (static.yml)
             ↓
    Dashboard updates in 1-2 minutes
```

---

## 📊 Files Overview

| File | Purpose |
|------|---------|
| `solar-crontab.txt` | Cron schedule configuration |
| `com.solar.update.plist` | launchd schedule configuration |
| `launchd-manager.sh` | Helper script for launchd management |
| `update-local.sh` | Main automation script (runs scraper + pipeline) |
| `/tmp/solar-update.log` | Standard output logs |
| `/tmp/solar-update-error.log` | Error logs (launchd only) |

---

## 🧪 Testing

### Manual Test Run
```bash
cd /Users/bhargav/repos/solar_intelligence
./update-local.sh
```

This will:
1. Fetch live data from Waaree portal
2. Process and update dashboard JSON
3. Commit and push to GitHub
4. Trigger automatic deployment

### Verify Automation is Working

**1. Check next scheduled run:**
```bash
# For cron
crontab -l

# For launchd
./launchd-manager.sh status
```

**2. Monitor logs in real-time:**
```bash
tail -f /tmp/solar-update.log
```

**3. Check GitHub commits:**
Visit: https://github.com/bhargavachary/solar-intelligence/commits/main

**4 Check live dashboard:**
Visit: https://bhargavachary.github.io/solar-intelligence/

---

## ⚙️ Switching Between Cron and launchd

### Currently Using Cron, Want to Switch to launchd?

```bash
# 1. Remove cron
crontab -r

# 2. Install launchd
./launchd-manager.sh install
```

### Currently Using launchd, Want to Switch to Cron?

```bash
# 1. Remove launchd
./launchd-manager.sh uninstall

# 2. Install cron
crontab /Users/bhargav/repos/solar_intelligence/solar-crontab.txt
```

---

## 🛠️ Troubleshooting

### Updates Not Running?

**1. Check if scheduler is active:**
```bash
# Cron
crontab -l

# launchd
launchctl list | grep solar
```

**2. Check logs for errors:**
```bash
cat /tmp/solar-update.log
cat /tmp/solar-update-error.log  # launchd only
```

**3. Test manually:**
```bash
cd /Users/bhargav/repos/solar_intelligence
./update-local.sh
```

**4. Verify paths are correct:**
```bash
ls -la /Users/bhargav/repos/solar_intelligence/waaree_deep_crawler.py
ls -la /Users/bhargav/repos/solar_intelligence/venv/bin/python3
```

### Common Issues

**Issue:** "No such file or directory"
- **Fix:** Check paths in `solar-crontab.txt` or `com.solar.update.plist`
- All paths should use `/Users/bhargav/repos/solar_intelligence`

**Issue:** "Permission denied"
- **Fix:** Make script executable
  ```bash
  chmod +x /Users/bhargav/repos/solar_intelligence/update-local.sh
  ```

**Issue:** Portal scraping fails
- **Fix:** Check credentials.json exists and is valid
- Test scraper manually:
  ```bash
  cd /Users/bhargav/repos/solar_intelligence
  ./venv/bin/python3 waaree_deep_crawler.py
  ```

---

## 📈 Monitoring

### Real-time monitoring during scheduled run:
```bash
tail -f /tmp/solar-update.log
```

### Check last 50 lines of logs:
```bash
tail -50 /tmp/solar-update.log
```

### Check for errors:
```bash
grep -i error /tmp/solar-update.log
```

---

## 🎯 Recommendation

**Use launchd** if you:
- Want better macOS integration
- Need detailed logging
- Want the Mac to handle sleep/wake properly
- Want system-level job management

**Use cron** if you:
- Prefer simplicity
- Are familiar with cron syntax
- Want lightweight scheduling
- Don't need advanced features

**Current Status:** Cron is active and working. launchd is available as an alternative.

---

## 📝 Summary of Fixes Applied

1. ✅ Fixed crontab paths (`waaree_api_access` → `solar_intelligence`)
2. ✅ Fixed update-local.sh Python venv paths
3. ✅ Reinstalled corrected crontab
4. ✅ Created launchd plist with proper configuration
5. ✅ Created launchd-manager.sh helper script
6. ✅ Verified all dependencies exist
7. ✅ Made all scripts executable
8. ✅ Tested script syntax

**Result:** Automation is now fully functional! 🎉

---

## 🔗 Quick Reference

```bash
# Check what's running
crontab -l                    # Check cron
./launchd-manager.sh status   # Check launchd

# View logs
tail -f /tmp/solar-update.log

# Manual update
./update-local.sh

# Switch methods
crontab -r                    # Remove cron
./launchd-manager.sh install  # Install launchd
```

---

Updated: February 16, 2026
