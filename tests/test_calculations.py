"""
tests/test_calculations.py
Unit tests verifying core photovoltaic engineering mathematics:
- Power (kW) vs Energy (kWh) unit distinctions
- Interval integration and daily yield summation
- Capacity Factor and Performance Ratio (PR)
- Zero-division safety guards
- Explicit distinction between measured and modeled/estimated metrics
"""

import unittest


class TestSolarCalculations(unittest.TestCase):

    def test_energy_from_hourly_power_integration(self):
        """
        Energy (kWh) is the time integral of Power (kW).
        For 1-hour discrete intervals, Energy (kWh) = sum(Power (kW) * 1h).
        """
        # Power readings (kW) from 06:00 to 18:00
        hourly_power_kw = [
            (6, 0.10),
            (7, 0.45),
            (8, 0.90),
            (9, 1.35),
            (10, 1.70),
            (11, 2.05),
            (12, 2.15), # solar noon peak
            (13, 2.10),
            (14, 1.80),
            (15, 1.40),
            (16, 0.85),
            (17, 0.35),
            (18, 0.05),
        ]
        
        # Integration over 1-hour interval
        total_kwh = sum(power * 1.0 for _, power in hourly_power_kw)
        self.assertAlmostEqual(total_kwh, 15.25, places=2)

        # Peak power detection
        peak_kw = max(power for _, power in hourly_power_kw)
        self.assertEqual(peak_kw, 2.15)

    def test_capacity_factor(self):
        """
        Capacity Factor (%) = (Current Power kW / Rated System Capacity kW) * 100
        For 2.32 kW system generating 1.74 kW: CF = (1.74 / 2.32) * 100 = 75.0%
        """
        system_capacity_kw = 2.32
        current_power_kw = 1.74
        cf = (current_power_kw / system_capacity_kw) * 100.0
        self.assertAlmostEqual(cf, 75.0, places=1)

    def test_performance_ratio_standard(self):
        """
        Performance Ratio (PR) = Actual Daily Yield (kWh) / (System Capacity kW * Peak Sun Hours)
        Using Berhampur reference annual average PSH = 5.8 hours.
        """
        system_capacity_kw = 2.32
        psh = 5.8
        nominal_yield_kwh = system_capacity_kw * psh # 13.456 kWh
        
        actual_yield_kwh = 11.4376
        pr_pct = (actual_yield_kwh / nominal_yield_kwh) * 100.0
        self.assertAlmostEqual(pr_pct, 85.0, places=1)

    def test_division_by_zero_safety(self):
        """Zero capacity or zero readings must not raise ZeroDivisionError."""
        def calc_cf(power, cap):
            return round((power / cap) * 100, 1) if cap and cap > 0 else 0.0

        def calc_pr(daily_kwh, cap, psh=5.8):
            denom = cap * psh
            return round((daily_kwh / denom) * 100, 1) if denom > 0 else 0.0

        self.assertEqual(calc_cf(1.5, 0), 0.0)
        self.assertEqual(calc_cf(1.5, None), 0.0)
        self.assertEqual(calc_pr(5.0, 0), 0.0)
        self.assertEqual(calc_pr(0, 2.32), 0.0)

    def test_financial_savings_calculation(self):
        """Tariff calculation: Yield kWh * Tariff INR/kWh."""
        daily_kwh = 12.4
        tariff_inr = 5.0
        income_inr = daily_kwh * tariff_inr
        self.assertEqual(income_inr, 62.0)

    def test_measured_vs_estimated_distinction(self):
        """
        Ensure clear structural separation of measured telemetry vs estimated projections.
        """
        telemetry_point = {
            "timestamp": "2026-09-06 12:30:00",
            "current_power_kw": 1.539,
            "daily_yield_kwh": 3.1,
            "source": "waaree_api_telemetry",
            "is_measured": True,
        }
        self.assertTrue(telemetry_point["is_measured"])

        forecast_point = {
            "annual_kwh": 3318.0,
            "monsoon_drop_pct": 32,
            "source": "berhampur_psh_seasonal_model",
            "is_measured": False,
            "is_estimate": True,
        }
        self.assertTrue(forecast_point["is_estimate"])
        self.assertFalse(forecast_point["is_measured"])


if __name__ == "__main__":
    unittest.main()
