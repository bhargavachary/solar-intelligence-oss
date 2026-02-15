# Day-wise Data Segregation Implementation — Complete

## ✅ What's Implemented

### Architecture
- **Immutable daily archives**: `data/archives/solar_energy_<date>.json`
- **Lightweight dashboard**: `data/dashboard_data.json` (1.3 KB vs 13 KB old)
- **Schema v5.0**: New data structure with `live`, `last_7_days`, `monthly`, `analytics`

### Scripts Created

1. **`scripts/archive_daily_data.py`**
   - Archives data for a specific date or all dates (backfill)
   - Creates immutable `solar_energy_YYYY-MM-DD.json` files
   - Never overwrites existing archives (use `--force` to override)
   - Usage:
     ```bash
     python scripts/archive_daily_data.py              # archive today
     python scripts/archive_daily_data.py 2026-02-15  # archive specific date
     python scripts/archive_daily_data.py --backfill  # archive all dates
     ```

2. **`scripts/build_dashboard_summary.py`**
   - Aggregates all archives into lightweight dashboard summary
   - Output: `data/dashboard_data.json` (≤2 KB)
   - Computes: latest reading, last 7 days, monthly totals, analytics
   - Usage:
     ```bash
     python scripts/build_dashboard_summary.py         # rebuild dashboard
     python scripts/build_dashboard_summary.py --verbose  # verbose output
     ```

### Frontend Compatibility

- **`index.html`** updated with schema v5.0 adapter in `normalizeRecords()`
- Detects schema version and handles both:
  - Legacy: `payload.history` array
  - New: `payload.live` + `last_7_days` + `monthly`
- No breaking changes — dashboard renders correctly with new data

## 📊 File Size Comparison

```
OLD:     data/dashboard_data.json = 13 KB  (13 records in history array)
NEW:     data/dashboard_data.json = 1.3 KB (lightweight summary)
ARCHIVE: solar_energy_2026-02-15.json = 8.7 KB (immutable, 13 records)
```

**Result**: 10× reduction in dashboard JSON size → faster page load

## 🔄 Daily Workflow

### After Live Scrape
```bash
# 1. Archive today's data
python scripts/archive_daily_data.py

# 2. Rebuild dashboard summary
python scripts/build_dashboard_summary.py
```

### Migration from Old Data
```bash
# Extract all historical dates from current dashboard_data.json
python scripts/archive_daily_data.py --backfill

# Rebuild lightweight summary
python scripts/build_dashboard_summary.py
```

## 📂 Archive File Structure

`data/archives/solar_energy_2026-02-15.json`:
```json
{
  "date": "2026-02-15",
  "plant_id": "628c63b5-06c3-4b1b-a06a-556e87fd4a81",
  "meta": {
    "plant_capacity_kw": 2.32,
    "location": "Berhampur, Odisha",
    "archived_at": "2026-02-15 18:19:55",
    "record_count": 13,
    "sampling_interval": "hourly",
    "data_source": "live_portal"
  },
  "daily_summary": {
    "date": "2026-02-15",
    "total_yield_kwh": 11.1,
    "peak_power_kw": 1.502,
    "avg_power_kw": 0.857,
    "avg_voltage_v": 232.2,
    "record_count": 13,
    "first_reading": "2026-02-15 06:30:00",
    "last_reading": "2026-02-15 17:31:11"
  },
  "records": [
    {
      "timestamp": "2026-02-15 06:30:00",
      "current_power_kw": 0.103,
      "daily_yield_kwh": 0.24,
      "voltage_v": 230.8,
      ...
    },
    ...
  ]
}
```

## 📊 Dashboard Summary Structure

`data/dashboard_data.json`:
```json
{
  "meta": {
    "schema_version": "5.0",
    "generated_at": "2026-02-15 18:19:55",
    "plant_id": "628c63b5-06c3-4b1b-a06a-556e87fd4a81",
    "plant_capacity_kw": 2.32,
    "location": "Berhampur, Odisha",
    "data_source": "archived",
    "archive_count": 1,
    "date_range": {"first": "2026-02-15", "last": "2026-02-15"}
  },
  "live": {
    "timestamp": "2026-02-15 17:31:11",
    "power_kw": 0.04,
    "daily_yield_kwh": 11.1,
    "monthly_yield_kwh": 20.5,
    "total_yield_kwh": 68.3,
    "income_inr": 204.9,
    "status": "Online"
  },
  "last_7_days": [
    {"date": "2026-02-15", "yield_kwh": 11.1, "peak_power_kw": 1.502}
  ],
  "monthly": {
    "february_2026": {"yield_kwh": 11.1, "days_active": 1, "peak_power_kw": 1.502}
  },
  "analytics": {
    "health": {"overall_score": 92.5, "grade": "A+"},
    "capacity_factor_pct": 19.9,
    "performance_ratio_pct": 95.7,
    "daily_progress": [{"date": "2026-02-15", "yield_kwh": 11.1}],
    "seasonal_forecast": {"annual_kwh": 4051.5}
  }
}
```

## 🎯 Benefits Achieved

✅ **Immutability**: Archives never modified after creation  
✅ **Fast dashboard**: 1.3 KB vs 13 KB (10× smaller)  
✅ **Source of truth**: Full minute/hour data preserved in archives  
✅ **Replay capability**: Can rebuild dashboard from archives  
✅ **Git friendly**: Archives committed once, dashboard updates frequently  
✅ **Analytics ready**: Full historical data available for ML models  
✅ **Scalability**: Dashboard size stays constant even with years of data  

## ⚠️ Important Rules

1. **NEVER modify archives** after creation  
2. **Always run both scripts** after live scrape:
   - `archive_daily_data.py` → creates/updates today's archive
   - `build_dashboard_summary.py` → refreshes dashboard
3. **Commit archives separately** from dashboard in git (archives = infrequent, dashboard = frequent)

## 🔧 Next Steps

1. **Update `update_data.py`** to call archiver + builder after scrape
2. **Gitignore strategy**: Consider `.gitignore` for `dashboard_data.json` (rebuilt from archives)
3. **Retention policy**: Decide if/when to compress old archives (e.g., >1 year old)
4. **API endpoint**: Optional `/api/date/<YYYY-MM-DD>` to serve individual archives
