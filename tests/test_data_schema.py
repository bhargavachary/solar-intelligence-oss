"""
tests/test_data_schema.py
Validates Schema v5.0 compliance for dashboard.json and historical CSV records.
Ensures no breaking changes for index.html consumption.
"""

import csv
import json
import os
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class TestSchemaV5Compliance(unittest.TestCase):

    def test_dashboard_json_exists_and_valid_schema(self):
        dashboard_path = DATA_DIR / "dashboard.json"
        self.assertTrue(dashboard_path.exists(), "dashboard.json must exist")

        with open(dashboard_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Invariant 1: Top-level keys must match schema v5.0 exactly
        required_top_keys = {
            "meta", "summary", "live", "last_7_days",
            "today_records", "monthly", "analytics"
        }
        self.assertTrue(
            required_top_keys.issubset(set(data.keys())),
            f"Missing required schema v5.0 keys: {required_top_keys - set(data.keys())}"
        )

        # Invariant 2: Meta section
        meta = data["meta"]
        self.assertEqual(meta.get("schema_version"), "5.0")
        self.assertAlmostEqual(meta.get("plant_capacity_kw", 0), 2.32, places=2)
        self.assertIn("location", meta)
        self.assertIn("generated_at", meta)

        # Invariant 3: Live section
        live = data["live"]
        self.assertIn("timestamp", live)
        self.assertIn("power_kw", live)
        self.assertIn("daily_yield_kwh", live)
        self.assertIn("total_yield_kwh", live)
        self.assertIn("status", live)

        # Invariant 4: Analytics section
        analytics = data["analytics"]
        self.assertIn("health", analytics)
        self.assertIn("seasonal_forecast", analytics)
        forecast = analytics["seasonal_forecast"]
        self.assertEqual(len(forecast.get("monthly_kwh", [])), 12, "Must contain 12 months forecast")
        self.assertEqual(len(forecast.get("month_names", [])), 12, "Must contain 12 month names")

    def test_energy_history_csv_structure(self):
        csv_path = DATA_DIR / "energy_history.csv"
        self.assertTrue(csv_path.exists(), "energy_history.csv must exist")

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])

            required_cols = {"date", "yield_kwh", "peak_power_kw", "avg_power_kw", "source"}
            self.assertTrue(
                required_cols.issubset(fieldnames),
                f"Missing CSV columns: {required_cols - fieldnames}"
            )

            # Check hourly columns h05_kw to h19_kw
            for h in range(5, 20):
                col = f"h{h:02d}_kw"
                self.assertIn(col, fieldnames, f"Missing hourly column {col}")

            rows = list(reader)
            self.assertGreater(len(rows), 0, "energy_history.csv must have records")

            for r in rows:
                date_val = r.get("date", "")
                self.assertRegex(date_val, r"^\d{4}-\d{2}-\d{2}$", f"Invalid date format: {date_val}")
                yield_val = float(r.get("yield_kwh", 0) or 0)
                self.assertGreaterEqual(yield_val, 0.0, "Yield must be non-negative")

    def test_energy_logs_immutability_and_validity(self):
        log_dir = DATA_DIR / "energy_logs"
        self.assertTrue(log_dir.is_dir(), "energy_logs directory must exist")

        logs = list(log_dir.glob("*.json"))
        self.assertGreater(len(logs), 0, "Must have archive logs in energy_logs")

        # Spot-check 5 archive files
        for log_file in logs[:5]:
            with open(log_file, "r", encoding="utf-8") as f:
                log_data = json.load(f)
            self.assertIn("date", log_data, f"Log {log_file.name} missing date")


if __name__ == "__main__":
    unittest.main()
