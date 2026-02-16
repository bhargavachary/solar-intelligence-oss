# Automated Scheduled Updates

## ✅ Status: ACTIVE

Automated solar data updates are now configured using **cron** (UNIX job scheduler).

---

## Schedule

The scraper runs **5 times daily**:

| Time | Purpose |
|------|---------|
| **7:00 AM** IST | Morning generation start |
| **10:00 AM** IST | Mid-morning peak |
| **1:00 PM** IST | Afternoon peak |
| **4:00 PM** IST | Late afternoon |
| **7:00 PM** IST | Evening generation end |

---

## How It Works

1. **cron** (system scheduler) triggers at scheduled times
2. Runs `update-local.sh` in the workspace directory
3. Script executes:
   - `waaree_deep_crawler.py` (fetches live portal data)
   - `scripts/update_data.py --source live` (processes data)
   - Git commit & push to GitHub
4. GitHub Actions deploys updated dashboard automatically
5. Live site updates within 1-2 minutes

---

## Management Commands

### Check Status
```bash
crontab -l
```
Should show 5 entries for solar updates at scheduled times.

### View Logs
```bash
tail -f /tmp/solar-update.log
```

### Manually Trigger (for testing)
```bash
cd /Users/bhargav/repos/waaree_api_access
./update-local.sh
```

### Stop Automated Updates
```bash
crontab -r
```
⚠️ **Warning:** This removes ALL cron jobs, not just solar updates.

### Modify Schedule
```bash
crontab -e
```
Edit the schedule directly in your default editor.

### Reinstall Schedule
```bash
crontab /Users/bhargav/repos/waaree_api_access/solar-crontab.txt
```

---

## Why Local Scheduling?

**GitHub Actions failed** due to:
- Chrome segfaults in CI containers
- Bot detection blocking GitHub IPs
- Anti-automation measures on Waaree portal

**Local scheduling succeeds** because:
- ✅ Uses your working Chrome v144 setup
- ✅ Runs from residential IP (no bot detection)
- ✅ Access to credentials.json
- ✅ Proven stable (no failures)
- ✅ Simple cron setup, no permission issues

---

## Troubleshooting

### Updates Not Running?

1. **Check if cron is installed:**
   ```bash
   crontab -l
   ```

2. **Check logs for errors:**
   ```bash
   cat /tmp/solar-update.log
   ```

3. **Verify Chrome is working:**
   ```bash
   cd /Users/bhargav/repos/waaree_api_access
   ./update-local.sh
   ```

4. **Reinstall schedule:**
   ```bash
   crontab /Users/bhargav/repos/waaree_api_access/solar-crontab.txt
   ```

### Mac Must Be Awake

⚠️ **Important:** Your Mac must be powered on and awake at scheduled times. 

To prevent sleep during work hours:
```bash
# Keep Mac awake until 8 PM (example)
caffeinate -u -t 39600 &
```

Or configure Energy Saver in System Preferences to prevent sleep.

---

## Next Run Times

Cron will run at:
- Next 7:00 AM
- Next 10:00 AM  
- Next 1:00 PM
- Next 4:00 PM
- Next 7:00 PM

Check current time: `date`

---

## Files

- **Cron Schedule:** `solar-crontab.txt` (backup/reinstall)
- **Active Crontab:** Run `crontab -l` to view
- **Update Script:** `update-local.sh`
- **Log File:** `/tmp/solar-update.log`
- **Scraper:** `waaree_deep_crawler.py`
- **Data Processor:** `scripts/update_data.py`

---

## Success Indicators

✅ **Working correctly when:**
- `crontab -l` shows 5 scheduled entries
- `/tmp/solar-update.log` shows successful runs at scheduled times
- GitHub commits appear at 7 AM, 10 AM, 1 PM, 4 PM, 7 PM
- Dashboard shows fresh data 5x daily

---

## Alternative: GitHub Actions (Not Recommended)

We tried GitHub Actions with scheduled workflows but it failed due to Chrome reliability issues. If you want to try again:

```yaml
on:
  schedule:
    - cron: '30 1,4,7,10,13 * * *'  # UTC times
```

But expect failures due to:
- Chrome crashes in CI
- Bot detection blocking
- Selenium reliability issues

**Current solution (launchd) is more reliable.**
