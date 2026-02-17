# Waaree Solar Portal API — Complete Reference

## Overview

The Waaree digital solar monitoring portal (`https://digital.waaree.com`) is built on the
**FoxESS Cloud** platform. It exposes a REST-style JSON API secured by a custom HMAC-like
signature scheme. This document captures every finding from the 14-phase reverse-engineering
investigation and explains how to use the API programmatically.

---

## Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Fetch live dashboard data
python3 waaree_api_client.py --dashboard

# Get today's hourly generation
python3 waaree_api_client.py --hourly

# Get this month's daily breakdown
python3 waaree_api_client.py --monthly

# JSON output for scripting
python3 waaree_api_client.py --dashboard --json

# Start the HTTP API server (dashboard calls this)
python3 scraper_api.py
```

---

## Architecture

```
┌─────────────────────┐      HTTPS/JSON      ┌────────────────────────┐
│  waaree_api_client   │ ──────────────────►  │  digital.waaree.com    │
│  (Python)            │                      │  (FoxESS Cloud SPA)    │
└─────────────────────┘                      └────────────────────────┘
        │                                              │
        ▼                                              ▼
┌─────────────────────┐                      ┌────────────────────────┐
│  scraper_api.py      │                      │  /c/v0/*  /generic/*   │
│  (Flask HTTP server) │                      │  REST API endpoints    │
└─────────────────────┘                      └────────────────────────┘
        │
        ▼
┌─────────────────────┐
│  data/dashboard_     │
│  data.json           │ ◄── read by index.html
└─────────────────────┘
```

---

## Authentication

### 1. Signature Algorithm

Every request must carry a `Signature` header. The algorithm is:

```python
import hashlib

def compute_signature(path: str, token: str, lang: str, timestamp: str) -> str:
    """
    Portal-style signature.
    
    CRITICAL: \\r\\n are the LITERAL 4 characters (backslash-r-backslash-n),
    NOT carriage-return + line-feed bytes. Use Python raw f-strings.
    """
    sig_input = fr"{path}\r\n{token}\r\n{lang}\r\n{timestamp}"
    md5_hash = hashlib.md5(sig_input.encode("UTF-8")).hexdigest()
    return md5_hash + ".5245784"   # client_id suffix is mandatory
```

| Component      | Value / Source                          |
|----------------|----------------------------------------|
| `path`         | API path, e.g. `/c/v0/user/login`      |
| `token`        | JWT from login (empty string for login) |
| `lang`         | `"en"` (always)                        |
| `timestamp`    | Unix epoch in milliseconds as string   |
| `".5245784"`   | FoxESS Cloud client_id (hardcoded)     |

**Two variants exist** (only the portal variant works on Waaree):

| Variant    | Formula                                    | Used On         |
|------------|---------------------------------------------|-----------------|
| **Portal** | `MD5(path\r\ntoken\r\nlang\r\nts) + ".5245784"` | digital.waaree.com |
| OpenAPI    | `MD5(path\r\ntoken\r\nts)` (no lang, no suffix) | foxesscloud.com OpenAPI (not on Waaree) |

### 2. Required Headers

```python
headers = {
    "Token": "<jwt_token>",         # empty string for login
    "Lang": "en",
    "Timestamp": "1739789123456",   # epoch ms
    "Signature": "<computed>",
    "Timezone": "Asia/Kolkata",
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "Mozilla/5.0 ...",
}
```

### 3. Login

```
POST /c/v0/user/login
Body: {"user": "bhargavachary", "password": "<md5_of_password>"}
```

- Password MUST be MD5-hashed before sending:
  `hashlib.md5("R@m131091".encode()).hexdigest()`
- Response: `{"errno": 0, "result": {"token": "<jwt>", "access": 1, ...}}`
- Token valid for ~2 hours
- **CRITICAL**: Must send body with `data=json.dumps(payload)` NOT `json=payload`
  (the latter changes Content-Type and triggers 406 Not Acceptable)

### 4. Error Codes

| errno  | Meaning                        |
|--------|--------------------------------|
| 0      | Success                        |
| 41808  | Token is invalid               |
| 41809  | Signature verification failed  |
| 41810  | User has logged in elsewhere   |
| 41811  | Permission denied              |
| 41930  | Feature not available          |
| 40261  | Invalid parameter              |

---

## Working Endpoints

### User

| Method | Path                       | Body      | Returns              |
|--------|----------------------------|-----------|----------------------|
| GET    | `/c/v0/user/info`          | —         | Name, email, country |
| GET    | `/c/v0/user/access`        | —         | Access level         |
| GET    | `/generic/v0/user/api/get` | —         | API key quota info   |

### Plants

| Method | Path                         | Body                                   | Returns                          |
|--------|------------------------------|-----------------------------------------|----------------------------------|
| POST   | `/c/v0/plant/list`           | `{"currentPage":1, "pageSize":10}`     | Plant list with stationID        |
| POST   | `/c/v0/plant/device/list`    | `{"stationID":"...", "currentPage":1, "pageSize":100}` | Devices in a plant |

> **KNOWN BUG**: `pageSize > 10` returns empty results on `/c/v0/plant/list`.
> Always use `pageSize: 10` or less.

### Devices

| Method | Path                  | Body                                   | Returns                          |
|--------|-----------------------|-----------------------------------------|----------------------------------|
| POST   | `/c/v0/device/list`   | `{"currentPage":1, "pageSize":100}`    | All devices with live data       |
| POST   | `/c/v0/module/list`   | `{"currentPage":1, "pageSize":100}`    | Communication modules            |

Device list returns real-time fields:
- `power` (kW) — current AC output
- `generationToday` (kWh)
- `generationTotal` (kWh)
- `status` (0=offline, 1=online, 2=fault)
- `dataLatestUploadDate` — last data push from inverter

### Generation Reports

| Method | Path                                | Body                                          | Returns          |
|--------|-------------------------------------|-----------------------------------------------|------------------|
| POST   | `/generic/v0/plant/history/report`  | See below                                     | Time-series data |

**Hourly** (today's hour-by-hour):
```json
{
    "stationID": "628c63b5-06c3-4b1b-a06a-556e87fd4a81",
    "reportType": "day",
    "variables": ["generation", "feedin", "gridConsumption",
                  "chargeEnergyToTal", "dischargeEnergyToTal"],
    "queryDate": {"year": 2026, "month": 2, "day": 17}
}
```

**Daily** (day-by-day in a month):
```json
{
    "stationID": "...",
    "reportType": "month",
    "variables": ["generation"],
    "queryDate": {"year": 2026, "month": 2}
}
```

**Monthly** (month-by-month in a year):
```json
{
    "stationID": "...",
    "reportType": "year",
    "variables": ["generation"],
    "queryDate": {"year": 2026}
}
```

Response format:
```json
[
    {
        "variable": "generation",
        "unit": "kWh",
        "data": [
            {"index": 8, "value": 0.2},
            {"index": 9, "value": 0.6},
            ...
        ]
    }
]
```

### Error Messages

| Method | Path                     | Body | Returns                          |
|--------|--------------------------|------|----------------------------------|
| GET    | `/c/v0/errors/message`   | —    | All error code → message mappings |

---

## Non-Working Endpoints (404 or Permission Denied on Waaree)

These are FoxESS-standard paths discovered in JavaScript bundles but NOT implemented
on the Waaree portal:

| Path                              | Error  | Notes                              |
|-----------------------------------|--------|------------------------------------|
| `/c/v0/device/real/query`         | 404    | Real-time PV variables             |
| `/c/v0/device/real/all`           | 404    | All real-time variables            |
| `/c/v0/device/real/flow`          | 404    | Energy flow diagram data           |
| `/c/v0/device/history/raw`        | 40261  | Raw history (param error)          |
| `/c/v0/device/earnings`           | 41930  | Earnings data                      |
| `/c/v0/device/report/query`       | 41811  | Permission denied                  |
| `/c/v0/plant/status/all`          | 404    | All plant statuses                 |
| `/c/v0/plant/status/detail`       | 404    | Detailed plant status              |
| `/c/v0/plant/earnings/*`          | 404    | Plant earnings endpoints           |
| `/op/v0/*`                        | 401    | OpenAPI format (not on Waaree)     |

---

## Plant & Device Details

| Field          | Value                                          |
|----------------|------------------------------------------------|
| Plant Name     | DJA Kuteer                                     |
| Station ID     | `628c63b5-06c3-4b1b-a06a-556e87fd4a81`         |
| City           | Berhampur, Odisha, India                       |
| Capacity       | 2.32 kW                                        |
| Device SN      | `B0VS3320598K520`                              |
| Device ID      | `8212a76e-0625-4452-bb06-45b2295de7a6`         |
| Module SN      | `B09W6DUF584A114`                              |
| Product Type   | S3                                             |
| Feed-in Date   | 2026-02-14                                     |
| API Key        | `18fbf95a-fb2c-42cc-9e34-8cff2fd1aa36`         |
| API Quota      | 1440 calls/day                                 |

---

## Files

| File                     | Purpose                                         |
|--------------------------|-------------------------------------------------|
| `waaree_api_client.py`   | Core API client class + CLI                     |
| `scraper_api.py`         | Flask HTTP server (replaces Selenium scraper)   |
| `credentials.json`       | Username, password, plant config                |
| `.waaree_token.json`     | Cached JWT token (auto-created)                 |
| `data/dashboard.json`      | Dashboard data file (read by `index.html`)    |
| `scraper_api_old.py`     | Old Selenium-based scraper server (deprecated)  |
| `waaree_deep_crawler.py` | Old Selenium crawler (deprecated, 2122 lines)   |

---

## HTTP API Server Endpoints

Start with: `python3 scraper_api.py` (listens on port 8006)

| Method | Path              | Description                                |
|--------|-------------------|--------------------------------------------|
| POST   | `/trigger_scrape` | Fetch data & update dashboard JSON (async) |
| GET    | `/status`         | Last update status + timestamp             |
| GET    | `/health`         | Health check                               |
| GET    | `/api/live`       | Live power, yield, status from API         |
| GET    | `/api/hourly`     | Today's hourly generation                  |
| GET    | `/api/daily`      | This month's daily generation              |
| GET    | `/api/monthly`    | This year's monthly generation             |
| GET    | `/api/dashboard`  | Full dashboard payload (not written to file)|

---

## Investigation Summary

### What Was Tried

1. **Blind endpoint probing** — Tested `/api/`, `/bus/api/`, standard REST patterns.
   Result: 403 (WAF) or Vue SPA HTML shell.

2. **JavaScript bundle analysis** — Downloaded & analyzed 72 JS chunk files.
   Found: Vue.js SPA, WASM signature module, interceptor code, 244 unique API paths.

3. **FoxESS Cloud pattern** — Tested `/c/v0/*` and `/c/v1/*` endpoints.
   Result: Error 41809 (signature verification failed) = endpoints are REAL.

4. **Signature reverse engineering** — Found WASM `begin_signature(url, token, lang, timestamp)`.
   Matched to foxesscloud Python library's MD5 algorithm.

5. **The missing piece** — Appending `.5245784` (client_id) to the MD5 hash.
   Without this suffix: 41809 on every request. With it: success.

6. **Login 406 fix** — `json=payload` parameter in requests triggers 406.
   Must use `data=json.dumps(payload)` to keep Content-Type exact.

7. **pageSize bug** — `/c/v0/plant/list` with `pageSize > 10` returns empty.
   Always use `pageSize: 10`.

### What Doesn't Work

- **OpenAPI format** (`/op/v0/*`) returns 401 on foxesscloud.com; not available on Waaree
- **foxesscloud library** `get_site()`/`get_device()` return 41808 (token invalid on foxesscloud.com — data only on Waaree domain)
- **Real-time PV variables** (`/c/v0/device/real/*`) — 404, not implemented
- **Raw device history** (`/c/v0/device/history/raw`) — parameter error
- **Earnings endpoints** — not implemented or permission denied

### Performance Comparison

| Metric             | Old Selenium Scraper | New API Client |
|--------------------|---------------------|----------------|
| Data fetch time    | 45-120 seconds      | 2-4 seconds    |
| Dependencies       | Chrome, Selenium    | requests only  |
| Reliability        | ~60% success rate   | ~99%           |
| Data points        | 1 snapshot          | Hourly history |
| Code size          | 2122 lines          | ~560 lines     |
| Headless browser   | Required            | Not needed     |

---

## Rate Limits & Best Practices

- API quota: **1440 calls/day** (~1 per minute)
- Each dashboard update uses ~5 API calls (login, plants, devices, hourly, daily)
- Recommended update interval: **5 minutes** (288 updates/day = ~1440 API calls)
- Token caching reduces login calls; cached token valid ~2 hours
- Always handle errno 41808/41809 by re-authenticating
