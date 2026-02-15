# Solar Data Management Guide

## Overview

Daily solar telemetry is segregated into **immutable energy logs** (full minute/hour data) and a **lightweight dashboard summary** for web rendering.

## Architecture

```
data/
├── dashboard_data.json          # Lightweight summary for web (~1.3 KB)
│                                 # Contains: latest reading, 7-day summary, monthly totals, analytics
│
└── energy_logs/                  # Daily energy logs (immutable, source of truth)
    ├── solar_energy_2026-02-15.json  (~9 KB per day)
    ├── solar_energy_2026-02-14.json
    └── ...
```

### Energy Log Files (Immutable)

**Naming**: `solar_energy_YYYY-MM-DD.json`  
**Purpose**: Full minute/hour telemetry arc for each day  
**Rule**: Once written, never modified (source of truth)

**Structure**:
```json
{
  "date": "2026-02-15",
  "plant_id": "628c63b5-06c3-4b1b-a06a-556e87fd4a81",
  "meta": {
    "plant_capacity_kw": 2.32,
    "location": "Berhampur, Odisha",
    "archived_at": "2026-02-15 18:19:55",
    "record_count": 13,
    "sampling_interval": "hourly"
  },
  "daily_summary": {
    "total_yield_kwh": 11.1,
    "peak_power_kw": 1.502,
    "avg_power_kw": 0.857
  },
  "records": [...]
}
```

### Dashboard Summary (Derived)

**Purpose**: Lightweight data for web dashboard  
**Source**: Aggregated from energy logs  
**Size**: ~1.3 KB (10× smaller than old format)

**Schema v5.0 Structure**:
```json
{
  "meta": {"schema_version": "5.0", ...},
  "live": {latest reading},
  "last_7_days": [{day summaries}],
  "monthly": {monthly totals},
  "analytics": {forecasts, health, insights}
}
```

## Scripts

### `archive_daily_data.py`
Creates immutable daily energy logs.

```bash
# Log today's data
python scripts/archive_daily_data.py

# Log specific date
python scripts/archive_daily_data.py 2026-02-14

# Migrate all existing data
python scripts/archive_daily_data.py --backfill
```

### `build_dashboard_summary.py`
Aggregates energy logs into lightweight dashboard.

```bash
python scripts/build_dashboard_summary.py
python scripts/build_dashboard_summary.py --verbose
```

### `update_data.py` (Integrated Pipeline)
After live scrape: creates energy log → rebuilds dashboard.

```bash
python scripts/update_data.py --source live
```

## Daily Workflow

```bash
# Automatic (recommended)
python scripts/update_data.py --source live

# Manual
python scripts/archive_daily_data.py        # 1. Create today's log
python scripts/build_dashboard_summary.py   # 2. Rebuild dashboard
```

## Benefits

✓ **Immutable logs** — Historical data never lost  
✓ **Fast dashboard** — 1.3 KB vs 13 KB (10× smaller)  
✓ **Scalable** — Dashboard size stays constant  
✓ **Analytics ready** — Full historical data available  
✓ **Git friendly** — Logs committed once, dashboard updated frequently  

## Key Principles

1. Energy logs are **immutable** (never edit after creation)
2. Dashboard is **derived** (always rebuilt from logs)
3. Logs = **source of truth**, dashboard = **view**
4. One log per day: `solar_energy_YYYY-MM-DD.json`
5. Dashboard stays small: only latest + summaries

## Troubleshooting

**Dashboard not updating?**
```bash
python scripts/build_dashboard_summary.py --verbose
```

**Log already exists?**
```bash
# Use --force cautiously (loses immutability)
python scripts/archive_daily_data.py 2026-02-15 --force
```

**Check specific log:**
```bash
python3 -c "import json; d=json.load(open('data/energy_logs/solar_energy_2026-02-15.json')); print(f'Records: {len(d[\"records\"])}'); print(f'Yield: {d[\"daily_summary\"][\"total_yield_kwh\"]} kWh')"
```
