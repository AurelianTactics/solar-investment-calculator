"""Formula-correctness tests for balcony / plug-in solar (the active metric).

The worked example reproduces the Office of the Public Advocate's sourced anchor: a 1.2 kW Maine
plug-in system saves ~$388/yr. Run with: python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import balcony  # noqa: E402
from assumptions import (  # noqa: E402
    UNSOURCED,
    balcony_assumptions,
    capital_assumptions,
)

# Hand-verified worked example (defaults; escalation/degradation off for a clean payback check).
WORKED = dict(
    capacity_kw=1.2,
    specific_yield_kwh_per_kw=1200.0,
    self_consumption_fraction=1.0,
    volumetric_rate_per_kwh=0.27,
    kit_cost=1200.0,
    electrician_cost=300.0,
    escalation=0.0,
    degradation=0.0,
)


class TestWorkedExample(unittest.TestCase):
    def test_generation_savings_and_capital(self):
        r = balcony.compute(**WORKED)
        self.assertAlmostEqual(r.annual_generation_kwh, 1440.0, places=6)
        self.assertAlmostEqual(r.self_consumed_kwh, 1440.0, places=6)
        self.assertAlmostEqual(r.annual_savings, 388.8, places=6)
        self.assertAlmostEqual(r.upfront_cost, 1500.0, places=6)
        # simple payback = 1500 / 388.8 = 3.85802...
        self.assertAlmostEqual(r.capital.simple_payback_years, 3.8580246913, places=6)

    def test_reconciles_with_opa_anchor(self):
        # The sourced cross-check: OPA says ~$388/yr for a 1.2 kW system.
        r = balcony.compute(**WORKED)
        self.assertLess(abs(r.annual_savings - 388.0), 1.5)

    def test_four_steps_reported(self):
        r = balcony.compute(**WORKED)
        self.assertEqual([s.n for s in r.steps], [1, 2, 3, 4])


class TestSelfConsumptionIsLoadBearing(unittest.TestCase):
    def test_exported_surplus_earns_nothing(self):
        # Halving self-consumption halves savings — exported kWh are uncompensated (not NEB).
        full = balcony.compute(**WORKED)
        half = balcony.compute(**{**WORKED, "self_consumption_fraction": 0.5})
        self.assertAlmostEqual(half.annual_savings, full.annual_savings / 2, places=6)
        self.assertAlmostEqual(half.self_consumed_kwh, 720.0, places=6)


class TestDefaultsFromAssumptions(unittest.TestCase):
    def test_shipped_defaults_reproduce_the_anchor(self):
        a = {**capital_assumptions(), **balcony_assumptions()}
        r = balcony.compute_from_assumptions(a)
        self.assertAlmostEqual(r.annual_savings, 388.8, places=6)

    def test_electrician_cost_is_a_real_unsourced_default(self):
        # Demonstrates the transparency mechanic with a genuinely unsourced shipped default.
        a = balcony_assumptions()
        self.assertEqual(a["electrician_cost"].tag, UNSOURCED)
        self.assertTrue(a["electrician_cost"].is_unsourced)
        self.assertIsNone(a["electrician_cost"].source)


class TestCapitalVerdict(unittest.TestCase):
    def test_fast_payback_beats_the_market(self):
        # ~3.9-yr payback over 25 yr at a 7% opportunity rate -> solar wins (NPV > 0).
        a = {**capital_assumptions(), **balcony_assumptions()}
        r = balcony.compute_from_assumptions(a)
        self.assertGreater(r.capital.npv, 0)


class TestGuards(unittest.TestCase):
    def test_rejects_self_consumption_out_of_range(self):
        with self.assertRaises(ValueError):
            balcony.compute(**{**WORKED, "self_consumption_fraction": 1.5})


if __name__ == "__main__":
    unittest.main()
