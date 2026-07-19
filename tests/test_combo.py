"""Formula-correctness tests for the combined options (battery+rooftop, battery+balcony).

The combos are stream-wise additive: each component keeps its own escalation/degradation/horizon
stream (battery: 13-yr service life, 3%/yr fade; PV: 25 yr); per-year cashflows are summed over
the longer horizon, and NPV/payback/verdict derive from the summed stream. Hand-verified worked
example (all escalation/degradation zeroed):

  rooftop defaults: year-1 savings 6600 kWh x $0.27 = $1,782;  upfront 5.5 kW x $2.95/W = $16,225
  battery defaults: year-1 value  $0 + $200 resilience = $200; upfront 13.5 kWh x $998 = $13,473
  combined:         upfront $29,698; year-1 $1,982; simple payback 29698/1982 = 14.9839 yr
                    (differs from rooftop's 9.1049 and battery's 67.365 — combined-stream payback)

Run with: pytest tests
"""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import balcony  # noqa: E402
import battery  # noqa: E402
import battery_balcony  # noqa: E402
import battery_rooftop  # noqa: E402
import capital  # noqa: E402
import rooftop  # noqa: E402
from assumptions import (  # noqa: E402
    UNSOURCED,
    USER_PROVIDED,
    battery_balcony_assumptions,
    battery_rooftop_assumptions,
)

CLI = os.path.join(os.path.dirname(__file__), "..", "src", "cli.py")


def flat_assumptions(builder):
    """Builder defaults with escalation/degradation zeroed (the hand-verified example)."""
    a = builder()
    a["electricity_escalation"] = a["electricity_escalation"].with_user_value(0.0)
    a["panel_degradation"] = a["panel_degradation"].with_user_value(0.0)
    a["battery_annual_degradation"] = a["battery_annual_degradation"].with_user_value(0.0)
    return a


# --------------------------------------------------------------------- battery+rooftop worked example

class TestBatteryRooftopWorkedExample:
    def setup_method(self):
        self.r = battery_rooftop.compute_from_assumptions(flat_assumptions(battery_rooftop_assumptions))

    def test_upfront_is_sum_of_component_upfronts(self):
        assert self.r.upfront_cost == pytest.approx(29698.0)          # 16225 + 13473
        assert self.r.pv.upfront_cost == pytest.approx(16225.0)
        assert self.r.battery.upfront_cost == pytest.approx(13473.0)

    def test_year1_savings_is_sum_of_component_year1(self):
        assert self.r.annual_savings == pytest.approx(1982.0)         # 1782 + 200 + 0 interaction

    def test_npv_is_additive_under_identical_rates(self):
        pv = rooftop.compute(
            capacity_kw=5.5, specific_yield_kwh_per_kw=1200.0, installed_cost_per_w=2.95,
            federal_itc_pct=0.0, credit_value_per_kwh=0.27, annual_usage_kwh=6600.0,
            offset_cap_fraction=1.0, horizon_years=25, opportunity_rate=0.07,
            escalation=0.0, degradation=0.0,
        )
        bt = battery.compute(
            usable_kwh=13.5, installed_cost_per_kwh=998.0, federal_itc_pct=0.0,
            annual_bill_savings=0.0, resilience_value_per_year=200.0,
            horizon_years=13, opportunity_rate=0.07, annual_degradation=0.0,
        )
        assert self.r.capital.npv == pytest.approx(pv.capital.npv + bt.capital.npv)

    def test_payback_comes_from_the_combined_stream(self):
        combined = self.r.capital.simple_payback_years
        assert combined == pytest.approx(29698.0 / 1982.0)            # 14.9839...
        # ...and differs from BOTH component paybacks (adding paybacks would be wrong).
        assert combined != pytest.approx(16225.0 / 1782.0)            # rooftop alone: 9.1049
        assert combined != pytest.approx(13473.0 / 200.0)             # battery alone: 67.365

    def test_step_chain_shows_the_combination(self):
        steps = self.r.steps
        assert [s.n for s in steps] == list(range(1, len(steps) + 1))
        used = set().union(*(s.uses for s in steps))
        # component inputs and combo-only keys all appear in the chain
        assert "capacity_kw" in used
        assert "battery_usable_kwh" in used
        assert "battery_pv_interaction_value_per_year" in used
        assert "battery_horizon_years" in used


# --------------------------------------------------------------------- horizon honesty

class TestHorizonHonesty:
    def test_battery_contributes_nothing_after_year_13(self):
        # With the shipped defaults (escalation, PV degradation, and 3%/yr battery fade all
        # live), year-14 combined cashflow must equal the PV-only cashflow: the battery stream
        # ended at its 13-yr service life.
        a = battery_rooftop_assumptions()
        combo_r = battery_rooftop.compute_from_assumptions(a)
        pv = rooftop.compute_from_assumptions(a)
        assert combo_r.capital.horizon_years == 25
        assert combo_r.capital.yearly[13].savings == pytest.approx(pv.capital.yearly[13].savings)
        # ...while year 13 still includes the battery's faded value: 200 x 0.97^12.
        assert combo_r.capital.yearly[12].savings == pytest.approx(
            pv.capital.yearly[12].savings + 200.0 * 0.97 ** 12)

    def test_battery_balcony_same_rule(self):
        a = battery_balcony_assumptions()
        combo_r = battery_balcony.compute_from_assumptions(a)
        pv = balcony.compute_from_assumptions(a)
        assert combo_r.capital.yearly[13].savings == pytest.approx(pv.capital.yearly[13].savings)


# --------------------------------------------------------------------- battery+balcony worked example

class TestBatteryBalconyWorkedExample:
    def test_totals(self):
        r = battery_balcony.compute_from_assumptions(flat_assumptions(battery_balcony_assumptions))
        assert r.upfront_cost == pytest.approx(14973.0)               # 1500 + 13473
        assert r.annual_savings == pytest.approx(588.8)               # 388.8 + 200
        assert r.capital.simple_payback_years == pytest.approx(14973.0 / 588.8)


# --------------------------------------------------------------------- interaction assumption

class TestInteractionAssumption:
    def test_default_zero_keeps_combo_exactly_additive(self):
        a = flat_assumptions(battery_rooftop_assumptions)
        assert a["battery_pv_interaction_value_per_year"].value == 0.0
        r = battery_rooftop.compute_from_assumptions(a)
        assert r.annual_savings == pytest.approx(1982.0)

    def test_nonzero_shifts_annual_savings_by_that_amount(self):
        a = flat_assumptions(battery_rooftop_assumptions)
        a["battery_pv_interaction_value_per_year"] = (
            a["battery_pv_interaction_value_per_year"].with_user_value(150.0)
        )
        r = battery_rooftop.compute_from_assumptions(a)
        assert r.annual_savings == pytest.approx(1982.0 + 150.0)
        # the uplift rides the battery stream: present in year 13, gone by year 14
        assert r.capital.yearly[12].savings == pytest.approx(1782.0 + 200.0 + 150.0)
        assert r.capital.yearly[13].savings == pytest.approx(1782.0)

    def test_tagged_unsourced_with_no_url(self):
        for builder in (battery_rooftop_assumptions, battery_balcony_assumptions):
            asm = builder()["battery_pv_interaction_value_per_year"]
            assert asm.tag == UNSOURCED
            assert asm.is_unsourced
            assert asm.source is None or asm.source.url is None


# --------------------------------------------------------------------- builder shape

class TestBuilders:
    def test_two_horizons_coexist(self):
        a = battery_rooftop_assumptions()
        assert a["horizon_years"].value == 25.0            # the PV stream's horizon
        assert a["battery_horizon_years"].value == 13.0    # the battery stream's service life

    def test_itc_collision_resolved_per_component(self):
        a = battery_rooftop_assumptions()
        assert "federal_itc_pct" in a                      # rooftop's
        assert "battery_federal_itc_pct" in a              # battery's, namespaced

    def test_round_trip_matches_explicit_compute(self):
        r = battery_rooftop.compute_from_assumptions(battery_rooftop_assumptions())
        pv = rooftop.compute_from_assumptions(battery_rooftop_assumptions())
        assert r.pv.annual_savings == pytest.approx(pv.annual_savings)
        assert r.upfront_cost == pytest.approx(pv.upfront_cost + 13473.0)


# --------------------------------------------------------------------- guards

class TestGuards:
    def test_negative_capacity_raises(self):
        a = battery_rooftop_assumptions()
        a["capacity_kw"] = a["capacity_kw"].with_user_value(-1.0)
        with pytest.raises(ValueError):
            battery_rooftop.compute_from_assumptions(a)

    def test_zero_battery_horizon_raises(self):
        a = battery_rooftop_assumptions()
        a["battery_horizon_years"] = a["battery_horizon_years"].with_user_value(0.0)
        with pytest.raises(ValueError):
            battery_rooftop.compute_from_assumptions(a)

    def test_combine_rejects_empty_and_mismatched_rates(self):
        with pytest.raises(ValueError):
            capital.combine([])
        a = capital.compare(100.0, 10.0, horizon_years=5, opportunity_rate=0.07)
        b = capital.compare(100.0, 10.0, horizon_years=5, opportunity_rate=0.05)
        with pytest.raises(ValueError):
            capital.combine([a, b])


# --------------------------------------------------------------------- CLI parity

def run_cli(*args):
    res = subprocess.run(
        [sys.executable, CLI, *args], capture_output=True, text=True, timeout=60
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


class TestCli:
    def test_battery_rooftop_json_schema(self):
        payload = json.loads(run_cli("--option", "battery+rooftop", "--json"))
        assert payload["option"] == "battery+rooftop"
        assert payload["result"]["upfront_cost"] == pytest.approx(29698.0)
        assert payload["steps"], "combo steps missing from JSON"
        assert "battery_usable_kwh" in payload["assumptions"]
        assert "battery_pv_interaction_value_per_year" in payload["assumptions"]

    def test_battery_balcony_text_renders(self):
        out = run_cli("--option", "battery+balcony")
        assert "Battery + Balcony" in out
        assert "STEPS" in out

    def test_set_retags_user_provided(self):
        payload = json.loads(run_cli(
            "--option", "battery+rooftop", "--json",
            "--set", "battery_resilience_value_per_year=400",
        ))
        asm = payload["assumptions"]["battery_resilience_value_per_year"]
        assert asm["tag"] == USER_PROVIDED
        assert asm["value"] == 400.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
