# Waaree API Access - Solarman Smart PV API Client

A production-ready Python client for accessing real-time data from the Solarman Smart PV (V5) API.

## Features

- 🔐 **Secure Authentication**: SHA-256 password hashing before API calls
- 🏭 **Station Management**: Retrieve list of all solar stations in your account
- 📊 **Real-time Data**: Fetch live data from solar stations
- 🛡️ **Error Handling**: Comprehensive error handling with informative messages
- 📝 **Logging**: Built-in logging for debugging and monitoring
- 🔄 **Session Management**: Uses connection pooling for improved performance
- 🎯 **Type Hints**: Full type annotations for better IDE support

## Installation

1. Clone the repository:
```bash
git clone https://github.com/bhargavachary/waaree_api_access.git
cd waaree_api_access
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Requirements

- Python 3.7+
- requests library

## Configuration

Before using the script, you need to obtain API credentials from Solarman:

1. **APP_ID**: Your application ID
2. **APP_SECRET**: Your application secret
3. **EMAIL**: Your Solarman account email
4. **PASSWORD**: Your Solarman account password

## Usage

### Basic Usage

Edit the `solarman_api.py` file and replace the placeholder values:

```python
APP_ID = "YOUR_APP_ID"  # Replace with your App ID
APP_SECRET = "YOUR_APP_SECRET"  # Replace with your App Secret
EMAIL = "your.email@example.com"  # Replace with your email
PASSWORD = "your_password"  # Replace with your password
```

Then run the script:

```bash
python solarman_api.py
```

### Using as a Module

You can also import and use the `SolarmanAPI` class in your own scripts:

```python
from solarman_api import SolarmanAPI

# Initialize the API client
api = SolarmanAPI(
    app_id="YOUR_APP_ID",
    app_secret="YOUR_APP_SECRET",
    email="your.email@example.com",
    password="your_password"
)

# Login to get access token
access_token = api.login()

# Get list of stations
stations = api.get_station_list()

# Get real-time data for a specific station
station_id = stations[0]['id']
realtime_data = api.get_realtime_data(str(station_id))

# Or fetch data from all stations at once
all_data = api.fetch_all_stations_data()

# Close the session
api.close()
```

### Using Context Manager

The recommended way is to use the context manager for automatic cleanup:

```python
from solarman_api import SolarmanAPI

with SolarmanAPI(app_id, app_secret, email, password) as api:
    api.login()
    stations = api.get_station_list()
    data = api.get_realtime_data(str(stations[0]['id']))
    print(data)
```

## API Endpoints

The script interacts with the following Solarman API endpoints:

1. **Authentication**: `POST /account/v1.0/token`
   - Authenticates user and returns access token
   - Password is hashed with SHA-256 before sending

2. **Station List**: `POST /station/v1.0/list`
   - Retrieves list of all stations associated with the account
   - Requires authentication token

3. **Real-time Data**: `POST /station/v1.0/realTime`
   - Fetches real-time data from a specific station
   - Requires authentication token and station ID

## API Flow

```
1. Login (POST /account/v1.0/token)
   ↓
2. Get Access Token
   ↓
3. Fetch Station List (POST /station/v1.0/list)
   ↓
4. Get Station IDs
   ↓
5. Fetch Real-time Data (POST /station/v1.0/realTime)
```

## Error Handling

The script includes comprehensive error handling for:

- Network connectivity issues
- HTTP errors (4xx, 5xx)
- API-level errors
- Invalid credentials
- Missing parameters
- Timeout errors
- JSON parsing errors

All errors are logged and raised as `SolarmanAPIError` exceptions.

## Logging

The script uses Python's built-in logging module. By default, it logs to stdout with INFO level. You can adjust the logging level:

```python
import logging
logging.getLogger('solarman_api').setLevel(logging.DEBUG)
```

## Security Notes

- ✅ Passwords are hashed using SHA-256 before transmission
- ✅ Uses HTTPS for all API communications
- ✅ Session tokens are managed securely
- ⚠️ Never commit credentials to version control
- ⚠️ Use environment variables for sensitive data in production

## Example Output

```
2024-01-01 10:00:00 - solarman_api - INFO - Logging in as user@example.com...
2024-01-01 10:00:01 - solarman_api - INFO - Login successful
2024-01-01 10:00:01 - solarman_api - INFO - Fetching station list...
2024-01-01 10:00:02 - solarman_api - INFO - Found 2 station(s)
2024-01-01 10:00:02 - solarman_api - INFO - Fetching real-time data for station 12345...
2024-01-01 10:00:03 - solarman_api - INFO - Successfully fetched real-time data for station 12345
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Disclaimer

This is an unofficial client for the Solarman API. Use at your own risk. The authors are not responsible for any damages or issues that may arise from using this software.

## Support

For issues related to the API itself, please contact Solarman support. For issues with this client, please open an issue on GitHub.
