"""Formula-correctness tests — the active metric (STRATEGY.md, R10).

A change that breaks the hand-verified worked example is a regression. Run with:
    python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from assumptions import (  # noqa: E402
    DEFAULT_SOURCED,
    UNSOURCED,
    USER_PROVIDED,
    default_assumptions,
)
from solar_calc import compute  # noqa: E402

# Canonical worked example from the POC plan (illustrative inputs; the test asserts the
# arithmetic, not the realism of the inputs).
WORKED = dict(
    monthly_bill=150.0,
    price_per_kwh=0.25,
    bill_offset_fraction=0.60,
    subscription_discount_pct=0.12,
    allocation_pct=1.00,
)


class TestWorkedExample(unittest.TestCase):
    def test_every_output_matches_hand_verification(self):
        r = compute(**WORKED)
        self.assertAlmostEqual(r.annual_spend, 1800.0, places=6)
        self.assertAlmostEqual(r.monthly_usage_kwh, 600.0, places=6)
        self.assertAlmostEqual(r.annual_usage_kwh, 7200.0, places=6)
        self.assertAlmostEqual(r.credit_value_per_kwh, 0.15, places=6)
        self.assertAlmostEqual(r.credits_generated, 1080.0, places=6)
        self.assertAlmostEqual(r.annual_savings, 129.60, places=6)
        self.assertAlmostEqual(r.monthly_savings, 10.80, places=6)
        self.assertAlmostEqual(r.pct_off, 0.072, places=6)
        self.assertEqual(r.capital, 0.0)

    def test_four_steps_are_reported(self):
        r = compute(**WORKED)
        self.assertEqual([s.n for s in r.steps], [1, 2, 3, 4])
        # Step 2 (usage) is the only one that depends on price_per_kwh in a way that shows;
        # the dollar steps must trace their assumption dependencies for the chip display (R9).
        self.assertIn("subscription_discount_pct", r.steps[3].uses)
        self.assertIn("bill_offset_fraction", r.steps[2].uses)


class TestCancellationProperty(unittest.TestCase):
    """In the bill-first flow, price_per_kwh cancels out of the dollar result (POC plan)."""

    def test_changing_price_leaves_dollars_unchanged_but_moves_usage(self):
        base = compute(**WORKED)
        bumped = compute(**{**WORKED, "price_per_kwh": 0.50})
        # Dollars identical...
        self.assertAlmostEqual(base.annual_savings, bumped.annual_savings, places=6)
        self.assertAlmostEqual(base.monthly_savings, bumped.monthly_savings, places=6)
        self.assertAlmostEqual(base.pct_off, bumped.pct_off, places=6)
        # ...usage halves.
        self.assertAlmostEqual(bumped.annual_usage_kwh, base.annual_usage_kwh / 2, places=6)

    def test_pct_off_identity(self):
        # pct_off == offset x discount x allocation (an exact model identity in the bill-first flow)
        r = compute(**WORKED)
        expected = (
            WORKED["bill_offset_fraction"]
            * WORKED["subscription_discount_pct"]
            * WORKED["allocation_pct"]
        )
        self.assertAlmostEqual(r.pct_off, expected, places=6)


class TestUsageFirstFlow(unittest.TestCase):
    def test_provided_usage_is_used_and_price_then_matters(self):
        # When usage is given directly, price_per_kwh becomes load-bearing for the dollar result.
        a = compute(**{**WORKED, "annual_usage_kwh": 7200.0})
        b = compute(**{**WORKED, "annual_usage_kwh": 7200.0, "price_per_kwh": 0.50})
        self.assertAlmostEqual(a.annual_usage_kwh, 7200.0, places=6)
        self.assertGreater(b.annual_savings, a.annual_savings)  # higher price -> higher credit value


class TestTransparencyMechanic(unittest.TestCase):
    def test_unsourced_default_is_tagged_pending_research(self):  # AE3
        a = default_assumptions()
        self.assertEqual(a["bill_offset_fraction"].tag, UNSOURCED)
        self.assertTrue(a["bill_offset_fraction"].is_unsourced)
        self.assertIsNone(a["bill_offset_fraction"].source)

    def test_allocation_is_a_stated_default(self):
        a = default_assumptions()
        self.assertEqual(a["allocation_pct"].tag, DEFAULT_SOURCED)
        self.assertIsNotNone(a["allocation_pct"].source)

    def test_editing_a_default_retags_user_provided_and_clears_source(self):  # AE2, R7
        a = default_assumptions()
        edited = a["allocation_pct"].with_user_value(0.8)
        self.assertEqual(edited.value, 0.8)
        self.assertEqual(edited.tag, USER_PROVIDED)
        self.assertIsNone(edited.source)


class TestGuards(unittest.TestCase):
    def test_rejects_nonpositive_price(self):
        with self.assertRaises(ValueError):
            compute(**{**WORKED, "price_per_kwh": 0.0})

    def test_rejects_negative_bill(self):
        with self.assertRaises(ValueError):
            compute(**{**WORKED, "monthly_bill": -1.0})


if __name__ == "__main__":
    unittest.main()
