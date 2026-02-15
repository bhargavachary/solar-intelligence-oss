<div align="center">

# ☀️ Solar Intelligence Dashboard

**Real-time monitoring for a 2.32 kW rooftop solar plant**

[![Live Dashboard](https://img.shields.io/badge/🔴_Live-Dashboard-ff9f0a?style=for-the-badge)](https://bhargavachary.in/waaree_api_access/)
[![Update Data](https://img.shields.io/github/actions/workflow/status/bhargavachary/waaree_api_access/update-data.yml?style=for-the-badge&label=Data%20Pipeline&logo=github-actions)](https://github.com/bhargavachary/waaree_api_access/actions)
[![GitHub Pages](https://img.shields.io/badge/Hosted_on-GitHub_Pages-222?style=for-the-badge&logo=github)](https://bhargavachary.in/waaree_api_access/)

<br>

<a href="https://bhargavachary.in/waaree_api_access/">
  <img src="assets/screenshot.png" alt="Dashboard Preview" width="800" style="border-radius: 16px; box-shadow: 0 24px 80px rgba(0,0,0,0.2)" />
</a>

<br><br>

*Apple-inspired glassmorphism dashboard with ML analytics, anomaly detection, and seasonal forecasting — all running client-side.*

</div>

---

## 🌟 Features

| Feature | Description |
|---------|-------------|
| ⚡ **Live Power Monitoring** | Real-time power output, daily yield, and lifetime generation |
| 📊 **ML Analytics Engine** | EWMA smoothing, linear regression trends, Z-score anomaly detection |
| 🔮 **Seasonal Forecasting** | Berhampur solar irradiance model with monthly predictions |
| 🛡️ **Health Scoring** | Composite index from performance ratio, uptime, and data quality |
| 🎨 **Glassmorphism Design** | Apple-inspired dark/light mode with ambient gradient animations |
| 📱 **Fully Responsive** | Desktop, tablet, and mobile optimized |
| 🤖 **Auto-updating** | GitHub Actions pipeline refreshes data 3× daily |
| 📈 **Interactive Charts** | Power curves, voltage/current dual-axis, monthly bar charts |

## 🏗️ Architecture

```
waaree_api_access/
├── index.html                    # Dashboard (HTML + CSS + JS, schema v5.0)
├── data/
│   ├── dashboard_data.json       # Lightweight summary (~1.3 KB)
│   └── energy_logs/              # Immutable daily logs (source of truth)
│       ├── solar_energy_2026-02-15.json
│       └── ...
├── scripts/
│   ├── archive_daily_data.py     # Create immutable daily energy logs
│   ├── build_dashboard_summary.py # Aggregate logs → dashboard
│   ├── update_data.py            # Integrated pipeline (scrape → log → build)
│   └── waaree_deep_crawler.py    # Live portal scraper
├── solar_analytics.py            # Pure Python ML analytics engine
├── docs/
│   └── DATA_MANAGEMENT.md        # Data architecture guide
└── .github/workflows/
    └── update-data.yml           # Scheduled pipeline (3×/day)
```

## 🚀 Quick Start

### View Live
Visit **[bhargavachary.in/waaree_api_access/](https://bhargavachary.in/waaree_api_access/)** — read-only mode, auto-refreshes every 60s.

### Run Locally

```bash
# Clone
git clone https://github.com/bhargavachary/waaree_api_access.git
cd waaree_api_access

# Generate data
python scripts/generate_data.py

# Serve locally
python -m http.server 8005

# Open http://localhost:8005 — local dev mode with 10s refresh
```

### Generate Multi-day History

```bash
python scripts/generate_data.py --days 7
```

## 🔬 Analytics Engine

The `solar_analytics.py` module is a **pure Python** (no numpy/sklearn) analytics suite:

- **Anomaly Detection** — Z-score + IQR dual-method flagging
- **EWMA Smoothing** — Exponentially Weighted Moving Average with forecast
- **Linear Regression** — Trend detection with R² confidence
- **Seasonal Model** — Berhampur PSH (Peak Sun Hours) monthly scaling
- **Performance Ratio** — IEEE-standard PR calculation
- **Health Scoring** — Weighted composite index (A+ to F grading)
- **Degradation Estimation** — Annual % decline tracking

## ☀️ Plant Details

| Spec | Value |
|------|-------|
| **Manufacturer** | N/A |
| **Capacity** | 2.32 kW |
| **Type** | Rooftop Grid-tied |
| **Location** | Berhampur, Odisha (19.3°N, 84.8°E) |
| **Peak Sun Hours** | 3.5 – 7.0 hrs (seasonal) |
| **Est. Annual Yield** | ~3,200 kWh |

## 🔧 Data Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  generate_data   │────▶│  solar_analytics  │────▶│   data/      │
│  (bell curve     │     │  (ML enrichment)  │     │   dashboard  │
│   + physics)     │     │                   │     │   _data.json │
└─────────────────┘     └──────────────────┘     └──────┬──────┘
                                                         │
                    GitHub Actions (3×/day)               │
                    ───────────────────────               ▼
                                                  ┌──────────────┐
                                                  │  index.html   │
                                                  │  (client JS   │
                                                  │   rendering)  │
                                                  └──────────────┘
```

## 📂 Other Tools

| Script | Purpose |
|--------|---------|
| `waaree_deep_crawler.py` | Selenium scraper for digital.waaree.com |
| `scraper_api.py` | Flask API server for local scrape triggers |
| `validate_dashboard.py` | 112-test validation suite (Grade A+) |
| `mock_inverter.py` | RS-485 inverter simulator for testing |

## 📄 License

MIT © [Bhargav Achary](https://bhargavachary.in/)

---

<div align="center">
  <sub>Maintained with Love by Bhargav and Copilot</sub>
</div>
