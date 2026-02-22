# Solar Intelligence — Claude Context

Real-time solar monitoring dashboard for a 2.32 kW rooftop PV system (Berhampur, Odisha).
Data source: Waaree / FoxESS Cloud API (reverse-engineered REST, no Selenium).

## Architecture
```
waaree_api_client.py   ← core API client (login, plants, devices, generation data)
scraper_api.py         ← Flask HTTP server wrapping the API client (local use)
update_data.py         ← pipeline: fetch → log → CSV → commit → push
update-local.sh        ← shell wrapper for update_data.py (local manual runs)
index.html             ← single-file dashboard (HTML + CSS + JS, no build step)
credentials.json       ← git-ignored — NEVER commit; CI injects via WAAREE_CREDENTIALS secret
requirements.txt       ← requests>=2.31.0, flask>=3.0.0, flask-cors>=4.0.0
data/
  dashboard.json       ← schema v5.0 — consumed by index.html (do not change top-level keys)
  energy_history.csv   ← daily table with hourly power columns
  energy_logs/         ← immutable daily JSON archives: YYYY-MM-DD.json
docs/
  01-ARCHITECTURE.md
  02-API-REFERENCE.md
  03-SETUP-AND-OPERATIONS.md
.github/workflows/
  solar_update.yml     ← auto-update: 5x/day at 07:00, 10:00, 13:00, 16:00, 19:00 IST
  static.yml           ← GitHub Pages deploy
```

## Environment
- Python — use `base` conda env (no dedicated env for this project)
  ```bash
  conda activate base
  pip install -r requirements.txt   # if deps not already installed
  ```
- `credentials.json` is git-ignored — create locally from your Waaree account credentials
- CI injects credentials via `WAAREE_CREDENTIALS` GitHub Actions secret (JSON string)

## Key Rules
- `dashboard.json` must stay on schema v5.0 — do not add/remove top-level keys without auditing `index.html`
- `energy_logs/` files are immutable write-once archives — never modify existing daily files
- Auto-update workflow commits `data/*` and `index.html` — do not restructure these paths
- `update_data.py --push` does git commit + push — confirm with user before running
- `index.html` is intentionally self-contained (no bundler) — keep it that way

## Common Tasks
```bash
conda activate base
python3 update_data.py           # fetch latest data (no push)
python3 update_data.py --push    # fetch + commit + push (confirm first)
python3 scraper_api.py           # run Flask API server locally
# open index.html in browser to view dashboard
```

## Do Not
- Do not add a build system or npm to this project
- Do not split `index.html` into separate files
- Do not commit `credentials.json` or any API token
- Do not modify files in `energy_logs/` — write-once archives
- Do not change the GitHub Actions cron schedule without updating the IST comments in the workflow
