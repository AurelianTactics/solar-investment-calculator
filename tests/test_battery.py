"""Formula-correctness tests for home battery storage (the active metric).

The worked example encodes the honest verdict: a battery doesn't pay back on Maine economics.
Since the 2026-07-16 research pull the shipped defaults model a 13-yr expected service life with
3%/yr LFP fade (warranty stays 10 as a separate risk-window concept), and the one real bill lever
is the off-by-default ``tou_enrolled`` mode (three-case math shared with plugin-battery via
``src/tou.py``).

Run with: pytest tests
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

# The original hand-verified flat example (10 yr, no fade), kept as an anchor: the model changes
# must not silently move numbers that were verified by hand.
WORKED_FLAT = dict(
    usable_kwh=13.5,
    installed_cost_per_kwh=998.0,
    federal_itc_pct=0.0,
    annual_bill_savings=0.0,
    resilience_value_per_year=200.0,
    horizon_years=10,
    opportunity_rate=0.07,
    annual_degradation=0.0,
)

# The TOU worked example (CMP rates; 6,600 kWh home, 25% on-peak, 70% coverage — Case 3):
#   arb = 6600 x 0.058120 - (0.3 x 1650) x 0.367366 = 383.592 - 181.84617 = 201.74583
TOU_ARB_CASE3 = 6600 * 0.058120 - 495 * 0.367366


class TestWorkedExample(unittest.TestCase):
    def test_cost_and_value(self):
        r = battery.compute(**WORKED_FLAT)
        self.assertAlmostEqual(r.gross_cost, 13473.0, places=6)   # 13.5 x 998
        self.assertAlmostEqual(r.upfront_cost, 13473.0, places=6)  # no ITC
        self.assertAlmostEqual(r.annual_savings, 200.0, places=6)  # 0 bill + 0 tou + 200 resilience
        # 13473 / 200 = 67.365 yr payback — far beyond any battery horizon
        self.assertAlmostEqual(r.capital.simple_payback_years, 67.365, places=3)

    def test_four_steps_reported(self):
        r = battery.compute(**WORKED_FLAT)
        self.assertEqual([s.n for s in r.steps], [1, 2, 3, 4])


class TestHonestVerdict(unittest.TestCase):
    def test_pure_economics_npv_is_strongly_negative(self):
        # The point of the option: it does NOT pay for itself on the bill.
        r = battery.compute(**WORKED_FLAT)
        self.assertLess(r.capital.npv, 0)

    def test_resilience_is_what_drives_any_value(self):
        with_res = battery.compute(**WORKED_FLAT)
        no_res = battery.compute(**{**WORKED_FLAT, "resilience_value_per_year": 0.0})
        self.assertAlmostEqual(with_res.annual_savings, 200.0, places=6)
        self.assertAlmostEqual(no_res.annual_savings, 0.0, places=6)
        self.assertIsNone(no_res.capital.simple_payback_years)  # zero savings -> never

    def test_longer_horizon_does_not_flip_the_verdict(self):
        # The 13-yr service life (vs 10-yr warranty) only adds more years of ~$0 savings.
        r = battery.compute(**{**WORKED_FLAT, "horizon_years": 13, "annual_degradation": 0.03})
        self.assertLess(r.capital.npv, 0)


class TestDegradation(unittest.TestCase):
    def test_fade_trims_each_later_year(self):
        r = battery.compute(**{**WORKED_FLAT, "horizon_years": 13, "annual_degradation": 0.03})
        self.assertAlmostEqual(r.capital.yearly[0].savings, 200.0, places=6)
        self.assertAlmostEqual(r.capital.yearly[12].savings, 200.0 * 0.97 ** 12, places=6)


class TestTouMode(unittest.TestCase):
    def _enrolled(self, **over):
        return battery.compute(**{
            **WORKED_FLAT,
            "tou_enrolled": True,
            "annual_usage_kwh": 6600.0,
            "on_peak_share": 0.25,
            "residual_coverage": 0.7,
            "enrollment_discount_per_kwh": 0.058120,
            "residual_penalty_per_kwh": 0.367366,
            **over,
        })

    def test_off_by_default(self):
        r = battery.compute(**WORKED_FLAT)
        self.assertEqual(r.tou_arbitrage, 0.0)
        self.assertIsNone(r.tou)

    def test_case3_rescue_matches_master_equation(self):
        r = self._enrolled()
        self.assertEqual(r.tou.case, 3)
        self.assertAlmostEqual(r.tou_arbitrage, TOU_ARB_CASE3, places=6)   # 201.74583
        self.assertAlmostEqual(r.annual_savings, TOU_ARB_CASE3 + 200.0, places=6)

    def test_case2_gravy_is_incremental_only(self):
        # Under the 15.8% line the baseline is TOU-without-battery, so the battery earns only
        # the shifted kWh x penalty — NOT the whole savings-vs-flat (that would double-count).
        r = self._enrolled(on_peak_share=0.10)
        self.assertEqual(r.tou.case, 2)
        self.assertAlmostEqual(r.tou_arbitrage, 0.7 * 660 * 0.367366, places=6)  # 169.723092

    def test_case3_floors_at_zero_when_flat_still_wins(self):
        # Deep on-peak + weak coverage: enrolling would lose vs flat -> the battery earns $0.
        r = self._enrolled(on_peak_share=0.40, residual_coverage=0.2)
        self.assertEqual(r.tou.case, 3)
        self.assertEqual(r.tou_arbitrage, 0.0)
        self.assertLess(r.tou.savings_vs_flat, 0)

    def test_a_powerwall_fails_where_a_cheap_plugin_clears(self):
        # The handoff's verdict: at 25% on-peak the arbitrage-only NPV of a $998/kWh Powerwall
        # is deeply negative even enrolled — the installed battery is the same math with a
        # more expensive device.
        r = self._enrolled(resilience_value_per_year=0.0)
        self.assertLess(r.capital.npv, -9000)


class TestDefaultsFromAssumptions(unittest.TestCase):
    def test_shipped_defaults(self):
        a = {**capital_assumptions(), **battery_assumptions()}
        r = battery.compute_from_assumptions(a)
        self.assertAlmostEqual(r.gross_cost, 13473.0, places=6)
        self.assertEqual(r.tou_arbitrage, 0.0)          # tou_enrolled ships off
        self.assertLess(r.capital.npv, 0)

    def test_horizon_is_service_life_not_warranty(self):
        # battery_assumptions must override capital_assumptions' 25-yr PV horizon with the
        # 13-yr expected service life; the 10-yr warranty is a separate risk-window record.
        a = {**capital_assumptions(), **battery_assumptions()}
        self.assertEqual(a["horizon_years"].value, 13.0)
        self.assertEqual(a["warranty_years"].value, 10.0)
        self.assertEqual(a["annual_degradation"].value, 0.03)

    def test_credit_zero_sourced_and_resilience_unsourced(self):
        a = battery_assumptions()
        self.assertEqual(a["federal_itc_pct"].value, 0.0)
        self.assertEqual(a["federal_itc_pct"].tag, DEFAULT_SOURCED)
        self.assertEqual(a["resilience_value_per_year"].tag, UNSOURCED)
        self.assertTrue(a["resilience_value_per_year"].is_unsourced)
        # ...and it defaults to $0 (2026-07-21): what an outage is worth is the user's to state,
        # so the shipped verdict counts only money the battery demonstrably saves.
        self.assertEqual(a["resilience_value_per_year"].value, 0.0)

    def test_stale_no_arbitrage_claim_is_gone(self):
        # The 2026-07-16 handoff's factual fix: the note must no longer deny that residential
        # TOU arbitrage exists — it exists, conditional and delivery-only, behind tou_enrolled.
        a = battery_assumptions()
        note = (a["annual_bill_savings"].source.note or "") + a["annual_bill_savings"].explain
        self.assertNotIn("No strong residential TOU arbitrage", note)
        self.assertIn("tou_enrolled", note)

    def test_tou_rates_sourced_load_shape_unsourced(self):
        a = battery_assumptions()
        self.assertEqual(a["enrollment_discount_per_kwh"].value, 0.058120)
        self.assertEqual(a["residual_penalty_per_kwh"].value, 0.367366)
        self.assertEqual(a["enrollment_discount_per_kwh"].tag, DEFAULT_SOURCED)
        self.assertEqual(a["residual_penalty_per_kwh"].tag, DEFAULT_SOURCED)
        self.assertTrue(a["on_peak_share"].is_unsourced)
        self.assertTrue(a["residual_coverage"].is_unsourced)
        self.assertEqual(a["tou_enrolled"].value, 0.0)


class TestGuards(unittest.TestCase):
    def test_rejects_itc_out_of_range(self):
        with self.assertRaises(ValueError):
            battery.compute(**{**WORKED_FLAT, "federal_itc_pct": 2.0})


if __name__ == "__main__":
    unittest.main()
