"""Formula-correctness tests for the plug-in / DIY DER battery option (the active metric).

Scope (2026-07-20): this option models ONE situation — the home already under the TOU on-peak
line (share < 0.1582), where enrolling lowers the bill on its own and the battery adds arbitrage
on top. Over the line is out of scope and raises; see docs/BACKLOG.md.

Hand-verified worked example (shipped defaults; CMP Rate TOU rates):
  6,600 kWh home, 12% on-peak, 70% coverage -> under the 0.1582 line
  on-peak 792 kWh; shifted 554.4; residual 237.6
  enrolling alone = 6600 x 0.058120 - 792 x 0.367366 = 383.592 - 290.953872 = 92.638128 $/yr
  arb    = 554.4 x 0.367366 = 203.6677104 $/yr   (incremental over enrolling alone)
  size   = 554.4 / 250 = 2.2176 kWh; gross = 2.2176 x $600 = $1,330.56 (itc 0)
  annual = 203.6677104 + 200 resilience = 403.6677104
  payback = 1330.56 / 403.6677104 = 3.296 yr
  break-even = 90.13 x 10 = $901.30/kWh (a $600/kWh unit clears it; a $998 Powerwall doesn't)

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
    on_peak_share=0.12,
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

ARB = 554.4 * 0.367366            # 203.6677104
ENROLL_ONLY = 6600 * 0.058120 - 792 * 0.367366   # 92.638128


class TestWorkedExample:
    def setup_method(self):
        self.r = plugin_battery.compute(**DEFAULTS)

    def test_load_split(self):
        assert self.r.tou.under_threshold
        assert self.r.tou.on_peak_kwh == pytest.approx(792.0)
        assert self.r.tou.shifted_kwh == pytest.approx(554.4)
        assert self.r.tou.residual_kwh == pytest.approx(237.6)

    def test_enrolling_alone_already_lowers_the_bill(self):
        # The battery's baseline: this saving is the rate change's, not the hardware's.
        assert self.r.enrollment_only_savings == pytest.approx(ENROLL_ONLY)
        assert self.r.enrollment_only_savings > 0

    def test_battery_sized_to_the_shifted_load(self):
        assert self.r.usable_kwh_needed == pytest.approx(2.2176)
        assert self.r.gross_cost == pytest.approx(1330.56)
        assert self.r.upfront_cost == pytest.approx(1330.56)   # itc 0

    def test_arbitrage_is_the_incremental_shift_only(self):
        # Not the whole TOU-vs-flat win — the enrollment discount is the rate's, not the battery's.
        assert self.r.tou_arbitrage == pytest.approx(ARB)
        assert self.r.tou_arbitrage < self.r.tou.savings_vs_flat

    def test_annual_value_and_payback(self):
        assert self.r.annual_savings == pytest.approx(ARB + 200.0)
        assert self.r.capital.simple_payback_years == pytest.approx(1330.56 / (ARB + 200.0))
        assert self.r.capital.npv > 0        # pays back well inside the 10-yr horizon

    def test_break_even_uses_the_sourced_per_kwh_value(self):
        assert self.r.break_even_cost_per_kwh == pytest.approx(90.13 * 10)   # $901.30

    def test_a_cheap_unit_clears_it_a_powerwall_does_not(self):
        assert 600.0 < self.r.break_even_cost_per_kwh
        assert 998.0 > self.r.break_even_cost_per_kwh

    def test_step_chain_is_complete_and_ordered(self):
        assert [s.n for s in self.r.steps] == list(range(1, 11))
        used = set().union(*(s.uses for s in self.r.steps))
        for key in ("annual_usage_kwh", "on_peak_share", "residual_coverage", "cycles_per_year",
                    "installed_cost_per_kwh", "enrollment_discount_per_kwh",
                    "residual_penalty_per_kwh", "resilience_value_per_year",
                    "value_per_usable_kwh_yr"):
            assert key in used


class TestScope:
    """Over the line is refused, not half-answered."""

    @pytest.mark.parametrize("share", [0.16, 0.25, 0.40])
    def test_over_the_line_raises_out_of_scope(self, share):
        with pytest.raises(plugin_battery.OutOfScope) as e:
            plugin_battery.compute(**{**DEFAULTS, "on_peak_share": share})
        msg = str(e.value)
        assert "0.1582" in msg               # names the line you're over
        assert f"{share:.4f}" in msg         # and where you actually are
        assert "BACKLOG" in msg              # and where the missing case lives

    def test_out_of_scope_is_a_value_error_so_every_surface_handles_it(self):
        assert issubclass(plugin_battery.OutOfScope, ValueError)

    def test_just_under_the_line_still_computes(self):
        r = plugin_battery.compute(**{**DEFAULTS, "on_peak_share": 0.15})
        assert r.tou_arbitrage > 0


class TestDefaultsFromAssumptions:
    def test_round_trip_matches_explicit_compute(self):
        a = {**capital_assumptions(), **plugin_battery_assumptions()}
        r = plugin_battery.compute_from_assumptions(a)
        assert r.upfront_cost == pytest.approx(1330.56)
        assert r.annual_savings == pytest.approx(ARB + 200.0)
        assert r.capital.horizon_years == 10   # plugin overrides the 25-yr PV default

    def test_shipped_default_is_a_home_this_option_models(self):
        a = plugin_battery_assumptions()
        threshold = (a["enrollment_discount_per_kwh"].value
                     / a["residual_penalty_per_kwh"].value)
        assert a["on_peak_share"].value < threshold

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

def run_cli(*args, expect_ok=True):
    res = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, timeout=60)
    if expect_ok:
        assert res.returncode == 0, res.stderr
    return res


class TestCli:
    def test_json_schema_and_worked_numbers(self):
        payload = json.loads(run_cli("--option", "plugin-battery", "--json").stdout)
        assert payload["option"] == "plugin-battery"
        assert payload["result"]["upfront_cost"] == pytest.approx(1330.56)
        assert payload["result"]["annual_savings_year1"] == pytest.approx(ARB + 200.0)
        assert payload["assumptions"]["installed_cost_per_kwh"]["is_unsourced"]

    def test_compare_row_matches_single_option_payload(self):
        both = json.loads(run_cli("--compare", "battery,plugin-battery", "--json").stdout)
        alone = json.loads(run_cli("--option", "plugin-battery", "--json").stdout)
        assert both["options"]["plugin-battery"] == alone

    def test_text_render_shows_the_shopping_number(self):
        out = run_cli("--option", "plugin-battery").stdout
        assert "Plug-In / DIY Battery" in out
        assert "Break-even" in out

    def test_over_the_line_exits_with_a_readable_message(self):
        res = run_cli("--option", "plugin-battery", "--set", "on_peak_share=0.25",
                      expect_ok=False)
        assert res.returncode != 0
        assert "under the TOU on-peak line" in res.stderr
        assert "Traceback" not in res.stderr    # a clean error, not a crash

    def test_shared_usage_flag_reaches_the_option(self):
        payload = json.loads(run_cli("--compare", "community,plugin-battery", "--json",
                                     "--annual-usage", "10000").stdout)
        asm = payload["options"]["plugin-battery"]["assumptions"]["annual_usage_kwh"]
        assert asm["value"] == pytest.approx(10000.0)
        assert asm["tag"] == "user-provided"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
