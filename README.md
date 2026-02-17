# ☀️ Solar Intelligence

Real-time solar energy monitoring dashboard for a **2.32 kW rooftop PV system** in **Berhampur, Odisha**.
Live data fetched from **Waaree / FoxESS Cloud** via reverse-engineered REST API — no Selenium, no browser automation.

**[→ Live Dashboard](https://bhargavachary.github.io/solar-intelligence/)**

---

## Architecture

```
credentials.json          ← plant credentials (git-ignored)
waaree_api_client.py      ← core API client (login, plants, devices, generation)
scraper_api.py            ← Flask HTTP server wrapping the API client
update_data.py            ← pipeline: fetch → log → CSV → commit → push
update-local.sh           ← shell wrapper for update_data.py

data/
  dashboard.json          ← live payload consumed by index.html (schema v5.0)
  energy_history.csv      ← consolidated daily table with hourly power columns
  energy_logs/            ← immutable daily JSON archives

index.html                ← single-file dashboard (HTML + CSS + JS)

docs/
  01-ARCHITECTURE.md      ← system design and data flow
  02-API-REFERENCE.md     ← complete FoxESS Cloud API reference
  03-SETUP-AND-OPERATIONS.md ← setup, deployment and scheduling
```

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/bhargavachary/solar-intelligence.git
cd solar-intelligence
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Create credentials.json: { "username": "...", "password": "..." }

# 3. Fetch live data + build CSV + archive log
python3 update_data.py

# 4. Fetch + commit + push to GitHub Pages
python3 update_data.py --push
```

## API Client CLI

```bash
python3 waaree_api_client.py --dashboard       # full dashboard payload
python3 waaree_api_client.py --hourly           # today's hourly generation
python3 waaree_api_client.py --monthly          # this month's daily totals
python3 waaree_api_client.py --yearly           # yearly monthly totals
```

## Data Format

### `data/energy_history.csv`
```
date,yield_kwh,peak_power_kw,avg_power_kw,h05_kw,h06_kw,...,h19_kw,source
2026-02-14,9.4,1.508,0.94,,,,,,,,,,,,,,,,api
2026-02-17,11.4,1.508,1.14,,,,0.2,0.6,1.0,1.3,1.4,...,api
```

Rows = days, hourly columns (`h05_kw`–`h19_kw`) = power in kW at that hour.

## Dashboard

Single `index.html` deployed on **GitHub Pages** — no build step, no framework.
Loads `data/dashboard.json` at runtime.

Features: live power display, hourly power curves, 7-day trends, monthly analytics,
seasonal forecasting, financial ROI tracking, dark/light theme, glassmorphism design,
animated popup detail cards, responsive layout.

## Documentation

| Doc | Contents |
|-----|----------|
| [01-ARCHITECTURE](docs/01-ARCHITECTURE.md) | System design, data schema v5.0, flow diagrams |
| [02-API-REFERENCE](docs/02-API-REFERENCE.md) | FoxESS Cloud endpoints, auth, signature algorithm |
| [03-SETUP-AND-OPERATIONS](docs/03-SETUP-AND-OPERATIONS.md) | Installation, scheduling, troubleshooting |

## License

Private project. © Bhargav Achary
