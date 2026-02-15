# Automated Solar Data Scraping Workflow

## Overview
This GitHub Actions workflow automatically scrapes solar telemetry data from the Waaree portal at scheduled intervals throughout the day.

## Schedule
The workflow runs **5 times daily** at:
- 🌅 **7:00 AM IST** (1:30 AM UTC)
- ☀️ **10:00 AM IST** (4:30 AM UTC)
- 🌤️ **1:00 PM IST** (7:30 AM UTC)
- 🌆 **4:00 PM IST** (10:30 AM UTC)
- 🌃 **7:00 PM IST** (1:30 PM UTC)

These times are optimized to capture:
- Morning startup (7 AM)
- Peak morning generation (10 AM)
- Afternoon peak (1 PM)
- Evening transition (4 PM)
- End of day summary (7 PM)

## How It Works

### Session Management (Smart & Efficient)
The workflow implements intelligent session reuse to minimize unnecessary logins:

1. **Session Cache**: After each successful scrape, the browser session is saved
2. **Age Check**: Before each run, checks if the cached session is < 4 hours old
3. **Reuse First**: If session is valid, attempts to reuse it (faster, less load on portal)
4. **Fallback**: If session reuse fails or session expired, performs fresh login
5. **Persistence**: Successful session is saved for next run

This approach:
- ✅ Reduces scraping time from ~60s to ~20s when session is reused
- ✅ Minimizes load on Waaree portal
- ✅ More reliable - falls back to fresh login if session issues occur

### Workflow Steps

1. **Checkout**: Fetches latest code
2. **Setup Python**: Installs Python 3.11 with pip caching
3. **Install Dependencies**: Installs required packages from `requirements.txt`
4. **Install Chrome**: Sets up Chrome browser for Selenium
5. **Restore Session**: Attempts to restore previous session from cache
6. **Check Session Age**: Validates if session is still usable (< 4 hours)
7. **Create Credentials**: Builds credentials file from GitHub Secrets
8. **Scrape (Reuse)**: If session valid, tries reusing existing session
9. **Scrape (Fresh)**: If reuse fails or session expired, performs fresh login
10. **Sync Data**: Copies scraped data to `data/dashboard_data.json`
11. **Run Analytics**: Executes optional analytics enrichment
12. **Save Session**: Caches the session for next run
13. **Archive Diagnostics**: Saves HTML snapshots and logs as artifacts
14. **Commit & Push**: Auto-commits updated data to repository
15. **Trigger Pages**: Triggers GitHub Pages deployment for dashboard

## Required GitHub Secrets

You must configure these secrets in your repository settings:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `WAAREE_USERNAME` | Portal login username/email | `your.email@example.com` |
| `WAAREE_PASSWORD` | Portal login password | `YourSecurePassword123` |
| `WAAREE_PLANT_ID` | Your solar plant ID | `62758` |

**To add secrets:**
1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add each secret with its value

## Manual Triggering

You can manually trigger the workflow anytime:

1. Go to **Actions** tab in GitHub
2. Select **"Update Solar Data"** workflow
3. Click **"Run workflow"** dropdown
4. Select branch (usually `main`)
5. Click **"Run workflow"** button

This is useful for:
- Testing after setup
- Getting immediate data update
- Recovering from temporary failures

## Monitoring

### Check Workflow Status
- Navigate to **Actions** tab
- See all workflow runs with timestamps and status
- Green ✅ = Success
- Red ❌ = Failed (check logs)
- Yellow ⏳ = In progress

### View Logs
Click on any workflow run to see detailed logs for each step.

### Download Diagnostics
Failed runs automatically save diagnostics:
- Navigate to failed run
- Scroll to bottom → "Artifacts"
- Download `diagnostics-<run-id>.zip`
- Contains HTML snapshots and error logs

## Troubleshooting

### Workflow fails with "Authentication failed"
- Check if GitHub Secrets are configured correctly
- Verify credentials work by logging into portal manually
- Password may have been changed - update secret

### Workflow times out
- Portal may be slow or down
- Workflow has 5-minute timeout per scrape attempt
- Will retry on next scheduled run

### Session reuse always fails
- This is OK - workflow falls back to fresh login
- May indicate portal changed authentication flow
- Check diagnostics for specific error

### No data updates
- Check if workflow is enabled (Actions tab)
- Verify schedule is correct
- Check if commits are being pushed (may be blocked by branch protection)

## Local Testing

Before deploying, you can test locally:

### Quick Validation (No Chrome Required)
```bash
python validate_workflow.py
```

Checks:
- ✅ YAML syntax
- ✅ Cron schedule
- ✅ File structure
- ✅ Git configuration
- ✅ Secrets availability

### Full Integration Test (Requires Chrome)
```bash
python test_workflow.py --runs 3 --delay 10
```

Runs 3 complete scrape cycles with 10s delay between them to test:
- Fresh login
- Session persistence
- Session reuse
- Data validation
- File operations

## Files

| File | Purpose |
|------|---------|
| `.github/workflows/update-solar-data.yml` | Main workflow definition |
| `waaree_deep_crawler.py` | Core scraping engine |
| `requirements.txt` | Python dependencies |
| `validate_workflow.py` | Pre-deployment validator |
| `test_workflow.py` | Full integration tester |
| `data/dashboard_data.json` | Output data file (dashboard reads this) |
| `diagnostics/` | Debug artifacts (HTML snapshots, logs) |

## Performance

| Metric | Value |
|--------|-------|
| Fresh login scrape | ~45-60 seconds |
| Session reuse scrape | ~15-25 seconds |
| Session validity | 4 hours |
| Daily runs | 5 times |
| Monthly Actions minutes | ~75 minutes |

GitHub Free tier includes **2,000 minutes/month**, so this workflow uses <4% of free quota.

## Best Practices

1. **Monitor first week**: Check logs daily to ensure stability
2. **Review diagnostics**: If failures occur, download and review artifacts
3. **Keep secrets updated**: Change password? Update GitHub Secret immediately
4. **Don't over-schedule**: 5 runs/day is optimal - more may trigger rate limiting
5. **Use manual trigger**: For testing, use workflow_dispatch instead of pushing test commits

## Security

- ✅ Credentials stored as encrypted GitHub Secrets (never in code)
- ✅ Session files cached but expire after 4 hours
- ✅ Credentials file created ephemerally (exists only during workflow run)
- ✅ No sensitive data committed to repository
- ✅ Diagnostics redact credentials from HTML snapshots

## Future Enhancements

Potential improvements:
- [ ] Slack/email notifications on failure
- [ ] Adaptive scheduling based on daylight hours
- [ ] ML-based anomaly detection
- [ ] Multi-plant support
- [ ] Historical data backfill

---

## Quick Start

1. **Add GitHub Secrets** (see Required GitHub Secrets section)
2. **Test locally** (optional): `python validate_workflow.py`
3. **Commit and push** workflow file
4. **Monitor** first run in Actions tab
5. **Verify** dashboard updates with fresh data

✅ That's it! Your solar data will now update automatically throughout the day.
