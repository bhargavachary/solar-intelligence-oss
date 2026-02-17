# 01 — System Architecture

## Overview

**Solar Intelligence** is a real-time monitoring dashboard for a 2.32 kW rooftop solar plant
located in Berhampur, Odisha, India. It fetches live data from the Waaree digital portal
via a reverse-engineered REST API and renders an interactive single-page dashboard.

## Architecture

```
                    ┌─────────────────────────────────┐
                    │  digital.waaree.com (FoxESS)    │
                    │  REST API (/c/v0, /generic/v0)  │
                    └──────────────┬──────────────────┘
                                   │ HTTPS/JSON
                                   ▼
┌──────────────────────────────────────────────────────┐
│  waaree_api_client.py                                │
│  ─ MD5 signature auth + JWT token caching            │
│  ─ Plants, Devices, Hourly/Daily/Monthly reports     │
└──────────────────┬───────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐     ┌──────────────────┐
│ scraper_api.py│     │ generate_report  │
│ (Flask :8006) │     │ (CLI reports)    │
│               │     └──────────────────┘
│ /trigger_scrape│
│ /api/live      │
│ /api/hourly    │
│ /api/daily     │
│ /api/monthly   │
│ /api/dashboard │
└───────┬───────┘
        │ writes
        ▼
┌───────────────────┐       ┌──────────────────┐
│ data/             │       │ index.html       │
│  dashboard.json   │──────▶│ (client-side JS) │
│  energy_logs/     │       │ GitHub Pages     │
└───────────────────┘       └──────────────────┘
```

## Component Summary

| Component | File | Purpose |
|-----------|------|---------|
| **API Client** | `waaree_api_client.py` | Core library: auth, signature, all API calls |
| **API Server** | `scraper_api.py` | Flask HTTP server for dashboard updates |
| **Dashboard** | `index.html` | Single-file interactive dashboard (Chart.js) |
| **Report Generator** | `generate_report.py` | CLI tool for comprehensive system reports |
| **Update Script** | `update-local.sh` | One-command data refresh + git push |
| **Data** | `data/dashboard.json` | Live dashboard payload (schema v5.0) |
| **Energy Logs** | `data/energy_logs/` | Daily JSON logs (immutable historical record) |
| **Credentials** | `credentials.json` | Portal login (gitignored) |
| **Token Cache** | `.waaree_token.json` | Cached JWT token (gitignored) |

## Data Flow

1. `update-local.sh` (or cron) calls `waaree_api_client.py`
2. Client authenticates with Waaree portal (MD5 signature + JWT)
3. Fetches: current power, hourly/daily/monthly generation
4. `scraper_api.py` builds schema v5.0 JSON → writes `data/dashboard.json`
5. Git push triggers GitHub Pages deploy
6. `index.html` loads `data/dashboard.json` and renders charts/cards

## Deployment

- **Hosting**: GitHub Pages (auto-deploy on push to `main`)
- **Data Updates**: Manual via `./update-local.sh` or cron schedule
- **Local Dev**: `python -m http.server 8080` → `http://localhost:8080`

## Technology Stack

| Layer | Technology |
|-------|-----------|
| API Client | Python 3.14, `requests` library |
| Signature | MD5 HMAC (FoxESS Cloud protocol) |
| Server | Flask + flask-cors |
| Dashboard | Vanilla HTML/CSS/JS, Chart.js 4.4 |
| Fonts | Inter (Google Fonts) |
| Hosting | GitHub Pages (static) |
| CI/CD | GitHub Actions (Pages deploy) |
