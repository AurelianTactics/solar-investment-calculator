"""Formula-correctness tests for rooftop solar (the active metric).

Worked example sizes a system to a typical CMP home with NO federal credit (the 2026 reality after
25D expired). Run with: python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import rooftop  # noqa: E402
from assumptions import (  # noqa: E402
    DEFAULT_SOURCED,
    capital_assumptions,
    rooftop_assumptions,
)

WORKED = dict(
    capacity_kw=5.5,
    specific_yield_kwh_per_kw=1200.0,
    installed_cost_per_w=2.95,
    federal_itc_pct=0.0,
    credit_value_per_kwh=0.27,
    annual_usage_kwh=6600.0,
    offset_cap_fraction=1.0,
    escalation=0.0,
    degradation=0.0,
)


class TestWorkedExample(unittest.TestCase):
    def test_chain(self):
        r = rooftop.compute(**WORKED)
        self.assertAlmostEqual(r.annual_generation_kwh, 6600.0, places=6)
        self.assertAlmostEqual(r.effective_kwh, 6600.0, places=6)
        self.assertAlmostEqual(r.annual_savings, 1782.0, places=6)
        self.assertAlmostEqual(r.gross_cost, 16225.0, places=6)   # 5.5 x 1000 x 2.95
        self.assertAlmostEqual(r.upfront_cost, 16225.0, places=6)  # no ITC
        # simple payback = 16225 / 1782 = 9.104938...
        self.assertAlmostEqual(r.capital.simple_payback_years, 9.1049382716, places=6)

    def test_five_steps_reported(self):
        r = rooftop.compute(**WORKED)
        self.assertEqual([s.n for s in r.steps], [1, 2, 3, 4, 5])


class TestFederalCreditExpiry(unittest.TestCase):
    def test_default_itc_is_zero_and_sourced(self):
        # The headline 2026 finding: 25D expired, so the shipped default is 0% (sourced).
        a = rooftop_assumptions()
        self.assertEqual(a["federal_itc_pct"].value, 0.0)
        self.assertEqual(a["federal_itc_pct"].tag, DEFAULT_SOURCED)
        self.assertIsNotNone(a["federal_itc_pct"].source)

    def test_restoring_30pct_credit_shortens_payback(self):
        no_itc = rooftop.compute(**WORKED)
        with_itc = rooftop.compute(**{**WORKED, "federal_itc_pct": 0.30})
        self.assertAlmostEqual(with_itc.upfront_cost, 16225.0 * 0.70, places=6)
        self.assertLess(with_itc.capital.simple_payback_years, no_itc.capital.simple_payback_years)


class TestOversizingPenalty(unittest.TestCase):
    def test_generation_beyond_usage_is_not_credited(self):
        # An 11 kW system over-produces vs a 6,600 kWh home: savings stay capped, cost doubles.
        big = rooftop.compute(**{**WORKED, "capacity_kw": 11.0})
        self.assertAlmostEqual(big.annual_generation_kwh, 13200.0, places=6)
        self.assertAlmostEqual(big.effective_kwh, 6600.0, places=6)       # capped at usage
        self.assertAlmostEqual(big.annual_savings, 1782.0, places=6)      # unchanged
        self.assertGreater(big.capital.simple_payback_years, 18.0)        # worse than sized-to-usage


class TestDefaultsFromAssumptions(unittest.TestCase):
    def test_shipped_defaults(self):
        a = {**capital_assumptions(), **rooftop_assumptions()}
        r = rooftop.compute_from_assumptions(a)
        self.assertAlmostEqual(r.annual_savings, 1782.0, places=6)
        self.assertAlmostEqual(r.upfront_cost, 16225.0, places=6)

    def test_high_maine_price_makes_no_itc_payback_still_beat_market(self):
        # ~9-yr payback over 25 yr at 7% -> NPV > 0 even without the federal credit.
        a = {**capital_assumptions(), **rooftop_assumptions()}
        r = rooftop.compute_from_assumptions(a)
        self.assertGreater(r.capital.npv, 0)


class TestGuards(unittest.TestCase):
    def test_rejects_itc_out_of_range(self):
        with self.assertRaises(ValueError):
            rooftop.compute(**{**WORKED, "federal_itc_pct": 1.5})


if __name__ == "__main__":
    unittest.main()
