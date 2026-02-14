#!/usr/bin/env python3
"""
Solarman Smart PV (V5) API Client
A production-ready Python script to fetch real-time data from the Solarman Smart PV API.

This module provides a SolarmanAPI class that handles:
- Authentication with the Solarman API
- Fetching station lists
- Retrieving real-time data from solar stations

Author: Solarman API Integration
License: MIT
"""

import hashlib
import json
import logging
import sys
from typing import Dict, List, Optional, Any

import requests


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SolarmanAPIError(Exception):
    """Custom exception for Solarman API errors."""
    pass


class SolarmanAPI:
    """
    Client for interacting with the Solarman Smart PV (V5) API.
    
    This class handles authentication and data retrieval from the Solarman API,
    including token management, station listing, and real-time data fetching.
    
    Attributes:
        base_url (str): Base URL for the Solarman API
        app_id (str): Application ID for API authentication
        app_secret (str): Application secret for API authentication
        email (str): User email for authentication
        password (str): User password (will be hashed before sending)
        access_token (Optional[str]): Current access token (obtained after login)
        session (requests.Session): HTTP session for making requests
    """
    
    BASE_URL = "https://global-api.solarmanpv.com"
    
    def __init__(self, app_id: str, app_secret: str, email: str, password: str):
        """
        Initialize the SolarmanAPI client.
        
        Args:
            app_id: Application ID provided by Solarman
            app_secret: Application secret provided by Solarman
            email: User email for authentication
            password: User password (will be hashed with SHA-256)
        
        Raises:
            ValueError: If any required parameter is empty
        """
        if not all([app_id, app_secret, email, password]):
            raise ValueError("All authentication parameters (app_id, app_secret, email, password) are required")
        
        self.app_id = app_id
        self.app_secret = app_secret
        self.email = email
        self.password = password
        self.access_token: Optional[str] = None
        
        # Create a session for connection pooling and improved performance
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _hash_password(self, password: str) -> str:
        """
        Hash the password using SHA-256.
        
        Args:
            password: Plain text password
            
        Returns:
            Hexadecimal string of the hashed password
        """
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        require_auth: bool = False
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the Solarman API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base URL)
            data: Request payload (for POST requests)
            require_auth: Whether this endpoint requires authentication
            
        Returns:
            Response JSON as a dictionary
            
        Raises:
            SolarmanAPIError: If the request fails or returns an error
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        # Add authorization header if required
        headers = {}
        if require_auth:
            if not self.access_token:
                raise SolarmanAPIError("No access token available. Please login first.")
            headers['Authorization'] = f"Bearer {self.access_token}"
        
        try:
            logger.debug(f"Making {method} request to {url}")
            
            if method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers, timeout=30)
            elif method.upper() == 'GET':
                response = self.session.get(url, params=data, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check HTTP status code
            response.raise_for_status()
            
            # Parse JSON response
            response_data = response.json()
            
            # Check API-level success
            if not response_data.get('success', False):
                error_msg = response_data.get('msg', 'Unknown error')
                error_code = response_data.get('code', 'N/A')
                raise SolarmanAPIError(f"API Error (Code: {error_code}): {error_msg}")
            
            logger.debug(f"Request successful: {endpoint}")
            return response_data
            
        except requests.exceptions.Timeout:
            raise SolarmanAPIError(f"Request timeout for {endpoint}")
        except requests.exceptions.ConnectionError:
            raise SolarmanAPIError(f"Connection error for {endpoint}. Please check your internet connection.")
        except requests.exceptions.HTTPError as e:
            raise SolarmanAPIError(f"HTTP error {e.response.status_code} for {endpoint}: {e}")
        except requests.exceptions.RequestException as e:
            raise SolarmanAPIError(f"Request failed for {endpoint}: {e}")
        except json.JSONDecodeError:
            raise SolarmanAPIError(f"Invalid JSON response from {endpoint}")
    
    def login(self) -> str:
        """
        Authenticate with the Solarman API and obtain an access token.
        
        This method:
        1. Hashes the password using SHA-256
        2. Sends authentication request to /account/v1.0/token
        3. Stores the access token for subsequent requests
        
        Returns:
            The access token string
            
        Raises:
            SolarmanAPIError: If authentication fails
        """
        logger.info(f"Logging in as {self.email}...")
        
        # Hash the password
        hashed_password = self._hash_password(self.password)
        
        # Prepare login payload
        payload = {
            'appId': self.app_id,
            'appSecret': self.app_secret,
            'email': self.email,
            'password': hashed_password
        }
        
        try:
            # Make login request
            response_data = self._make_request('POST', '/account/v1.0/token', data=payload)
            
            # Extract access token
            self.access_token = response_data.get('access_token')
            if not self.access_token:
                raise SolarmanAPIError("No access token in response")
            
            logger.info("Login successful")
            return self.access_token
            
        except SolarmanAPIError as e:
            logger.error(f"Login failed: {e}")
            raise
    
    def get_station_list(self) -> List[Dict[str, Any]]:
        """
        Retrieve the list of solar stations associated with the account.
        
        This method requires authentication (login must be called first).
        
        Returns:
            List of station dictionaries containing station information
            
        Raises:
            SolarmanAPIError: If the request fails or user is not authenticated
        """
        logger.info("Fetching station list...")
        
        try:
            # Make request to get station list
            response_data = self._make_request('POST', '/station/v1.0/list', require_auth=True)
            
            # Extract station list
            station_list = response_data.get('stationList', [])
            
            logger.info(f"Found {len(station_list)} station(s)")
            return station_list
            
        except SolarmanAPIError as e:
            logger.error(f"Failed to fetch station list: {e}")
            raise
    
    def get_realtime_data(self, station_id: str) -> Dict[str, Any]:
        """
        Fetch real-time data from a specific solar station.
        
        This method requires authentication (login must be called first).
        
        Args:
            station_id: The ID of the station to fetch data from
            
        Returns:
            Dictionary containing real-time station data
            
        Raises:
            SolarmanAPIError: If the request fails or user is not authenticated
            ValueError: If station_id is empty
        """
        if not station_id:
            raise ValueError("station_id cannot be empty")
        
        logger.info(f"Fetching real-time data for station {station_id}...")
        
        try:
            # Prepare request payload
            payload = {
                'stationId': station_id
            }
            
            # Make request to get real-time data
            response_data = self._make_request('POST', '/station/v1.0/realTime', data=payload, require_auth=True)
            
            logger.info(f"Successfully fetched real-time data for station {station_id}")
            return response_data
            
        except SolarmanAPIError as e:
            logger.error(f"Failed to fetch real-time data: {e}")
            raise
    
    def fetch_all_stations_data(self) -> List[Dict[str, Any]]:
        """
        Convenience method to fetch real-time data from all stations.
        
        This method:
        1. Gets the list of all stations
        2. Fetches real-time data for each station
        
        Returns:
            List of dictionaries, each containing station info and real-time data
            
        Raises:
            SolarmanAPIError: If any request fails
        """
        logger.info("Fetching data from all stations...")
        
        # Get station list
        stations = self.get_station_list()
        
        all_data = []
        for station in stations:
            station_id = station.get('id')
            if station_id:
                try:
                    realtime_data = self.get_realtime_data(str(station_id))
                    all_data.append({
                        'station_info': station,
                        'realtime_data': realtime_data
                    })
                except SolarmanAPIError as e:
                    logger.warning(f"Failed to fetch data for station {station_id}: {e}")
                    continue
        
        logger.info(f"Successfully fetched data from {len(all_data)} station(s)")
        return all_data
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
        logger.debug("Session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def main():
    """
    Example usage of the SolarmanAPI client.
    
    Replace the placeholders with your actual credentials.
    """
    # Configuration - Replace these with your actual credentials
    APP_ID = "YOUR_APP_ID"  # Replace with your App ID
    APP_SECRET = "YOUR_APP_SECRET"  # Replace with your App Secret
    EMAIL = "your.email@example.com"  # Replace with your email
    PASSWORD = "your_password"  # Replace with your password
    
    # Validate that placeholders have been replaced
    if APP_ID == "YOUR_APP_ID" or APP_SECRET == "YOUR_APP_SECRET":
        logger.error("Please replace APP_ID and APP_SECRET with your actual credentials")
        sys.exit(1)
    
    try:
        # Create API client using context manager
        with SolarmanAPI(APP_ID, APP_SECRET, EMAIL, PASSWORD) as api:
            # Step 1: Login to get access token
            logger.info("=" * 60)
            logger.info("Step 1: Authenticating...")
            logger.info("=" * 60)
            access_token = api.login()
            logger.info(f"Access token obtained: {access_token[:20]}...")
            
            # Step 2: Get list of stations
            logger.info("\n" + "=" * 60)
            logger.info("Step 2: Fetching station list...")
            logger.info("=" * 60)
            stations = api.get_station_list()
            
            if not stations:
                logger.warning("No stations found in your account")
                return
            
            # Display station information
            for idx, station in enumerate(stations, 1):
                logger.info(f"\nStation {idx}:")
                logger.info(f"  ID: {station.get('id')}")
                logger.info(f"  Name: {station.get('name')}")
                logger.info(f"  Location: {station.get('locationLat')}, {station.get('locationLng')}")
            
            # Step 3: Get real-time data for the first station
            if stations:
                logger.info("\n" + "=" * 60)
                logger.info("Step 3: Fetching real-time data...")
                logger.info("=" * 60)
                
                first_station_id = str(stations[0].get('id'))
                realtime_data = api.get_realtime_data(first_station_id)
                
                logger.info(f"\nReal-time data for station {first_station_id}:")
                logger.info(json.dumps(realtime_data, indent=2))
            
            logger.info("\n" + "=" * 60)
            logger.info("Data retrieval completed successfully!")
            logger.info("=" * 60)
            
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except SolarmanAPIError as e:
        logger.error(f"API error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
