# Copilot Instructions — Solar Intelligence

Real-time solar monitoring dashboard. Python data pipeline + single-file HTML dashboard.
Data source: Waaree / FoxESS Cloud API (reverse-engineered REST).

## Stack
- Python (conda `base` env): `requests`, `flask`, `flask-cors`
- Frontend: single self-contained `index.html` — no bundler, no npm

## Rules
- `dashboard.json` schema is v5.0 — do not add/remove top-level keys without checking `index.html`
- `energy_logs/YYYY-MM-DD.json` files are immutable — never modify existing daily archives
- `credentials.json` is git-ignored — never read, generate, or reference its contents
- Do not split `index.html` into separate files
- Do not add a build system or npm
- `update_data.py --push` commits and pushes — confirm with user before suggesting this
- Auto-update runs via GitHub Actions 5x/day — do not modify cron schedule without noting IST times
- Use `conda activate base` before Python commands

## Style
- Python: type hints optional, `logging` over `print`, `pathlib.Path` for file ops
