# Quick Start Guide - Solarman API Client

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bhargavachary/waaree_api_access.git
   cd waaree_api_access
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Getting Your API Credentials

To use this client, you need:
- **APP_ID**: Application ID from Solarman developer portal
- **APP_SECRET**: Application secret from Solarman developer portal
- **EMAIL**: Your Solarman account email
- **PASSWORD**: Your Solarman account password

## Quick Start

### Option 1: Run the Main Script

1. Edit `solarman_api.py` and replace the placeholders:
   ```python
   APP_ID = "your_actual_app_id"
   APP_SECRET = "your_actual_app_secret"
   EMAIL = "your.email@example.com"
   PASSWORD = "your_actual_password"
   ```

2. Run the script:
   ```bash
   python3 solarman_api.py
   ```

### Option 2: Use as a Module

Create a new Python file:

```python
from solarman_api import SolarmanAPI

# Initialize client
with SolarmanAPI(
    app_id="your_app_id",
    app_secret="your_app_secret",
    email="your_email",
    password="your_password"
) as api:
    # Login
    api.login()
    
    # Get stations
    stations = api.get_station_list()
    print(f"Found {len(stations)} stations")
    
    # Get real-time data from first station
    if stations:
        station_id = str(stations[0]['id'])
        data = api.get_realtime_data(station_id)
        print(f"Power: {data.get('power')} W")
```

### Option 3: Use Example Scripts

Run the examples to see different usage patterns:
```bash
python3 examples.py
```

## Running Tests

```bash
python3 test_solarman_api.py
```

Expected output:
```
======================================================================
SOLARMAN API - Unit Tests
======================================================================

... (test details) ...

----------------------------------------------------------------------
Ran 13 tests in 0.009s

OK
```

## API Workflow

The script follows this workflow:

```
1. Initialize SolarmanAPI with credentials
   ↓
2. Call api.login() → Get access token
   ↓
3. Call api.get_station_list() → Get list of stations
   ↓
4. Call api.get_realtime_data(station_id) → Get real-time data
```

## Common Use Cases

### Get Data from All Stations
```python
with SolarmanAPI(app_id, app_secret, email, password) as api:
    api.login()
    all_data = api.fetch_all_stations_data()
    for station_data in all_data:
        print(station_data)
```

### Get Data from Specific Station
```python
with SolarmanAPI(app_id, app_secret, email, password) as api:
    api.login()
    data = api.get_realtime_data("12345")
    print(data)
```

### Handle Errors
```python
from solarman_api import SolarmanAPI, SolarmanAPIError

try:
    with SolarmanAPI(app_id, app_secret, email, password) as api:
        api.login()
        stations = api.get_station_list()
except SolarmanAPIError as e:
    print(f"API Error: {e}")
except Exception as e:
    print(f"Error: {e}")
```

## Security Best Practices

1. **Never commit credentials to Git**
2. **Use environment variables for production:**
   ```python
   import os
   
   APP_ID = os.getenv('SOLARMAN_APP_ID')
   APP_SECRET = os.getenv('SOLARMAN_APP_SECRET')
   EMAIL = os.getenv('SOLARMAN_EMAIL')
   PASSWORD = os.getenv('SOLARMAN_PASSWORD')
   ```

3. **Use configuration files (excluded from Git):**
   ```python
   # Create config.py (not tracked in Git)
   from config import APP_ID, APP_SECRET, EMAIL, PASSWORD
   ```

## Troubleshooting

### Connection Errors
- Check your internet connection
- Verify the API endpoint is accessible
- Check firewall settings

### Authentication Errors
- Verify your credentials are correct
- Check if your account is active
- Ensure APP_ID and APP_SECRET are valid

### No Stations Found
- Verify your account has stations configured
- Check if you have the right permissions

## Next Steps

- Check `examples.py` for more usage patterns
- Read the full `README.md` for detailed documentation
- Run tests to verify your setup: `python3 test_solarman_api.py`

## Support

For API-related questions, contact Solarman support.
For client issues, open an issue on GitHub.
