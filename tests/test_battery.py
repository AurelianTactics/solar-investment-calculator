"""Formula-correctness tests for home battery storage (the active metric).

The worked example encodes the honest verdict: a battery doesn't pay back on Maine economics.
Run with: python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import battery  # noqa: E402
from assumptions import (  # noqa: E402
    DEFAULT_SOURCED,
    UNSOURCED,
    battery_assumptions,
    capital_assumptions,
)

WORKED = dict(
    usable_kwh=13.5,
    installed_cost_per_kwh=998.0,
    federal_itc_pct=0.0,
    annual_bill_savings=0.0,
    resilience_value_per_year=200.0,
    horizon_years=10,
    opportunity_rate=0.07,
)


class TestWorkedExample(unittest.TestCase):
    def test_cost_and_value(self):
        r = battery.compute(**WORKED)
        self.assertAlmostEqual(r.gross_cost, 13473.0, places=6)   # 13.5 x 998
        self.assertAlmostEqual(r.upfront_cost, 13473.0, places=6)  # no ITC
        self.assertAlmostEqual(r.annual_savings, 200.0, places=6)  # 0 bill + 200 resilience
        # 13473 / 200 = 67.365 yr payback — far beyond the 10-yr horizon
        self.assertAlmostEqual(r.capital.simple_payback_years, 67.365, places=3)

    def test_three_steps_reported(self):
        r = battery.compute(**WORKED)
        self.assertEqual([s.n for s in r.steps], [1, 2, 3])


class TestHonestVerdict(unittest.TestCase):
    def test_pure_economics_npv_is_strongly_negative(self):
        # The point of the option: it does NOT pay for itself on the bill.
        r = battery.compute(**WORKED)
        self.assertLess(r.capital.npv, 0)

    def test_resilience_is_what_drives_any_value(self):
        with_res = battery.compute(**WORKED)
        no_res = battery.compute(**{**WORKED, "resilience_value_per_year": 0.0})
        self.assertAlmostEqual(with_res.annual_savings, 200.0, places=6)
        self.assertAlmostEqual(no_res.annual_savings, 0.0, places=6)
        self.assertIsNone(no_res.capital.simple_payback_years)  # zero savings -> never


class TestDefaultsFromAssumptions(unittest.TestCase):
    def test_shipped_defaults(self):
        a = {**capital_assumptions(), **battery_assumptions()}
        r = battery.compute_from_assumptions(a)
        self.assertAlmostEqual(r.gross_cost, 13473.0, places=6)
        self.assertLess(r.capital.npv, 0)

    def test_horizon_is_ten_not_twentyfive(self):
        # battery_assumptions must override capital_assumptions' 25-yr PV horizon.
        a = {**capital_assumptions(), **battery_assumptions()}
        self.assertEqual(a["horizon_years"].value, 10.0)

    def test_credit_zero_sourced_and_resilience_unsourced(self):
        a = battery_assumptions()
        self.assertEqual(a["federal_itc_pct"].value, 0.0)
        self.assertEqual(a["federal_itc_pct"].tag, DEFAULT_SOURCED)
        self.assertEqual(a["resilience_value_per_year"].tag, UNSOURCED)
        self.assertTrue(a["resilience_value_per_year"].is_unsourced)


class TestGuards(unittest.TestCase):
    def test_rejects_itc_out_of_range(self):
        with self.assertRaises(ValueError):
            battery.compute(**{**WORKED, "federal_itc_pct": 2.0})


if __name__ == "__main__":
    unittest.main()
