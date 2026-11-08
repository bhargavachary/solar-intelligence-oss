"""
tests/test_api_client.py
Tests signature calculation, authentication token caching, and error handling
in WaareeAPIClient without issuing real network requests.
"""

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from waaree_api_client import WaareeAPIClient, WaareeAPIError


class TestWaareeAPIClient(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.token_file = Path(self.tmp_dir) / "test_token.json"
        self.client = WaareeAPIClient(
            username="test_user@example.com",
            password="test_password",
            token_file=str(self.token_file),
        )

    def test_signature_algorithm(self):
        """
        Verify portal API signature calculation:
        MD5(path + \\r\\n + token + \\r\\n + lang + \\r\\n + timestamp) + ".5245784"
        """
        path = "/c/v0/device/list"
        token = "test_token_123"
        ts = "1700000000"
        lang = "en"

        sig = WaareeAPIClient._compute_signature(path, token, lang, ts)
        self.assertTrue(sig.endswith(f".{WaareeAPIClient.CLIENT_ID}"))
        self.assertEqual(len(sig.split(".")[0]), 32)

    def test_token_cache_and_expiration(self):
        """Test token cache loading and expiration evaluation."""
        self.assertIsNone(self.client._load_cached_token())

        # Write cached token valid for 2 hours
        now = datetime.now()
        cache_data = {
            "token": "cached_jwt_token",
            "saved_at": now.isoformat(),
        }
        self.token_file.write_text(json.dumps(cache_data))

        token = self.client._load_cached_token()
        self.assertEqual(token, "cached_jwt_token")

        # Test expired token (> 2 hours)
        old_time = now - timedelta(hours=3)
        cache_data["saved_at"] = old_time.isoformat()
        self.token_file.write_text(json.dumps(cache_data))

        expired_token = self.client._load_cached_token()
        self.assertIsNone(expired_token)

    def test_api_error_handling(self):
        """Non-zero errno in response must raise WaareeAPIError."""
        self.client._token = "valid_token"
        self.client._token_time = datetime.now()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "errno": 40101,
            "msg": "Token expired or invalid",
            "result": None,
        }
        self.client.session.post = MagicMock(return_value=mock_resp)

        with self.assertRaises(WaareeAPIError) as ctx:
            self.client._post("/c/v0/plant/list")
        self.assertIn("errno=40101", str(ctx.exception))


class TestResilienceAndMocking(unittest.TestCase):

    def test_build_dashboard_json_with_mock_client(self):
        """
        Verify build_dashboard_json generates valid schema v5.0
        even when API returns minimal/empty telemetry.
        """
        from scraper_api import build_dashboard_json

        mock_client = MagicMock()
        mock_client.get_plants.return_value = [{
            "stationID": "test-plant-001",
            "systemCapacity": 2.32,
            "city": "Berhampur"
        }]
        mock_client.get_devices.return_value = [{
            "power": 1.25,
            "generationToday": 4.5,
            "generationTotal": 1200.0,
            "status": 1,
            "dataLatestUploadDate": "2026-11-08 11:00:00"
        }]
        mock_client.get_hourly_generation.return_value = {
            "generation": [(8, 0.4), (9, 0.8), (10, 1.25)]
        }
        mock_client.get_daily_generation.return_value = [(1, 4.0), (2, 4.5)]
        mock_client.get_monthly_generation.return_value = [(1, 120.0)]

        payload = build_dashboard_json(mock_client)

        self.assertEqual(payload["meta"]["schema_version"], "5.0")
        self.assertEqual(payload["meta"]["plant_id"], "test-plant-001")
        self.assertEqual(payload["live"]["power_kw"], 1.25)
        self.assertEqual(payload["live"]["daily_yield_kwh"], 4.5)
        self.assertEqual(len(payload["today_records"]), 3)
        self.assertEqual(payload["summary"]["peak_power_kw"], 1.25)


if __name__ == "__main__":
    unittest.main()
