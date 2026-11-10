#!/usr/bin/env python3
from __future__ import annotations
"""
Waaree Solar API Client
========================
Direct API access to Waaree digital portal (digital.waaree.com).
Replaces the unreliable Selenium-based web scraper.

Discovery Notes:
- Waaree portal is built on FoxESS Cloud platform
- Uses WASM-based signature in browser; Python equivalent found via foxesscloud library
- Portal API signature: MD5(path + literal_\\r\\n + token + literal_\\r\\n + lang + literal_\\r\\n + timestamp) + ".5245784"
- Login returns a JWT token valid for ~2 hours
- Token is required for all authenticated endpoints

Working Endpoints:
  POST /c/v0/user/login          - Login (returns token)
  GET  /c/v0/user/info           - User info
  GET  /c/v0/user/access         - User access level
  POST /c/v0/plant/list          - Plant list
  POST /c/v0/device/list         - Device list (current power, today/total generation)
  POST /c/v0/plant/device/list   - Plant devices
  POST /c/v0/module/list         - Module list
  POST /generic/v0/plant/history/report - Hourly/Daily/Monthly generation data
  GET  /generic/v0/user/api/get  - API key quota info
  GET  /c/v0/errors/message      - Error code translations
"""

import requests
import hashlib
import time
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

# Suppress SSL warnings for the portal
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("waaree_api")


class WaareeAPIClient:
    """Direct API client for Waaree digital solar monitoring portal."""

    BASE_URL = "https://digital.waaree.com"
    CLIENT_ID = "5245784"  # FoxESS Cloud client ID used in portal signature
    TOKEN_VALIDITY = timedelta(hours=2)
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, username: str, password: str, token_file: str | None = None):
        """
        Initialize with portal credentials.

        Args:
            username: Waaree portal username
            password: Waaree portal password (plain text)
            token_file: Optional file path to cache login token
        """
        self.username = username
        self.password = password
        self.password_md5 = hashlib.md5(password.encode()).hexdigest()
        self.token_file = token_file
        self.session = requests.Session()
        self._token: str | None = None
        self._token_time: datetime | None = None

    # ───────────────────────────────────────────
    # Signature & Headers
    # ───────────────────────────────────────────

    @staticmethod
    def _compute_signature(path: str, token: str, lang: str, timestamp: str) -> str:
        """
        Compute portal-style signature.
        
        Algorithm: MD5(path + literal_\\r\\n + token + literal_\\r\\n + lang + literal_\\r\\n + timestamp) + ".CLIENT_ID"
        Note: \\r\\n are the literal 4 characters backslash-r-backslash-n, NOT CRLF bytes.
        """
        sig_input = fr"{path}\r\n{token}\r\n{lang}\r\n{timestamp}"
        md5_hash = hashlib.md5(sig_input.encode("UTF-8")).hexdigest()
        return md5_hash + "." + WaareeAPIClient.CLIENT_ID

    def _headers(self, path: str, token: str = "", lang: str = "en") -> dict:
        """Build authenticated request headers."""
        ts = str(round(time.time() * 1000))
        return {
            "Token": token,
            "Lang": lang,
            "Timestamp": ts,
            "Signature": self._compute_signature(path, token, lang, ts),
            "Timezone": "Asia/Kolkata",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": self.USER_AGENT,
        }

    # ───────────────────────────────────────────
    # Authentication
    # ───────────────────────────────────────────

    def _load_cached_token(self) -> str | None:
        """Load token from cache file if still valid."""
        if not self.token_file or not os.path.exists(self.token_file):
            return None
        try:
            with open(self.token_file) as f:
                data = json.load(f)
            saved_time = datetime.fromisoformat(data["saved_at"])
            if datetime.now() - saved_time < self.TOKEN_VALIDITY:
                logger.debug("Using cached token")
                return data["token"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None

    def _save_token(self, token: str):
        """Save token to cache file."""
        if not self.token_file:
            return
        try:
            with open(self.token_file, "w") as f:
                json.dump({"token": token, "saved_at": datetime.now().isoformat()}, f)
        except OSError:
            pass

    def login(self) -> str:
        """
        Authenticate and obtain session token.
        
        Returns:
            JWT token string
            
        Raises:
            WaareeAPIError: If login fails
        """
        # Check cache first
        cached = self._load_cached_token()
        if cached:
            self._token = cached
            self._token_time = datetime.now()
            return cached

        path = "/c/v0/user/login"
        headers = self._headers(path, "", "en")
        payload = {"user": self.username, "password": self.password_md5}

        try:
            response = self.session.post(
                self.BASE_URL + path,
                headers=headers,
                data=json.dumps(payload),
                timeout=30,
                verify=False,
            )
        except requests.exceptions.RequestException as e:
            raise WaareeAPIError(f"Network error on login {path}: {e}") from e

        if response.status_code != 200:
            raise WaareeAPIError(f"Login HTTP error: {response.status_code}")

        try:
            data = response.json()
        except Exception as e:
            raise WaareeAPIError(f"Malformed JSON response on login: {e}") from e
        if data.get("errno") != 0:
            errno = data.get("errno")
            raise WaareeAPIError(f"Login failed: errno={errno}")

        self._token = data["result"]["token"]
        self._token_time = datetime.now()
        self._save_token(self._token)
        logger.info("Login successful")
        return self._token

    def _ensure_token(self):
        """Ensure we have a valid token, refreshing if needed."""
        if self._token and self._token_time:
            if datetime.now() - self._token_time < self.TOKEN_VALIDITY:
                return
        self.login()

    # ───────────────────────────────────────────
    # API Request Helpers
    # ───────────────────────────────────────────

    def _post(self, path: str, body: dict | None = None) -> dict:
        """Make authenticated POST request."""
        self._ensure_token()
        headers = self._headers(path, self._token, "en")
        try:
            response = self.session.post(
                self.BASE_URL + path,
                headers=headers,
                data=json.dumps(body or {}),
                timeout=30,
                verify=False,
            )
        except requests.exceptions.RequestException as e:
            raise WaareeAPIError(f"Network error on POST {path}: {e}") from e

        if response.status_code != 200:
            raise WaareeAPIError(f"HTTP {response.status_code} on POST {path}")
        try:
            data = response.json()
        except Exception as e:
            raise WaareeAPIError(f"Malformed JSON on POST {path}: {e}") from e

        if data.get("errno") != 0:
            raise WaareeAPIError(f"API error on {path}: errno={data.get('errno')}")
        return data.get("result", {})

    def _get(self, path: str, params: dict | None = None) -> dict:
        """Make authenticated GET request."""
        self._ensure_token()
        headers = self._headers(path, self._token, "en")
        try:
            response = self.session.get(
                self.BASE_URL + path,
                headers=headers,
                params=params,
                timeout=30,
                verify=False,
            )
        except requests.exceptions.RequestException as e:
            raise WaareeAPIError(f"Network error on GET {path}: {e}") from e

        if response.status_code != 200:
            raise WaareeAPIError(f"HTTP {response.status_code} on GET {path}")
        try:
            data = response.json()
        except Exception as e:
            raise WaareeAPIError(f"Malformed JSON on GET {path}: {e}") from e

        if data.get("errno") != 0:
            raise WaareeAPIError(f"API error on {path}: errno={data.get('errno')}")
        return data.get("result", {})

    # ───────────────────────────────────────────
    # User Info
    # ───────────────────────────────────────────

    def get_user_info(self) -> dict:
        """Get user profile information."""
        return self._get("/c/v0/user/info")

    def get_api_quota(self) -> dict:
        """Get API key usage quota (total and remaining daily calls)."""
        return self._get("/generic/v0/user/api/get")

    # ───────────────────────────────────────────
    # Plant Data
    # ───────────────────────────────────────────

    def get_plants(self) -> list[dict]:
        """Get list of all solar plants."""
        # Note: pageSize > 10 returns empty results on Waaree's API (known quirk)
        result = self._post("/c/v0/plant/list", {"currentPage": 1, "pageSize": 10})
        return result.get("plants", [])

    def get_plant_devices(self, station_id: str) -> list[dict]:
        """Get device list for a specific plant."""
        result = self._post("/c/v0/plant/device/list", {
            "stationID": station_id,
            "currentPage": 1,
            "pageSize": 100,
        })
        return result.get("devices", [])

    # ───────────────────────────────────────────
    # Device Data
    # ───────────────────────────────────────────

    def get_devices(self) -> list[dict]:
        """
        Get all devices with current status.
        
        Returns list of dicts with keys including:
            deviceSN, deviceID, moduleSN, plantName, deviceType,
            status, power (kW), generationToday (kWh), generationTotal (kWh),
            productType, hasBattery, hasPV, dataLatestUploadDate
        """
        result = self._post("/c/v0/device/list", {"currentPage": 1, "pageSize": 100})
        return result.get("devices", [])

    def get_modules(self) -> list[dict]:
        """Get communication module list."""
        result = self._post("/c/v0/module/list", {"currentPage": 1, "pageSize": 100})
        return result.get("data", [])

    # ───────────────────────────────────────────
    # Generation Reports
    # ───────────────────────────────────────────

    def get_hourly_generation(self, station_id: str, date: datetime | None = None) -> dict:
        """
        Get hourly generation data for a specific day.
        
        Args:
            station_id: Plant station ID
            date: Date to query (defaults to today)
            
        Returns:
            Dict with variable names as keys and list of (hour, kWh) tuples as values.
            Hours are 1-24, values are kWh generated in that hour.
        """
        if date is None:
            date = datetime.now()
        
        result = self._post("/generic/v0/plant/history/report", {
            "stationID": station_id,
            "reportType": "day",
            "variables": ["generation", "feedin", "gridConsumption",
                         "chargeEnergyToTal", "dischargeEnergyToTal"],
            "queryDate": {"year": date.year, "month": date.month, "day": date.day},
        })
        
        output = {}
        for var_data in result:
            var_name = var_data.get("variable", "unknown")
            data_points = var_data.get("data", [])
            output[var_name] = [
                (dp["index"], dp["value"])
                for dp in data_points
                if dp.get("value", 0) != 0
            ]
        return output

    def get_daily_generation(self, station_id: str, year: int, month: int) -> list[tuple]:
        """
        Get daily generation for a specific month.
        
        Args:
            station_id: Plant station ID
            year: Year
            month: Month (1-12)
            
        Returns:
            List of (day, kWh) tuples for days with generation.
        """
        result = self._post("/generic/v0/plant/history/report", {
            "stationID": station_id,
            "reportType": "month",
            "variables": ["generation"],
            "queryDate": {"year": year, "month": month},
        })
        
        for var_data in result:
            if var_data.get("variable") == "generation":
                return [
                    (dp["index"], dp["value"])
                    for dp in var_data.get("data", [])
                    if dp.get("value", 0) != 0
                ]
        return []

    def get_monthly_generation(self, station_id: str, year: int) -> list[tuple]:
        """
        Get monthly generation for a specific year.
        
        Args:
            station_id: Plant station ID
            year: Year
            
        Returns:
            List of (month, kWh) tuples for months with generation.
        """
        result = self._post("/generic/v0/plant/history/report", {
            "stationID": station_id,
            "reportType": "year",
            "variables": ["generation"],
            "queryDate": {"year": year},
        })
        
        for var_data in result:
            if var_data.get("variable") == "generation":
                return [
                    (dp["index"], dp["value"])
                    for dp in var_data.get("data", [])
                    if dp.get("value", 0) != 0
                ]
        return []

    # ───────────────────────────────────────────
    # Convenience: Get Dashboard Data
    # ───────────────────────────────────────────

    def get_dashboard_data(self) -> dict:
        """
        Get all data needed for the solar dashboard in one call.
        
        Returns:
            Dict with keys: user, plants, devices, today_hourly, 
            current_power_kw, today_kwh, total_kwh, last_update
        """
        self._ensure_token()
        
        # Get plant and device data
        plants = self.get_plants()
        devices = self.get_devices()
        
        # Primary device data
        device = devices[0] if devices else {}
        current_power = device.get("power", 0)
        today_kwh = device.get("generationToday", 0)
        total_kwh = device.get("generationTotal", 0)
        last_update = device.get("dataLatestUploadDate", "")
        status = device.get("status", 0)
        
        # Station ID from plant list
        station_id = plants[0].get("stationID", "") if plants else ""
        
        # Hourly generation for today
        today_hourly = {}
        if station_id:
            try:
                today_hourly = self.get_hourly_generation(station_id)
            except WaareeAPIError as e:
                logger.warning(f"Could not get hourly data: {e}")
        
        return {
            "user": device.get("plantName", ""),
            "station_id": station_id,
            "device_sn": device.get("deviceSN", ""),
            "device_type": device.get("productType", ""),
            "plants": plants,
            "devices": devices,
            "current_power_kw": round(current_power, 3),
            "today_kwh": round(today_kwh, 2),
            "total_kwh": round(total_kwh, 2),
            "status": status,
            "status_text": {0: "offline", 1: "online", 2: "fault"}.get(status, "unknown"),
            "last_update": last_update,
            "today_hourly": today_hourly,
            "fetched_at": datetime.now().isoformat(),
        }


class WaareeAPIError(Exception):
    """Error from Waaree API."""
    pass


class MockWaareeAPIClient:
    """Mock API client for testing, CI, and offline demonstrations."""

    def __init__(self, username: str = "demo_user", password: str = "demo_pass", token_file: str | None = None):
        self.username = username
        self.password = password
        self.token_file = token_file
        self._token = "mock_jwt_token_foxess_5245784"
        self._token_time = datetime.now()

    def login(self) -> str:
        return self._token

    def get_user_info(self) -> dict:
        return {
            "userId": "usr_mock_101",
            "user": "Bhargav Achary",
            "email": "demo@example.com",
            "account": self.username,
        }

    def get_plants(self) -> list[dict]:
        return [{
            "stationID": "mock_plant_berhampur",
            "name": "2.32 kW Rooftop PV (Berhampur)",
            "systemCapacity": 2.32,
            "city": "Berhampur",
            "country": "India",
            "postcode": "760001",
            "timeZone": "Asia/Kolkata",
        }]

    def get_devices(self) -> list[dict]:
        return [{
            "deviceSN": "WAAREE-INV-2026-MOCK",
            "deviceType": "Inverter",
            "status": 1,  # 1 = Online
            "power": 1.485,
            "generationToday": 9.42,
            "generationTotal": 4210.8,
            "dataLatestUploadDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }]

    def get_plant_devices(self, station_id: str) -> list[dict]:
        return self.get_devices()

    def get_hourly_generation(self, station_id: str, target_date: datetime | None = None) -> dict:
        curve = [
            (6, 0.05), (7, 0.22), (8, 0.65), (9, 1.15),
            (10, 1.58), (11, 1.82), (12, 1.95), (13, 1.88),
            (14, 1.62), (15, 1.25), (16, 0.78), (17, 0.32), (18, 0.08)
        ]
        return {
            "generation": curve,
            "feedin": [(h, round(k * 0.4, 2)) for h, k in curve],
            "gridConsumption": [(h, 0.15) for h, _ in curve],
        }

    def get_daily_generation(self, station_id: str, year: int, month: int) -> list[tuple[int, float]]:
        now = datetime.now()
        days_in_month = now.day if (year == now.year and month == now.month) else 28
        results = []
        for d in range(1, max(2, days_in_month + 1)):
            kwh = 9.2 + ((d * 7) % 25) / 10.0
            results.append((d, round(kwh, 2)))
        return results

    def get_monthly_generation(self, station_id: str, year: int) -> list[tuple[int, float]]:
        monthly_yields = [
            (1, 275.4), (2, 288.1), (3, 318.5), (4, 335.2),
            (5, 342.0), (6, 290.4), (7, 245.8), (8, 252.3),
            (9, 280.6), (10, 295.2), (11, 284.5), (12, 270.1)
        ]
        now = datetime.now()
        return [(m, val) for m, val in monthly_yields if m <= now.month]

    def get_dashboard_data(self) -> dict:
        return {
            "user": "Bhargav Achary",
            "device_sn": "WAAREE-INV-2026-MOCK",
            "device_type": "Inverter",
            "status": 1,
            "status_text": "online",
            "current_power_kw": 1.485,
            "today_kwh": 9.42,
            "total_kwh": 4210.8,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "today_hourly": self.get_hourly_generation("mock_plant_berhampur"),
            "fetched_at": datetime.now().isoformat(),
        }


# ── CLI Usage ──

def main():
    """Command-line usage for testing and data extraction."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Waaree Solar API Client")
    parser.add_argument("--username", "-u", help="Portal username")
    parser.add_argument("--password", "-p", help="Portal password")
    parser.add_argument("--credentials", "-c", default="credentials.json",
                       help="Path to credentials.json")
    parser.add_argument("--mock", action="store_true",
                       help="Use mock client with simulated realistic data (no credentials required)")
    parser.add_argument("--output", "-o", help="Output file for dashboard data")
    parser.add_argument("--dashboard", action="store_true",
                       help="Fetch and display dashboard data")
    parser.add_argument("--hourly", action="store_true",
                       help="Show today's hourly generation")
    parser.add_argument("--monthly", action="store_true",
                       help="Show this month's daily generation")
    parser.add_argument("--yearly", action="store_true",
                       help="Show this year's monthly generation")
    parser.add_argument("--json", action="store_true",
                       help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    use_mock = args.mock or os.environ.get("WAAREE_MOCK") == "1"

    if use_mock:
        client = MockWaareeAPIClient(username=args.username or "demo_user")
    else:
        # Load credentials
        username = args.username or os.environ.get("WAAREE_USERNAME")
        password = args.password or os.environ.get("WAAREE_PASSWORD")
        
        if not username or not password:
            env_creds = os.environ.get("WAAREE_CREDENTIALS")
            if env_creds:
                try:
                    c = json.loads(env_creds)
                    username = username or c.get("username")
                    password = password or c.get("password")
                except Exception:
                    pass

        if not username or not password:
            cred_path = args.credentials
            if os.path.exists(cred_path):
                with open(cred_path) as f:
                    creds = json.load(f)
                username = username or creds.get("username")
                password = password or creds.get("password")
        
        if not username or not password:
            print("❌ Error: Waaree credentials not found.")
            print("💡 Provide credentials via:")
            print("   --username and --password flags")
            print("   credentials.json file")
            print("   WAAREE_CREDENTIALS / WAAREE_USERNAME / WAAREE_PASSWORD environment variables")
            print("   Or run with --mock for an offline demonstration:")
            print("   python3 waaree_api_client.py --mock --dashboard")
            return 1
        
        # Create client
        script_dir = os.path.dirname(os.path.abspath(__file__))
        token_file = os.path.join(script_dir, ".waaree_token.json")
        client = WaareeAPIClient(username, password, token_file=token_file)
    
    try:
        client.login()
        
        if args.dashboard or (not args.hourly and not args.monthly and not args.yearly):
            data = client.get_dashboard_data()
            
            if args.json:
                print(json.dumps(data, indent=2, default=str))
            else:
                print(f"Plant: {data['user']}")
                print(f"Device: {data['device_sn']} ({data['device_type']})")
                print(f"Status: {data['status_text']}")
                print(f"Current Power: {data['current_power_kw']} kW")
                print(f"Today: {data['today_kwh']} kWh")
                print(f"Total: {data['total_kwh']} kWh")
                print(f"Last Update: {data['last_update']}")
                
                if data['today_hourly'].get('generation'):
                    print(f"\nToday's Hourly Generation:")
                    for hour, kwh in data['today_hourly']['generation']:
                        bar = "█" * int(kwh * 10)
                        print(f"  {hour:2d}:00  {kwh:5.2f} kWh  {bar}")
            
            # Save to file if requested
            output_file = args.output
            if output_file:
                with open(output_file, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                print(f"\nSaved to {output_file}")
        
        if args.hourly:
            plants = client.get_plants()
            if plants:
                sid = plants[0]["stationID"]
                hourly = client.get_hourly_generation(sid)
                if args.json:
                    print(json.dumps(hourly, indent=2))
                else:
                    for var, points in hourly.items():
                        if points:
                            print(f"\n{var}:")
                            for hour, val in points:
                                print(f"  {hour:2d}:00  {val:.2f} kWh")
        
        if args.monthly:
            plants = client.get_plants()
            if plants:
                sid = plants[0]["stationID"]
                now = datetime.now()
                daily = client.get_daily_generation(sid, now.year, now.month)
                if args.json:
                    print(json.dumps(daily, indent=2))
                else:
                    print(f"Daily Generation ({now.strftime('%B %Y')}):")
                    for day, kwh in daily:
                        bar = "█" * int(kwh)
                        print(f"  Day {day:2d}:  {kwh:6.2f} kWh  {bar}")
        
        if args.yearly:
            plants = client.get_plants()
            if plants:
                sid = plants[0]["stationID"]
                now = datetime.now()
                monthly = client.get_monthly_generation(sid, now.year)
                if args.json:
                    print(json.dumps(monthly, indent=2))
                else:
                    month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    print(f"Monthly Generation ({now.year}):")
                    for month, kwh in monthly:
                        bar = "█" * int(kwh / 5)
                        print(f"  {month_names[month]:3s}:  {kwh:8.2f} kWh  {bar}")
    
    except WaareeAPIError as e:
        print(f"API Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
