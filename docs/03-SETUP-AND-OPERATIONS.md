# 03 — Setup & Operations Guide

## Prerequisites

- Python 3.10+ with `pip`
- Git

## Installation

```bash
git clone https://github.com/bhargavachary/solar-intelligence.git
cd solar-intelligence

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create `credentials.json` in the project root:

```json
{
    "username": "<waaree_portal_username>",
    "password": "<waaree_portal_password>",
    "plant_id": "<station_id_from_api>",
    "plant_capacity_kw": 2.32,
    "location": "Berhampur, Odisha"
}
```

## Usage

### One-Command Update (Fetch + Commit + Push)

```bash
./update-local.sh
```

### CLI Data Access

```bash
# Live dashboard summary
python3 waaree_api_client.py --dashboard

# Today's hourly generation
python3 waaree_api_client.py --hourly

# This month's daily breakdown
python3 waaree_api_client.py --monthly

# This year's monthly summary
python3 waaree_api_client.py --yearly

# JSON output (for piping/scripting)
python3 waaree_api_client.py --dashboard --json

# Generate full system report
python3 generate_report.py
```

### Local API Server

```bash
python3 scraper_api.py
# Listens on http://localhost:8006
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/trigger_scrape` | POST/GET | Refresh dashboard data (async) |
| `/status` | GET | Last update status |
| `/health` | GET | Health check |
| `/api/live` | GET | Live power + yield |
| `/api/hourly` | GET | Today's hourly generation |
| `/api/daily` | GET | This month's daily generation |
| `/api/monthly` | GET | This year's monthly generation |
| `/api/dashboard` | GET | Full dashboard payload |

### Local Dashboard

```bash
python3 -m http.server 8080
# Open http://localhost:8080
```

## Automated Updates (cron)

Add to crontab (`crontab -e`):

```cron
# Solar data update every 5 minutes during daylight (6 AM - 7 PM IST)
*/5 6-19 * * * cd /path/to/solar-intelligence && ./update-local.sh >> /tmp/solar-update.log 2>&1
```

## Data Schema (v5.0)

The dashboard reads `data/dashboard.json` with this structure:

```
{
  "meta":           { schema_version, plant_id, capacity, location, data_source }
  "summary":        { peak_power, avg_power, latest_timestamp, daily/monthly/total yield }
  "live":           { timestamp, power_kw, daily/monthly/total yield, status }
  "last_7_days":    [ { date, yield_kwh, peak_power, avg_power, record_count } ]
  "today_records":  [ { timestamp, power, yield, status, extraction_method } ]
  "monthly":        { "month_year": { yield, days_active, peak_power } }
  "analytics":      { health, statistics, daily_progress, power_trend, seasonal_forecast }
}
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Login fails (errno 41809) | Signature error — check `waaree_api_client.py` signature code |
| Login fails (406) | Must use `data=json.dumps()` not `json=` in requests |
| Empty plant list | Use `pageSize: 10` (API bug with larger values) |
| Token expired (41808) | Delete `.waaree_token.json`, re-run |
| Dashboard blank | Check `data/dashboard.json` exists and is valid JSON |
| API quota exceeded | Wait until midnight IST (1440 calls/day) |
