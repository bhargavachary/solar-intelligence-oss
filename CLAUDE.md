# Solar Intelligence — Claude Context

Real-time solar monitoring dashboard for a 2.32 kW rooftop PV system (Berhampur, Odisha).
Data source: Waaree / FoxESS Cloud API (reverse-engineered REST, no Selenium).

## Architecture
```
waaree_api_client.py   ← core API client (login, plants, devices, generation)
scraper_api.py         ← Flask HTTP server wrapping the API client
update_data.py         ← pipeline: fetch → log → CSV → commit → push
update-local.sh        ← shell wrapper for update_data.py
index.html             ← single-file dashboard (HTML + CSS + JS, no build step)
credentials.json       ← git-ignored, never commit
data/
  dashboard.json       ← schema v5.0, consumed by index.html
  energy_history.csv   ← daily table with hourly power columns
  energy_logs/         ← immutable daily JSON archives YYYY-MM-DD.json
docs/
  01-ARCHITECTURE.md
  02-API-REFERENCE.md
  03-SETUP-AND-OPERATIONS.md
```

## Environment
- Python — use conda env for this project (no venv)
- Dependencies: `requests`, `flask`, `flask-cors`
- `credentials.json` is git-ignored — never read, mention, or commit it

## Key Rules
- `dashboard.json` must stay on schema v5.0 — do not add/remove top-level keys without checking index.html
- `energy_logs/` files are immutable archives — never modify existing ones
- Auto-update runs via GitHub Actions (`.github/workflows/`) — do not break the workflow YAML
- `update_data.py --push` does git commit + push — confirm before running
- `index.html` is intentionally self-contained (no bundler) — keep it that way

## Common Tasks
- Fetch latest data (no push): `python3 update_data.py`
- Fetch + commit + push: `python3 update_data.py --push`
- Run Flask server locally: `python3 scraper_api.py`
- View dashboard: open `index.html` in browser

## Do Not
- Do not add a build system or npm to this project
- Do not split `index.html` into separate files
- Do not commit `credentials.json` or any API token
