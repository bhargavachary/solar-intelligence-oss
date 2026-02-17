# ☀️ Solar Intelligence

Real-time solar energy monitoring dashboard for a **5 kW rooftop PV system** in Hyderabad, India.
Live data fetched from **Waaree / FoxESS Cloud** via reverse-engineered REST API — no Selenium, no browser automation.

**[→ Live Dashboard](https://bhargavachary.github.io/solar_intelligence/)**

---

## Architecture

```
credentials.json          ← plant credentials (git-ignored)
waaree_api_client.py      ← core API client (login, plants, devices, generation)
scraper_api.py            ← Flask HTTP server wrapping the API client
generate_report.py        ← CLI report generator
update-local.sh           ← one-command: fetch → log → commit → push

data/
  dashboard.json          ← live payload consumed by index.html
  energy_logs/            ← immutable daily JSON archives

index.html                ← single-file dashboard (HTML + CSS + JS)
assets/                   ← static assets (icons, images)

docs/
  01-ARCHITECTURE.md      ← system design and data flow
  02-API-REFERENCE.md     ← complete FoxESS Cloud API reference
  03-SETUP-AND-OPERATIONS.md ← setup, deployment and scheduling
```

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/bhargavachary/solar_intelligence.git
cd solar_intelligence
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Create credentials.json with: username, password, plant_id, capacity, location

# 3. Fetch live data
python3 waaree_api_client.py --dashboard --json > data/dashboard.json

# 4. One-command update (fetch, log, commit, push)
./update-local.sh
```

## API Client CLI

```bash
python3 waaree_api_client.py --dashboard        # full dashboard payload
python3 waaree_api_client.py --hourly            # hourly generation
python3 waaree_api_client.py --monthly           # monthly totals
python3 waaree_api_client.py --yearly            # lifetime yearly totals
```

## Dashboard

The dashboard is a single `index.html` file deployed on **GitHub Pages**.
It loads `data/dashboard.json` at runtime — no build step, no framework.

Features: live power display, 7-day trend charts, monthly analytics,
dark/light theme, responsive layout, glassmorphism design with CSS animations.

## Documentation

| Doc | Contents |
|-----|----------|
| [01-ARCHITECTURE](docs/01-ARCHITECTURE.md) | System design, data schema v5.0, flow diagrams |
| [02-API-REFERENCE](docs/02-API-REFERENCE.md) | FoxESS Cloud endpoints, auth, signature algorithm |
| [03-SETUP-AND-OPERATIONS](docs/03-SETUP-AND-OPERATIONS.md) | Installation, scheduling, troubleshooting |

## License

Private project. © Bhargav Achary
