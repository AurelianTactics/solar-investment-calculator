"""Formula-correctness tests for the plug-in / DIY DER battery option (the active metric).

Hand-verified worked example (shipped defaults; CMP Rate TOU rates):
  6,600 kWh home, 25% on-peak, 70% coverage -> Case 3 (rescue)
  on-peak 1,650 kWh; shifted 1,155; residual 495
  arb   = 6600 x 0.058120 - 495 x 0.367366 = 383.592 - 181.84617 = 201.74583 $/yr
  size  = 1155 / 250 = 4.62 kWh; gross = 4.62 x $600 = $2,772 (itc 0)
  annual = 201.74583 + 200 resilience = 401.74583; payback = 2772 / 401.74583 = 6.90 yr
  break-even (case 3) = 201.74583 x 10 / 4.62 = 436.68 $/kWh

The Case-3 depth table from plugin-battery-answers.md (10,000 kWh home, coverage 1.0) is
reproduced exactly: break-even $908.13 at 16% on-peak -> $726.50 at 20% -> $581.20 at 25%
-> $363.25 at 40%.

Run with: pytest tests
"""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import plugin_battery  # noqa: E402
from assumptions import (  # noqa: E402
    DEFAULT_SOURCED,
    UNSOURCED,
    capital_assumptions,
    plugin_battery_assumptions,
)

CLI = os.path.join(os.path.dirname(__file__), "..", "src", "cli.py")

DEFAULTS = dict(
    annual_usage_kwh=6600.0,
    on_peak_share=0.25,
    residual_coverage=0.7,
    installed_cost_per_kwh=600.0,
    cycles_per_year=250.0,
    enrollment_discount_per_kwh=0.058120,
    residual_penalty_per_kwh=0.367366,
    value_per_usable_kwh_yr=90.13,
    federal_itc_pct=0.0,
    resilience_value_per_year=200.0,
    horizon_years=10,
    opportunity_rate=0.07,
)

ARB_CASE3 = 6600 * 0.058120 - 495 * 0.367366   # 201.74583


class TestWorkedExample:
    def setup_method(self):
        self.r = plugin_battery.compute(**DEFAULTS)

    def test_case_and_load_split(self):
        assert self.r.case == 3
        assert self.r.tou.on_peak_kwh == pytest.approx(1650.0)
        assert self.r.tou.shifted_kwh == pytest.approx(1155.0)
        assert self.r.tou.residual_kwh == pytest.approx(495.0)

    def test_battery_sized_to_the_shifted_load(self):
        assert self.r.usable_kwh_needed == pytest.approx(4.62)
        assert self.r.gross_cost == pytest.approx(2772.0)
        assert self.r.upfront_cost == pytest.approx(2772.0)   # itc 0

    def test_arbitrage_and_annual_value(self):
        assert self.r.tou_arbitrage == pytest.approx(ARB_CASE3)
        assert self.r.annual_savings == pytest.approx(ARB_CASE3 + 200.0)
        assert self.r.capital.simple_payback_years == pytest.approx(2772.0 / (ARB_CASE3 + 200.0))

    def test_case3_break_even_from_this_homes_own_numbers(self):
        assert self.r.break_even_cost_per_kwh == pytest.approx(ARB_CASE3 * 10 / 4.62)

    def test_step_chain_is_complete_and_ordered(self):
        assert [s.n for s in self.r.steps] == list(range(1, 11))
        used = set().union(*(s.uses for s in self.r.steps))
        for key in ("annual_usage_kwh", "on_peak_share", "residual_coverage", "cycles_per_year",
                    "installed_cost_per_kwh", "enrollment_discount_per_kwh",
                    "residual_penalty_per_kwh", "resilience_value_per_year"):
            assert key in used


class TestBriefDepthTable:
    """Case 3 break-even $/kWh falls as on-peak worsens (10,000 kWh, coverage 1.0)."""

    @pytest.mark.parametrize("share,needed,break_even", [
        (0.16, 6.4, 908.125),
        (0.20, 8.0, 726.5),
        (0.25, 10.0, 581.2),
        (0.40, 16.0, 363.25),
    ])
    def test_row(self, share, needed, break_even):
        r = plugin_battery.compute(**{**DEFAULTS, "annual_usage_kwh": 10000.0,
                                      "on_peak_share": share, "residual_coverage": 1.0})
        assert r.case == 3
        assert r.usable_kwh_needed == pytest.approx(needed)
        assert r.break_even_cost_per_kwh == pytest.approx(break_even)


class TestCase2Gravy:
    def setup_method(self):
        self.r = plugin_battery.compute(**{**DEFAULTS, "on_peak_share": 0.10})

    def test_under_the_line_enrolling_alone_wins(self):
        assert self.r.case == 2
        assert self.r.tou.enrollment_only_savings == pytest.approx(6600 * 0.058120 - 660 * 0.367366)
        assert self.r.tou.enrollment_only_savings > 0

    def test_battery_earns_only_the_incremental_shift(self):
        assert self.r.tou_arbitrage == pytest.approx(0.7 * 660 * 0.367366)   # 169.723092

    def test_case2_break_even_uses_the_sourced_per_kwh_value(self):
        assert self.r.break_even_cost_per_kwh == pytest.approx(90.13 * 10)   # ~$901/kWh

    def test_a_cheap_unit_clears_a_powerwall_price_does_not(self):
        assert 600.0 < self.r.break_even_cost_per_kwh   # station price clears
        assert 998.0 > self.r.break_even_cost_per_kwh   # Powerwall price does not


class TestRescueFloor:
    def test_no_arbitrage_when_flat_still_wins(self):
        r = plugin_battery.compute(**{**DEFAULTS, "on_peak_share": 0.40,
                                      "residual_coverage": 0.2})
        assert r.tou_arbitrage == 0.0
        assert r.annual_savings == pytest.approx(200.0)   # resilience only


class TestDefaultsFromAssumptions:
    def test_round_trip_matches_explicit_compute(self):
        a = {**capital_assumptions(), **plugin_battery_assumptions()}
        r = plugin_battery.compute_from_assumptions(a)
        assert r.upfront_cost == pytest.approx(2772.0)
        assert r.annual_savings == pytest.approx(ARB_CASE3 + 200.0)
        assert r.capital.horizon_years == 10   # plugin overrides the 25-yr PV default

    def test_the_two_honest_unknowns_ship_unsourced(self):
        a = plugin_battery_assumptions()
        assert a["installed_cost_per_kwh"].tag == UNSOURCED
        assert a["residual_coverage"].tag == UNSOURCED
        assert a["on_peak_share"].tag == UNSOURCED       # the user's own metered number
        for key in ("enrollment_discount_per_kwh", "residual_penalty_per_kwh",
                    "value_per_usable_kwh_yr", "cycles_per_year", "federal_itc_pct"):
            assert a[key].tag == DEFAULT_SOURCED, key


class TestGuards:
    def test_rejects_zero_cycles(self):
        with pytest.raises(ValueError):
            plugin_battery.compute(**{**DEFAULTS, "cycles_per_year": 0.0})

    def test_rejects_itc_out_of_range(self):
        with pytest.raises(ValueError):
            plugin_battery.compute(**{**DEFAULTS, "federal_itc_pct": 2.0})

    def test_rejects_bad_share(self):
        with pytest.raises(ValueError):
            plugin_battery.compute(**{**DEFAULTS, "on_peak_share": 1.5})


# --------------------------------------------------------------------- CLI surface

def run_cli(*args):
    res = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return res.stdout


class TestCli:
    def test_json_schema_and_worked_numbers(self):
        payload = json.loads(run_cli("--option", "plugin-battery", "--json"))
        assert payload["option"] == "plugin-battery"
        assert payload["result"]["upfront_cost"] == pytest.approx(2772.0)
        assert payload["result"]["annual_savings_year1"] == pytest.approx(ARB_CASE3 + 200.0)
        assert payload["assumptions"]["installed_cost_per_kwh"]["is_unsourced"]

    def test_compare_row_matches_single_option_payload(self):
        both = json.loads(run_cli("--compare", "battery,plugin-battery", "--json"))
        alone = json.loads(run_cli("--option", "plugin-battery", "--json"))
        assert both["options"]["plugin-battery"] == alone

    def test_text_render_names_the_case(self):
        out = run_cli("--option", "plugin-battery")
        assert "Plug-In / DIY Battery" in out
        assert "case" in out.lower()
        assert "Break-even" in out

    def test_shared_usage_flag_reaches_the_option(self):
        payload = json.loads(run_cli("--compare", "community,plugin-battery", "--json",
                                     "--annual-usage", "10000"))
        asm = payload["options"]["plugin-battery"]["assumptions"]["annual_usage_kwh"]
        assert asm["value"] == pytest.approx(10000.0)
        assert asm["tag"] == "user-provided"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
