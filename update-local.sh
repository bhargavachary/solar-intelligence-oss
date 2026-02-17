#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Solar Intelligence — Local Data Update (API Mode)
# ═══════════════════════════════════════════════════════════════════════════
# Fetches REAL data from Waaree/FoxESS Cloud API, writes data/dashboard.json,
# archives today's energy log, commits, and pushes to GitHub.
#
# Usage: ./update-local.sh [--no-push]
# ═══════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PYTHON="$SCRIPT_DIR/.venv/bin/python3"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Solar Data Update — API Mode"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Preflight checks
if [ ! -f "credentials.json" ]; then
    echo "❌ credentials.json not found"; exit 1
fi
if [ ! -f "$PYTHON" ]; then
    echo "❌ Python venv not found at .venv/"; exit 1
fi

# 1. Fetch live data via API → data/dashboard.json (using schema v5.0 builder)
echo "🔄 Fetching live data from Waaree API..."
$PYTHON << 'PYSCRIPT'
import json, os, sys
from scraper_api import build_dashboard_json
from waaree_api_client import WaareeAPIClient

creds_file = os.path.join(os.getcwd(), 'credentials.json')
token_file = os.path.join(os.getcwd(), '.waaree_token.json')
with open(creds_file) as f:
    creds = json.load(f)

client = WaareeAPIClient(creds['username'], creds['password'], token_file=token_file)
client.login()
data = build_dashboard_json(client)

with open('data/dashboard.json', 'w') as f:
    json.dump(data, f, indent=2, default=str)
PYSCRIPT
echo "✅ data/dashboard.json updated"

# 2. Archive today's energy log
echo "🔄 Archiving energy log..."
$PYTHON << 'PYSCRIPT'
from waaree_api_client import WaareeAPIClient
import json, os
from datetime import datetime

with open('credentials.json') as f:
    creds = json.load(f)
client = WaareeAPIClient(creds['username'], creds['password'], token_file='.waaree_token.json')
client.login()
plants = client.get_plants()
station_id = plants[0]['stationID'] if plants else ''
devices = client.get_devices()
device = devices[0] if devices else {}
now = datetime.now()

# get_daily_generation returns list of tuples: [(day, kwh), ...]
daily = client.get_daily_generation(station_id, now.year, now.month) if station_id else []
today_str = now.strftime('%Y-%m-%d')

# Find today's kwh from daily data
today_kwh = 0.0
for day, kwh in daily:
    if day == now.day:
        today_kwh = kwh
        break
if today_kwh == 0.0 and isinstance(device, dict):
    today_kwh = device.get('generationToday', 0.0)

log = {
    'date': today_str,
    'daily_kwh': round(float(today_kwh), 2),
    'total_kwh': round(float(device.get('generationTotal', 0) if isinstance(device, dict) else 0), 2),
    'peak_power_kw': round(float(device.get('power', 0) if isinstance(device, dict) else 0), 3),
    'source': 'api',
    'logged_at': now.isoformat()
}
log_file = f'data/energy_logs/solar_energy_{today_str}.json'
os.makedirs('data/energy_logs', exist_ok=True)
with open(log_file, 'w') as f:
    json.dump(log, f, indent=2)
print(f'✅ Energy log saved: {log_file}')
PYSCRIPT

# 3. Commit and push
if [[ "$1" != "--no-push" ]]; then
    echo "🔄 Committing changes..."
    git add data/dashboard.json data/energy_logs/*.json
    git commit -m "📊 Data update: $(date +'%Y-%m-%d %H:%M')" || echo "ℹ️  No changes to commit"

    echo "📤 Pushing to GitHub..."
    git push
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Solar data updated successfully!"
echo "  🌐 GitHub Pages will auto-deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
