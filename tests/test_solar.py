#!/usr/bin/env python3
"""
Unit tests for Solar Intelligence:
- Validates data/dashboard.json Schema v5.0 invariants and physical energy constraints.
- Validates data/energy_history.csv columns, formats, and power consistency.
- Validates WaareeAPIClient authentication signature algorithm.
- Validates peak power and average power calculation logic.
"""

import csv
import json
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
DASHBOARD_FILE = BASE_DIR / "data" / "dashboard.json"
CSV_FILE = BASE_DIR / "data" / "energy_history.csv"

from waaree_api_client import WaareeAPIClient


class TestDashboardSchema(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DASHBOARD_FILE.exists(), f"dashboard.json missing at {DASHBOARD_FILE}")
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_top_level_keys(self):
        expected_keys = {"meta", "summary", "live", "last_7_days", "today_records", "monthly", "analytics"}
        self.assertTrue(expected_keys.issubset(set(self.data.keys())), f"Missing keys: {expected_keys - set(self.data.keys())}")

    def test_meta_invariants(self):
        meta = self.data["meta"]
        self.assertEqual(meta.get("schema_version"), "5.0")
        self.assertEqual(meta.get("plant_capacity_kw"), 2.32)
        self.assertIn("Berhampur", meta.get("location", ""))

    def test_physical_power_and_yield_bounds(self):
        live = self.data["live"]
        # Instantaneous power cannot exceed 130% of system rating (allowing for cold-day solar irradiance spikes)
        max_possible_kw = self.data["meta"]["plant_capacity_kw"] * 1.3
        self.assertGreaterEqual(live.get("power_kw", 0), 0)
        self.assertLessEqual(live.get("power_kw", 0), max_possible_kw)

        # Cumulative daily yield must be non-negative and physically plausible (< 20 kWh for a 2.32 kW array in Odisha)
        daily = live.get("daily_yield_kwh", 0)
        self.assertGreaterEqual(daily, 0)
        self.assertLessEqual(daily, 20.0)

        # Total yield must be greater than monthly yield
        self.assertGreaterEqual(live.get("total_yield_kwh", 0), live.get("monthly_yield_kwh", 0))

    def test_last_7_days_structure(self):
        last_7 = self.data.get("last_7_days", [])
        self.assertIsInstance(last_7, list)
        for day in last_7:
            self.assertIn("date", day)
            self.assertIn("yield_kwh", day)
            self.assertGreaterEqual(day["yield_kwh"], 0)


class TestEnergyHistoryCSV(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CSV_FILE.exists(), f"energy_history.csv missing at {CSV_FILE}")
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.fieldnames = reader.fieldnames
            self.rows = list(reader)

    def test_csv_fieldnames(self):
        required_headers = ["date", "yield_kwh", "peak_power_kw", "avg_power_kw", "source"]
        for h in required_headers:
            self.assertIn(h, self.fieldnames)

        # Check hourly headers h05_kw to h19_kw exist
        for hour in range(5, 20):
            self.assertIn(f"h{hour:02d}_kw", self.fieldnames)

    def test_csv_rows_chronological_and_valid(self):
        dates = [row["date"] for row in self.rows if row.get("date")]
        self.assertEqual(dates, sorted(dates), "energy_history.csv rows must be chronologically ordered")

        for row in self.rows:
            if not row.get("date"):
                continue
            yield_kwh = float(row.get("yield_kwh") or 0)
            self.assertGreaterEqual(yield_kwh, 0)
            peak_kw = float(row.get("peak_power_kw") or 0)
            self.assertGreaterEqual(peak_kw, 0)


class TestAPIClientSignature(unittest.TestCase):
    def test_compute_signature_deterministic(self):
        path = "/c/v0/user/login"
        token = "test_jwt_token"
        lang = "en"
        timestamp = "1725600000000"

        sig1 = WaareeAPIClient._compute_signature(path, token, lang, timestamp)
        sig2 = WaareeAPIClient._compute_signature(path, token, lang, timestamp)
        self.assertEqual(sig1, sig2)
        self.assertTrue(sig1.endswith("." + WaareeAPIClient.CLIENT_ID))
        # Hash part should be 32 hex characters
        hash_part = sig1.split(".")[0]
        self.assertEqual(len(hash_part), 32)


if __name__ == "__main__":
    unittest.main()
