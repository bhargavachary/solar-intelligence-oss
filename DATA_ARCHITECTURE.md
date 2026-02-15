# Solar Data Architecture — Day-wise Segregation

## Overview
Segregates minute/hour-level telemetry into immutable daily archives while maintaining a lightweight dashboard summary for web rendering.

## File Structure

```
data/
├── dashboard_data.json           # Lightweight summary for web (≤20KB)
└── archives/
    ├── solar_energy_2026-02-15.json
    ├── solar_energy_2026-02-14.json
    └── ...
```

## Data Flow

1. **Live scraper** → `waaree_deep_crawler.py` → collects minute/hour data
2. **Archive manager** → segregates by date → writes `solar_energy_<date>.json`
3. **Dashboard builder** → aggregates archives → writes `dashboard_data.json`

## File Specifications

### `solar_energy_<date>.json` (Daily Archive — **IMMUTABLE**)
- **Naming**: `solar_energy_YYYY-MM-DD.json` (e.g., `solar_energy_2026-02-15.json`)
- **Content**: Full minute/hour arc for that calendar day (6:00 AM – 6:00 PM)
- **Immutability**: Once written, never modified (source of truth)
- **Structure**:
```json
{
  "date": "2026-02-15",
  "plant_id": "628c63b5-06c3-4b1b-a06a-556e87fd4a81",
  "meta": {
    "plant_capacity_kw": 2.32,
    "location": "Berhampur, Odisha",
    "archived_at": "2026-02-15 18:30:00",
    "record_count": 13,
    "sampling_interval": "hourly"
  },
  "daily_summary": {
    "peak_power_kw": 1.502,
    "total_yield_kwh": 11.1,
    "avg_voltage_v": 232.2,
    "uptime_hours": 11
  },
  "records": [
    {
      "timestamp": "2026-02-15 06:30:00",
      "power_kw": 0.103,
      "daily_yield_kwh": 0.24,
      "voltage_v": 230.8,
      "current_a": 0.45,
      "temperature_c": 27.8
    },
    ...
  ]
}
```

### `dashboard_data.json` (Web Summary — **MUTABLE**)
- **Purpose**: Lightweight data for web dashboard rendering
- **Content**: 
  - Latest live reading (1 point)
  - Last 7 days summary (7 points)
  - Monthly/annual aggregates
  - Analytics (forecasts, insights, health scores)
- **Size target**: ≤20KB (fast loading)
- **Structure**:
```json
{
  "meta": { ... },
  "live": {
    "timestamp": "2026-02-15 17:31:11",
    "power_kw": 0.04,
    "daily_yield_kwh": 11.1,
    "monthly_yield_kwh": 20.5,
    "total_yield_kwh": 68.3
  },
  "last_7_days": [
    {"date": "2026-02-09", "yield_kwh": 0.0, "peak_power_kw": 0.0},
    {"date": "2026-02-10", "yield_kwh": 0.0, "peak_power_kw": 0.0},
    ...
    {"date": "2026-02-15", "yield_kwh": 11.1, "peak_power_kw": 1.502}
  ],
  "monthly": {
    "february_2026": {"yield_kwh": 20.5, "days_active": 7}
  },
  "analytics": { ... }
}
```

## Scripts

### `archive_daily_data.py`
- Reads current `dashboard_data.json`
- Extracts records for a given date
- Writes immutable `solar_energy_<date>.json`
- **Never** overwrites existing archives

### `build_dashboard_summary.py`
- Reads all archives in `data/archives/`
- Aggregates last 7 days + monthly totals
- Writes lightweight `dashboard_data.json`
- Run this after new archive is created

### `update_data.py` (modified)
- After live scrape, calls `archive_daily_data.py` for today
- Then calls `build_dashboard_summary.py` to refresh dashboard

## Migration Plan

1. Create `data/archives/` directory
2. Extract today's data from current `dashboard_data.json` → `solar_energy_2026-02-15.json`
3. Run `build_dashboard_summary.py` to create new lightweight dashboard
4. Update `index.html` to read new structure (minimal changes)
5. Git commit archives separately from dashboard summary

## Benefits

✅ **Immutable archives** — never lose historical data  
✅ **Fast dashboard** — only loads summary (20KB vs 100KB+)  
✅ **Replay capability** — can rebuild dashboard from archives  
✅ **Analytics ready** — can run ML models on full historical data  
✅ **Git friendly** — archives change once, dashboard updates frequently
