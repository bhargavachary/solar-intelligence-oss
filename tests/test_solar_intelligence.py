#!/usr/bin/env python3
"""
Unit and Integration Tests for Solar Intelligence
===================================================
Covers:
  - Waaree / FoxESS Cloud signature calculation
  - Mock client API contract
  - Schema v5.0 invariants on data/dashboard.json
  - Energy history CSV structure
  - Dashboard builder data transformation
  - Scraper Flask API endpoints
  - Credential resolution precedence
"""

import os
import sys
import json
import csv
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from waaree_api_client import WaareeAPIClient, MockWaareeAPIClient
from scraper_api import app, build_dashboard_json
import update_data


class TestFoxESSSignatureAlgorithm(unittest.TestCase):
    def test_signature_format_and_client_id(self):
        sig = WaareeAPIClient._compute_signature(
            path="/c/v0/user/login",
            token="",
            lang="en",
            timestamp="1700000000000"
        )
        # Signature format must be: 32-hex-md5 + "." + CLIENT_ID (5245784)
        parts = sig.split(".")
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[0]), 32)
        self.assertEqual(parts[1], WaareeAPIClient.CLIENT_ID)
        # Verify deterministic hash
        self.assertEqual(sig, "93688dd15bc9cce4bb68404cc6caccb0.5245784")

    def test_headers_structure(self):
        client = WaareeAPIClient("dummy_user", "dummy_pass")
        headers = client._headers(path="/c/v0/plant/list", token="test_token_123", lang="en")
        required_keys = {"Token", "Lang", "Timestamp", "Signature", "Timezone", "Content-Type", "User-Agent"}
        for k in required_keys:
            self.assertIn(k, headers)
        self.assertEqual(headers["Token"], "test_token_123")
        self.assertEqual(headers["Timezone"], "Asia/Kolkata")
        self.assertTrue(headers["Signature"].endswith("." + WaareeAPIClient.CLIENT_ID))


class TestMockAPIClientContract(unittest.TestCase):
    def setUp(self):
        self.client = MockWaareeAPIClient(username="test_solar_engineer")

    def test_login(self):
        token = self.client.login()
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

    def test_user_info(self):
        info = self.client.get_user_info()
        self.assertEqual(info.get("account"), "test_solar_engineer")
        self.assertIn("user", info)

    def test_plants_contract(self):
        plants = self.client.get_plants()
        self.assertIsInstance(plants, list)
        self.assertGreater(len(plants), 0)
        plant = plants[0]
        self.assertIn("stationID", plant)
        self.assertEqual(plant.get("systemCapacity"), 2.32)

    def test_devices_contract(self):
        devices = self.client.get_devices()
        self.assertIsInstance(devices, list)
        self.assertGreater(len(devices), 0)
        device = devices[0]
        self.assertIn("deviceSN", device)
        self.assertEqual(device.get("status"), 1)
        self.assertGreater(device.get("power", 0), 0)

    def test_hourly_generation(self):
        hourly = self.client.get_hourly_generation("mock_plant_berhampur")
        self.assertIn("generation", hourly)
        points = hourly["generation"]
        self.assertIsInstance(points, list)
        # Bell curve should span morning to evening
        hours = [h for h, _ in points]
        self.assertIn(6, hours)
        self.assertIn(12, hours)
        self.assertIn(18, hours)

    def test_daily_generation(self):
        daily = self.client.get_daily_generation("mock_plant_berhampur", 2026, 11)
        self.assertIsInstance(daily, list)
        self.assertGreater(len(daily), 0)
        for day, kwh in daily:
            self.assertIsInstance(day, int)
            self.assertGreater(kwh, 0)

    def test_monthly_generation(self):
        monthly = self.client.get_monthly_generation("mock_plant_berhampur", 2026)
        self.assertIsInstance(monthly, list)
        for month, kwh in monthly:
            self.assertIn(month, range(1, 13))
            self.assertGreater(kwh, 0)


class TestDashboardSchemaV5Invariants(unittest.TestCase):
    def setUp(self):
        self.dashboard_file = PROJECT_ROOT / "data" / "dashboard.json"
        self.assertTrue(self.dashboard_file.exists(), "data/dashboard.json must exist")
        with open(self.dashboard_file) as f:
            self.data = json.load(f)

    def test_top_level_keys_strict_v5(self):
        expected_keys = {
            "meta", "summary", "live", "last_7_days",
            "today_records", "monthly", "analytics"
        }
        self.assertEqual(set(self.data.keys()), expected_keys)

    def test_meta_section(self):
        meta = self.data["meta"]
        self.assertEqual(meta.get("schema_version"), "5.0")
        self.assertEqual(meta.get("plant_capacity_kw"), 2.32)
        self.assertIn("location", meta)
        self.assertIn("generated_at", meta)

    def test_live_section(self):
        live = self.data["live"]
        required_live_keys = {
            "timestamp", "power_kw", "daily_yield_kwh",
            "monthly_yield_kwh", "total_yield_kwh", "status"
        }
        for k in required_live_keys:
            self.assertIn(k, live)

    def test_analytics_section(self):
        analytics = self.data["analytics"]
        self.assertIn("health", analytics)
        self.assertIn("capacity_factor_pct", analytics)
        self.assertIn("performance_ratio_pct", analytics)


class TestEnergyHistoryCSV(unittest.TestCase):
    def setUp(self):
        self.csv_file = PROJECT_ROOT / "data" / "energy_history.csv"
        self.assertTrue(self.csv_file.exists(), "data/energy_history.csv must exist")

    def test_csv_headers_and_columns(self):
        with open(self.csv_file, newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)
        expected_base = ["date", "yield_kwh", "peak_power_kw", "avg_power_kw"]
        hour_cols = [f"h{h:02d}_kw" for h in range(5, 20)]
        expected_headers = expected_base + hour_cols + ["source"]
        self.assertEqual(headers, expected_headers)

    def test_csv_rows_integrity(self):
        with open(self.csv_file, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertGreaterEqual(len(rows), 100, "Historical data should contain over 100 recorded days")
        # Check first and last rows
        for row in [rows[0], rows[-1]]:
            self.assertRegex(row["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertGreater(float(row["yield_kwh"]), 0)


class TestDashboardJsonBuilder(unittest.TestCase):
    def test_build_with_mock_client(self):
        client = MockWaareeAPIClient()
        payload = build_dashboard_json(client)
        
        # Verify schema compliance
        self.assertEqual(payload["meta"]["schema_version"], "5.0")
        self.assertEqual(payload["meta"]["plant_capacity_kw"], 2.32)
        self.assertEqual(payload["meta"]["location"], "Berhampur, Odisha")
        self.assertEqual(payload["live"]["status"], "Online")
        self.assertGreater(len(payload["today_records"]), 0)
        self.assertGreater(len(payload["last_7_days"]), 0)
        self.assertIn("analytics", payload)


class TestScraperAPIEndpoints(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "waaree-solar-api")

    def test_status_endpoint(self):
        resp = self.client.get("/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("scraper", data)
        self.assertIn("engine", data)

    def test_api_dashboard_endpoint(self):
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("meta", {}).get("schema_version"), "5.0")


class TestCredentialPrecedence(unittest.TestCase):
    def test_env_var_json(self):
        os.environ["WAAREE_CREDENTIALS"] = json.dumps({"username": "env_user", "password": "env_password"})
        try:
            creds = update_data.load_credentials()
            # If credentials.json exists, credentials.json takes precedence over env var
            # but if custom credentials not present, env credentials work
            self.assertIn("username", creds)
            self.assertIn("password", creds)
        finally:
            del os.environ["WAAREE_CREDENTIALS"]

    def test_env_user_password(self):
        os.environ["WAAREE_USERNAME"] = "test_user_solo"
        os.environ["WAAREE_PASSWORD"] = "test_pass_solo"
        try:
            creds = update_data.load_credentials(custom_path="/nonexistent/creds.json")
            if not os.path.exists(os.path.join(update_data.BASE, "credentials.json")):
                self.assertEqual(creds.get("username"), "test_user_solo")
                self.assertEqual(creds.get("password"), "test_pass_solo")
        finally:
            del os.environ["WAAREE_USERNAME"]
            del os.environ["WAAREE_PASSWORD"]


class TestUpdatePipelineDryRun(unittest.TestCase):
    def test_dry_run_pipeline_execution(self):
        client = MockWaareeAPIClient()
        data = update_data.fetch_dashboard(client, dry_run=True)
        self.assertIsNotNone(data)
        self.assertEqual(data["meta"]["schema_version"], "5.0")
        update_data.save_energy_log(data, dry_run=True)
        update_data.build_csv(data, dry_run=True)


if __name__ == "__main__":
    unittest.main()
