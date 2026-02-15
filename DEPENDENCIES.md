# Waaree API Access — Dependencies & Installation

This project has two runtime parts:
- **Python crawler** (`waaree_deep_crawler.py`)
- **Web dashboard** (`dashboard.html` served via `python -m http.server`)

## 1) System dependencies (macOS)

### Google Chrome
Required by Selenium for browser automation.

- Install manually from: https://www.google.com/chrome/

### Tesseract OCR (for screenshot text validation)
Used by crawler function `extract_text_from_screenshot()`.

```bash
brew install tesseract
```

Verify:
```bash
tesseract --version
```

---

## 2) Python dependencies

Defined in [requirements.txt](requirements.txt):
- `selenium==4.40.0`
- `webdriver-manager==4.0.2`

### Install (recommended: project virtual environment)

```bash
cd /Users/bhargav/Documents/GitHub/waaree_api_access
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 3) Configuration file

Create/update [credentials.json](credentials.json):

```json
{
  "username": "YOUR_WAAREE_USERNAME",
  "password": "YOUR_WAAREE_PASSWORD",
  "plant_id": "YOUR_PLANT_ID",
  "plant_capacity_kw": 2.32,
  "daily_realistic_max_kwh": 12,
  "location": "Berhampur, Odisha"
}
```

Field notes:
- `plant_capacity_kw`: inverter/system size for data sanity checks.
- `daily_realistic_max_kwh`: expected upper daily generation (good day).
- `location`: used in predictive/seasonal UI context.

---

## 4) Run commands

### Start crawler
```bash
cd /Users/bhargav/Documents/GitHub/waaree_api_access
python waaree_deep_crawler.py
```

### Start dashboard server
```bash
cd /Users/bhargav/Documents/GitHub/waaree_api_access
python3 -m http.server 8005
```

Open:
- http://localhost:8005/dashboard.html

---

## 5) Output files generated

- `dashboard_data.json` → structured telemetry feed for UI
- `waaree_telemetry_log.csv` → historical raw log
- `system_snapshots/latest_dashboard_status.png` → latest visual evidence
- `waaree_session.pkl` → saved session cookies

---

## 6) Troubleshooting

### Dashboard shows DATA ERROR
- Ensure server runs from project folder.
- Ensure `dashboard_data.json` exists and contains valid JSON.

### OCR validation not working
- Confirm `tesseract` is installed and available in PATH.
- Re-run: `tesseract --version`

### Unrealistic power values
- Check `plant_capacity_kw` and `daily_realistic_max_kwh` in [credentials.json](credentials.json).
- Crawler now applies sanity checks and unit correction for outliers.
