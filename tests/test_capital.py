"""Formula-correctness tests for the capital-allocation engine (the active metric).

Hand-verified worked examples. Run with: python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capital import compare  # noqa: E402


class TestWorkedExample(unittest.TestCase):
    """upfront=10,000; year-1 savings=1,000; 10 yr; 5% opportunity; no escalation/degradation.

    Hand arithmetic:
      simple_payback         = 10000 / 1000 = 10.0 yr
      lifetime_nominal       = 10 x 1000    = 10000
      annuity PV factor(5%,10) = (1 - 1.05^-10)/0.05 = 7.72173493
      npv  = -10000 + 1000 x 7.72173493 = -2278.26507   (negative: at 5% the cash wins)
      fv_savings = 1000 x (1.05^10 - 1)/0.05 = 12577.89254
      fv_lump    = 10000 x 1.05^10          = 16288.94627
      net_advantage_fv = 12577.89254 - 16288.94627 = -3711.05373
    """

    def setUp(self):
        self.r = compare(
            upfront_cost=10000.0,
            annual_savings_year1=1000.0,
            horizon_years=10,
            opportunity_rate=0.05,
        )

    def test_payback_and_lifetime(self):
        self.assertAlmostEqual(self.r.simple_payback_years, 10.0, places=6)
        self.assertAlmostEqual(self.r.lifetime_savings_nominal, 10000.0, places=6)
        self.assertAlmostEqual(self.r.lifetime_roi, 1.0, places=6)

    def test_npv_matches_hand_value(self):
        self.assertAlmostEqual(self.r.npv, -2278.265070815, places=4)

    def test_net_advantage_fv_matches_hand_value(self):
        self.assertAlmostEqual(self.r.net_advantage_fv, -3711.053732226, places=4)

    def test_npv_and_fv_are_consistent(self):
        # net_advantage_fv is just npv compounded to the horizon.
        self.assertAlmostEqual(
            self.r.net_advantage_fv, self.r.npv * (1.05 ** 10), places=4
        )

    def test_yearly_rows_cover_horizon(self):
        self.assertEqual([row.year for row in self.r.yearly], list(range(1, 11)))
        self.assertAlmostEqual(self.r.yearly[-1].cumulative, 10000.0, places=6)


class TestEscalationAndDegradation(unittest.TestCase):
    def test_year2_savings_apply_both_factors(self):
        r = compare(
            upfront_cost=10000.0,
            annual_savings_year1=1000.0,
            horizon_years=5,
            opportunity_rate=0.05,
            escalation=0.03,
            degradation=0.005,
        )
        # year 1 unscaled; year 2 = 1000 x 1.03 x 0.995 = 1024.85
        self.assertAlmostEqual(r.yearly[0].savings, 1000.0, places=6)
        self.assertAlmostEqual(r.yearly[1].savings, 1024.85, places=2)


class TestVerdictSign(unittest.TestCase):
    def test_fast_payback_beats_the_market(self):
        # A 5-yr simple payback at a 5% opportunity rate should have positive NPV (solar wins).
        r = compare(upfront_cost=10000.0, annual_savings_year1=2000.0, horizon_years=20, opportunity_rate=0.05)
        self.assertGreater(r.npv, 0)
        self.assertGreater(r.net_advantage_fv, 0)


class TestEdgeCases(unittest.TestCase):
    def test_zero_savings_never_pays_back(self):
        r = compare(upfront_cost=10000.0, annual_savings_year1=0.0, horizon_years=10)
        self.assertIsNone(r.simple_payback_years)
        self.assertAlmostEqual(r.npv, -10000.0, places=6)
        self.assertEqual(r.lifetime_roi, 0.0)


class TestGuards(unittest.TestCase):
    def test_rejects_negative_upfront(self):
        with self.assertRaises(ValueError):
            compare(upfront_cost=-1.0, annual_savings_year1=100.0)

    def test_rejects_zero_horizon(self):
        with self.assertRaises(ValueError):
            compare(upfront_cost=100.0, annual_savings_year1=100.0, horizon_years=0)

    def test_rejects_degradation_out_of_range(self):
        with self.assertRaises(ValueError):
            compare(upfront_cost=100.0, annual_savings_year1=100.0, degradation=1.0)


if __name__ == "__main__":
    unittest.main()
