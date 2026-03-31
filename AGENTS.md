# AGENTS.md — Solar Intelligence

Real-time solar monitoring dashboard for a 2.32 kW rooftop PV system (Berhampur, Odisha).
Data source: Waaree / FoxESS Cloud API (reverse-engineered REST — no Selenium, no browser).

---

## Architecture

```
waaree_api_client.py    ← core API client (login, plants, devices, generation data)
scraper_api.py          ← Flask HTTP server wrapping the API client (local use)
update_data.py          ← pipeline: fetch → log → CSV → commit → push
update-local.sh         ← shell wrapper for update_data.py (manual runs)
index.html              ← single-file dashboard (HTML + CSS + JS, no build step)
credentials.json        ← git-ignored — NEVER commit; CI injects via WAAREE_CREDENTIALS secret
requirements.txt        ← requests>=2.31.0, flask>=3.0.0, flask-cors>=4.0.0
data/
  dashboard.json        ← schema v5.0 — consumed by index.html (do not change top-level keys)
  energy_history.csv    ← daily table with hourly power columns
  energy_logs/          ← immutable daily JSON archives: YYYY-MM-DD.json
.github/workflows/
  solar_update.yml      ← auto-update: 5×/day at 07:00, 10:00, 13:00, 16:00, 19:00 IST
  static.yml            ← GitHub Pages deploy
```

---

## Environment

```bash
conda activate base
pip install -r requirements.txt   # if not already installed
```

- `credentials.json` is git-ignored; create locally from your Waaree account
- CI injects credentials via `WAAREE_CREDENTIALS` GitHub Actions secret (JSON string)
- **No Node.js, no npm** for this project

---

## Commands

```bash
conda activate base
python3 update_data.py           # fetch latest data (no push)
python3 update_data.py --push    # fetch + commit + push (confirm with user first)
python3 scraper_api.py           # run Flask API server locally
# View dashboard: open index.html in browser
```

---

## Rules

- `dashboard.json` must stay on schema **v5.0** — do not add/remove top-level keys without auditing `index.html`
- Files in `energy_logs/` are **immutable write-once** archives — never modify existing daily files
- `index.html` is intentionally self-contained (no bundler) — keep it that way
- The auto-update workflow commits `data/*` and `index.html` — do not restructure these paths
- Do **not** run `update_data.py --push` without user confirmation
- Do **not** add a build system or npm
- Do **not** split `index.html` into separate files
- Do **not** commit `credentials.json` or any API token
- Do **not** change the GHA cron schedule without updating the IST comments in the workflow

---

## Owner

**D K Bhargav Achary** — sole maintainer.
