#!/usr/bin/env python3
"""
Unit tests for the SolarmanAPI client.

Run with: python3 test_solarman_api.py
"""

import unittest
import hashlib
from unittest.mock import Mock, patch, MagicMock
from solarman_api import SolarmanAPI, SolarmanAPIError


class TestSolarmanAPI(unittest.TestCase):
    """Test cases for SolarmanAPI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app_id = "test_app_id"
        self.app_secret = "test_app_secret"
        self.email = "test@example.com"
        self.password = "test_password"
        self.api = SolarmanAPI(self.app_id, self.app_secret, self.email, self.password)
    
    def tearDown(self):
        """Clean up after tests."""
        self.api.close()
    
    def test_initialization(self):
        """Test API client initialization."""
        self.assertEqual(self.api.app_id, self.app_id)
        self.assertEqual(self.api.app_secret, self.app_secret)
        self.assertEqual(self.api.email, self.email)
        self.assertEqual(self.api.password, self.password)
        self.assertIsNone(self.api.access_token)
    
    def test_initialization_missing_params(self):
        """Test that initialization fails with missing parameters."""
        with self.assertRaises(ValueError):
            SolarmanAPI("", "secret", "email", "password")
        
        with self.assertRaises(ValueError):
            SolarmanAPI("id", "", "email", "password")
        
        with self.assertRaises(ValueError):
            SolarmanAPI("id", "secret", "", "password")
        
        with self.assertRaises(ValueError):
            SolarmanAPI("id", "secret", "email", "")
    
    def test_password_hashing(self):
        """Test SHA-256 password hashing."""
        test_password = "my_password"
        expected_hash = hashlib.sha256(test_password.encode('utf-8')).hexdigest()
        
        result = self.api._hash_password(test_password)
        
        self.assertEqual(result, expected_hash)
        self.assertEqual(len(result), 64)  # SHA-256 produces 64 hex characters
    
    def test_password_hashing_empty_string(self):
        """Test hashing of empty password."""
        result = self.api._hash_password("")
        expected = hashlib.sha256(b"").hexdigest()
        self.assertEqual(result, expected)
    
    @patch('solarman_api.requests.Session.post')
    def test_login_success(self, mock_post):
        """Test successful login."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'success': True,
            'access_token': 'test_token_12345'
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Call login
        token = self.api.login()
        
        # Verify
        self.assertEqual(token, 'test_token_12345')
        self.assertEqual(self.api.access_token, 'test_token_12345')
        
        # Verify the password was hashed
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        expected_hash = hashlib.sha256(self.password.encode('utf-8')).hexdigest()
        self.assertEqual(payload['password'], expected_hash)
    
    @patch('solarman_api.requests.Session.post')
    def test_login_failure(self, mock_post):
        """Test login with API error."""
        # Mock failed response
        mock_response = Mock()
        mock_response.json.return_value = {
            'success': False,
            'code': 'AUTH_ERROR',
            'msg': 'Invalid credentials'
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Call login and expect error
        with self.assertRaises(SolarmanAPIError) as context:
            self.api.login()
        
        self.assertIn('Invalid credentials', str(context.exception))
    
    @patch('solarman_api.requests.Session.post')
    def test_get_station_list_without_login(self, mock_post):
        """Test getting station list without authentication."""
        with self.assertRaises(SolarmanAPIError) as context:
            self.api.get_station_list()
        
        self.assertIn('No access token', str(context.exception))
    
    @patch('solarman_api.requests.Session.post')
    def test_get_station_list_success(self, mock_post):
        """Test successful station list retrieval."""
        # Set up authentication
        self.api.access_token = "test_token"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'success': True,
            'stationList': [
                {'id': 123, 'name': 'Station 1'},
                {'id': 456, 'name': 'Station 2'}
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Call method
        stations = self.api.get_station_list()
        
        # Verify
        self.assertEqual(len(stations), 2)
        self.assertEqual(stations[0]['id'], 123)
        self.assertEqual(stations[1]['name'], 'Station 2')
    
    @patch('solarman_api.requests.Session.post')
    def test_get_realtime_data_success(self, mock_post):
        """Test successful real-time data retrieval."""
        # Set up authentication
        self.api.access_token = "test_token"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'success': True,
            'data': {'power': 1000, 'energy': 5000}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Call method
        data = self.api.get_realtime_data("123")
        
        # Verify
        self.assertIn('data', data)
        self.assertEqual(data['data']['power'], 1000)
    
    def test_get_realtime_data_empty_station_id(self):
        """Test real-time data with empty station ID."""
        self.api.access_token = "test_token"
        
        with self.assertRaises(ValueError) as context:
            self.api.get_realtime_data("")
        
        self.assertIn('station_id cannot be empty', str(context.exception))
    
    def test_context_manager(self):
        """Test using API as context manager."""
        with SolarmanAPI(self.app_id, self.app_secret, self.email, self.password) as api:
            self.assertIsNotNone(api)
            self.assertIsInstance(api, SolarmanAPI)
    
    @patch('solarman_api.requests.Session.post')
    def test_connection_error(self, mock_post):
        """Test handling of connection errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")
        
        with self.assertRaises(SolarmanAPIError) as context:
            self.api.login()
        
        self.assertIn('Connection error', str(context.exception))
    
    @patch('solarman_api.requests.Session.post')
    def test_timeout_error(self, mock_post):
        """Test handling of timeout errors."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with self.assertRaises(SolarmanAPIError) as context:
            self.api.login()
        
        self.assertIn('timeout', str(context.exception).lower())


def run_tests():
    """Run all tests and display results."""
    print("=" * 70)
    print("SOLARMAN API - Unit Tests")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSolarmanAPI)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 70)
    print("Test Summary:")
    print(f"  Tests Run: {result.testsRun}")
    print(f"  Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
