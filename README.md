# SolarIntelligence ☀️

> **Telemetry and data analysis platform for rooftop solar PV generation in Berhampur, Odisha.**  
> Real-time REST API integration with FoxESS / Waaree Cloud, immutable daily JSON energy archives, and an interactive, client-side dashboard with zero build dependencies.

[![Dashboard](https://img.shields.io/badge/dashboard-live%20vanilla%20JS-brightgreen.svg)](index.html)
[![API Client](https://img.shields.io/badge/api%20client-Python%203.9%2B-blue.svg)](waaree_api_client.py)
[![Tests](https://img.shields.io/badge/tests-42%20passed-brightgreen.svg)](tests/)
[![Architecture](https://img.shields.io/badge/architecture-Schema%20v5.0-orange.svg)](docs/01-ARCHITECTURE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. What SolarIntelligence Does

SolarIntelligence provides automated, high-fidelity data collection and analytics for a **2.32 kW rooftop photovoltaic (PV) array** installed in Berhampur, Odisha, India.

- **Automated Data Pipeline:** Pulls generation telemetry directly from the Waaree / FoxESS Cloud REST API using reverse-engineered MD5 authentication signatures and JWT tokens (replacing legacy, fragile Selenium scrapers).
- **Consolidated CSV History:** Maintains `data/energy_history.csv` with daily totals and hourly generation columns (`h05_kw` to `h19_kw`).
- **Immutable Daily Logs:** Archives daily generation profiles in `data/energy_logs/` as audit-ready JSON snapshots.
- **Client-Side Visualizer:** Single-file `index.html` with interactive power curves, 7-day trends, monthly generation charts, and estimated tariff savings.

```text
  Solar Intelligence Dashboard (Schema v5.0)
  Plant: 2.32 kW Rooftop PV · Berhampur, Odisha
  ─────────────────────────────────────────────────────────────
  Current Power:  1.54 kW   ██████████░░░░  (66.3% capacity)
  Today's Yield:  3.10 kWh  |  Monthly Yield: 43.40 kWh
  Total Lifetime: 984.3 kWh |  Est. Value:   ₹15.50 (today)
  Inverter State: Online    |  Data Quality: 100/100
```

---

## 2. Why It Exists

Most residential solar inverters in India come bundled with proprietary, ad-heavy mobile applications that:
- Offer limited data export options or lock raw data behind vendor walls.
- Provide no automated integration for home automation, personal dashboards, or long-term degradation tracking.
- Frequently fail to display granular hourly breakdown profiles.

**SolarIntelligence solves this through open engineering:**
- **Direct API Protocol:** Fast (<1s) authenticated requests to portal endpoints. No headless browsers or emulators.
- **Data Provenance & Transparency:** Every reading is timestamped and categorized by data origin (`api` vs `estimate`).
- **Zero-Dependency Frontend:** The visualization runs statically in any browser without npm, node_modules, or server rendering.

---

## 3. Data Provenance & Sensor Boundaries

To ensure engineering rigor, this repository explicitly separates measured sensor telemetry from computed values and hardware limitations:

| Metric | Origin | Measurement Interval | Description / Boundaries |
|---|---|---|---|
| `power_kw` | **Measured** | 5–15 min (inverter push) | Instantaneous AC active power reported by the inverter telemetry unit. |
| `daily_yield_kwh` | **Measured** | Cumulative (daily reset) | Energy accumulator register inside the inverter firmware. |
| `hourly (h05–h19)` | **Measured** | Hourly aggregated | Hourly energy generation points returned by the FoxESS cloud report API. |
| `income_inr` | *Computed Estimate* | Per daily update | Calculated as `daily_yield_kwh * 5.0 INR/kWh` (standard Odisha DISCOM grid-tied tariff baseline). Not an official electricity bill statement. |
| `avg_power_kw` | *Computed* | Daily | Mean active power across active daylight generation hours. |
| `voltage_v` / `current_a` | *Unavailable* | N/A | Basic cloud API tiers for this residential inverter model omit DC string voltage, DC current, and internal heatsink temperature. These fields report `0` and are not fabricated. |

> [!IMPORTANT]
> **Safety Notice:** This software is for monitoring and performance evaluation only. It does not control inverter relays, grid synchronization parameters, or electrical disconnects. Always consult a certified electrical technician before servicing PV hardware.

---

## 4. Implementation Status

| Component | Status | Description |
|---|---|---|
| **API Client (`waaree_api_client.py`)** | **Production-Ready** | Handles MD5 signature calculation (`path\r\ntoken\r\nlang\r\ntimestamp.5245784`), JWT session renewal, and automatic retry. |
| **Pipeline CLI (`update_data.py`)** | **Production-Ready** | Reconciles hourly peaks, updates `data/dashboard.json` (Schema v5.0), and updates `data/energy_history.csv`. |
| **Local API Server (`scraper_api.py`)** | **Production-Ready** | Lightweight Flask API exposing `/api/live`, `/api/hourly`, `/api/daily`, and `/api/dashboard`. |
| **Single-Page Dashboard (`index.html`)** | **Production-Ready** | Responsive UI with Chart.js, solar diurnal curves, theme switching, and local metric calculation. |
| **Automated Testing Suite** | **Production-Ready** | Unit tests validating schema invariants, physical bounds, CSV integrity, and deterministic signature generation. |

---

## 5. Architecture & Data Flow

```text
┌─────────────────────────────────────────────────────────────┐
│                 digital.waaree.com (FoxESS)                 │
│                 REST API (/c/v0, /generic/v0)               │
└───────────────┬─────────────────────────────────────────────┘
                │ Authenticated HTTPS (MD5 Signature + JWT)
                ▼
┌─────────────────────────────────────────────────────────────┐
│                     waaree_api_client.py                    │
│   Token Cache (.waaree_token.json) · Automatic Relogin      │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│      scraper_api.py          │ │      update_data.py        │
│   (Flask server on :8006)    │ │   (Batch update pipeline)  │
└───────────────┬──────────────┘ └────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  data/ Store (Single Source)                │
│  - data/dashboard.json (Schema v5.0 payload)                │
│  - data/energy_history.csv (Daily rows with hourly columns) │
│  - data/energy_logs/solar_energy_YYYY-MM-DD.json            │
└──────────────────────────────┬──────────────────────────────┘
                               │ Static JSON Fetch
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Dashboard (index.html)                  │
│       Served via GitHub Pages or local HTTP server          │
└─────────────────────────────────────────────────────────────┘
```

### FoxESS / Waaree Cloud API Signature Protocol

Requests to the cloud portal (`/c/v0/...` and `/generic/v0/...`) require an MD5 request signature header alongside the bearer token:

```python
signature = hashlib.md5(
    f"{path}\r\n{token}\r\n{lang}\r\n{timestamp}.{CLIENT_ID}".encode("utf-8")
).hexdigest()
```

- **`CLIENT_ID`**: Fixed portal identifier `5245784`
- **`lang`**: Client language code (default: `en`)
- **`timestamp`**: Epoch timestamp in milliseconds
- **Headers Sent**: `token`, `timestamp`, `signature`, `lang: en`

---

## 6. Quick Start & Setup

### Prerequisites
- Python 3.9+ (`pip install -r requirements.txt`)
- Modern web browser

### Local Development Setup

```bash
git clone https://github.com/bhargavachary/solar-intelligence.git
cd solar-intelligence
pip install -r requirements.txt
```

### Developer Commands (`Makefile`)

The repository includes a self-documenting `Makefile` for developer hygiene:

```bash
make test    # Run full unit test suite (42 tests across schema, math, API)
make lint    # Validate Python bytecode compilation across all modules
make demo    # Run update pipeline with simulated telemetry (zero credentials required)
make serve   # Launch local dashboard server on http://localhost:8080
```

### Running Automated Tests

```bash
python3 -m unittest discover -s tests -v
```

### Viewing the Dashboard
You can inspect the live dashboard immediately with existing archived telemetry:

```bash
make serve
# Or: python3 -m http.server 8080
# Open http://localhost:8080 in your browser
```

### Offline Simulation Mode (No Credentials Needed)
Anyone can test and run the complete data pipeline without proprietary inverter credentials:

```bash
# Run pipeline dry-run with mock telemetry:
python3 update_data.py --mock --dry-run

# Run local API server with mock telemetry:
python3 scraper_api.py --mock
```

### Fetching Fresh Live Telemetry (Plant Account Required)
To fetch real telemetry from an active Waaree / FoxESS inverter, provide credentials via environment variables or a local JSON file:

**Option A (Environment Variables):**
```bash
export WAAREE_USERNAME="your_portal_username"
export WAAREE_PASSWORD="your_portal_password"
python3 update_data.py
```

**Option B (`credentials.json`, git-ignored):**
```json
{
  "username": "your_portal_username",
  "password": "your_portal_password"
}
```

```bash
python3 update_data.py
```

---

## 7. Limitations & Known Boundaries

1. **Authentication Token Lifecycle:** JWT session tokens expire approximately every 2 hours. The client automatically refreshes tokens on expiration.
2. **Reverse-Engineered Endpoints:** FoxESS Cloud portal changes may require header updates. Current implementation tracks the standard `5245784` client identifier.
3. **Sensor Granularity:** Cloud polling is restricted to reasonable intervals (5–15 minutes) to avoid vendor rate-limiting.

---

## 8. Contributing

Contributions and bug reports are welcome:
1. Ensure all physical constraint tests pass: `python3 -m unittest discover -s tests -v`.
2. Do not commit credentials, tokens, or simulated non-physical readings to `data/`.
3. Open a Pull Request detailing the changes and test evidence.

---

## 9. License

Released under the [MIT License](LICENSE). Copyright © D K Bhargav Achary.
