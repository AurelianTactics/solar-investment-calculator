"""Formula-correctness + contract tests for the side-by-side comparison surface (--compare).

A comparison is not a new calculation — it is the SAME per-option calculation, run over shared
inputs and tabulated. So the metric here is parity: every row of `--compare a,b` must equal what
`--option a` and `--option b` say on their own. If a comparison could drift from the single-option
answer, the table would be quietly lying about the thing it is asking you to choose between.

The other half is the shared/scoped --set split, which mirrors the web drawer:
  --set key=value          -> shared: every compared option carrying the key moves together
  --set option:key=value   -> that option's ledger only

Run with: pytest tests
"""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from assumptions import DEFAULT_SOURCED, USER_PROVIDED  # noqa: E402

CLI = os.path.join(os.path.dirname(__file__), "..", "src", "cli.py")


def run_cli(*args):
    res = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return res.stdout


def run_cli_fail(*args):
    res = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, timeout=60)
    assert res.returncode != 0, f"expected failure, got:\n{res.stdout}"
    return res.stdout + res.stderr


class TestComparePayloadParity:
    """Each row carries the option's own --json payload, unchanged."""

    def test_row_matches_single_option_payload(self):
        both = json.loads(run_cli("--compare", "community,rooftop", "--json"))
        alone = json.loads(run_cli("--option", "rooftop", "--json"))
        assert both["options"]["rooftop"] == alone

    def test_community_row_matches_single_option_payload(self):
        both = json.loads(run_cli("--compare", "community,balcony", "--json", "--bill", "150"))
        alone = json.loads(run_cli("--option", "community", "--json", "--bill", "150"))
        assert both["options"]["community"] == alone

    def test_combo_row_matches_single_option_payload(self):
        both = json.loads(run_cli("--compare", "battery,battery+rooftop", "--json"))
        alone = json.loads(run_cli("--option", "battery+rooftop", "--json"))
        assert both["options"]["battery+rooftop"] == alone

    def test_comparison_preserves_requested_order(self):
        payload = json.loads(run_cli("--compare", "rooftop,community,battery", "--json"))
        assert payload["comparison"] == ["rooftop", "community", "battery"]

    def test_shared_inputs_reported(self):
        payload = json.loads(run_cli("--compare", "community,rooftop", "--json"))
        shared = payload["shared_inputs"]
        assert shared["monthly_bill"] == pytest.approx(168.41)
        assert shared["annual_usage_kwh"]["value"] == pytest.approx(6600.0)
        assert shared["opportunity_rate"]["value"] == pytest.approx(0.07)

    def test_shared_bill_omitted_when_no_option_uses_it(self):
        payload = json.loads(run_cli("--compare", "balcony,battery", "--json"))
        assert "monthly_bill" not in payload["shared_inputs"]


class TestSharedOverrides:
    """A bare --set is YOUR situation: it moves every option that carries the key."""

    def test_shared_set_reaches_every_carrying_option(self):
        payload = json.loads(run_cli(
            "--compare", "rooftop,battery+rooftop", "--json", "--set", "opportunity_rate=0.03"))
        for key in ("rooftop", "battery+rooftop"):
            asm = payload["options"][key]["assumptions"]["opportunity_rate"]
            assert asm["value"] == pytest.approx(0.03)
            assert asm["tag"] == USER_PROVIDED
        assert payload["shared_inputs"]["opportunity_rate"]["value"] == pytest.approx(0.03)

    def test_shared_set_skips_options_without_the_key(self):
        # community has no capacity_kw; the balcony row still moves, and nothing errors.
        payload = json.loads(run_cli(
            "--compare", "community,balcony", "--json", "--set", "capacity_kw=0.8"))
        assert payload["options"]["balcony"]["assumptions"]["capacity_kw"]["value"] == pytest.approx(0.8)
        assert "capacity_kw" not in payload["options"]["community"]["assumptions"]

    def test_shared_usage_reaches_rooftop_assumption(self):
        payload = json.loads(run_cli(
            "--compare", "community,rooftop", "--json", "--annual-usage", "9000"))
        asm = payload["options"]["rooftop"]["assumptions"]["annual_usage_kwh"]
        assert asm["value"] == pytest.approx(9000.0)
        assert asm["tag"] == USER_PROVIDED
        # rooftop's savings are capped by usage: 9,000 kWh of generation isn't available from
        # 5.5 kW, so effective stays at generation (6,600 kWh) -> savings unchanged.
        assert payload["options"]["rooftop"]["result"]["annual_savings_year1"] == pytest.approx(1782.0)

    def test_shared_rate_keeps_npvs_comparable(self):
        payload = json.loads(run_cli(
            "--compare", "balcony,rooftop", "--json", "--set", "opportunity_rate=0.10"))
        rates = [v["result"]["opportunity_rate"] for v in payload["options"].values()]
        assert rates == [pytest.approx(0.10), pytest.approx(0.10)]


class TestScopedOverrides:
    """`option:key=value` is one option's ledger: the other rows must not move."""

    def test_scoped_set_touches_only_its_option(self):
        payload = json.loads(run_cli(
            "--compare", "rooftop,battery+rooftop", "--json", "--set", "rooftop:capacity_kw=8"))
        assert payload["options"]["rooftop"]["assumptions"]["capacity_kw"]["value"] == pytest.approx(8.0)
        other = payload["options"]["battery+rooftop"]["assumptions"]["capacity_kw"]
        assert other["value"] == pytest.approx(5.5)
        assert other["tag"] == DEFAULT_SOURCED

    def test_scoped_set_changes_only_its_row_result(self):
        payload = json.loads(run_cli(
            "--compare", "rooftop,battery+rooftop", "--json", "--set", "rooftop:capacity_kw=8"))
        # 8 kW x 1000 x $2.95/W = $23,600 for the scoped row; the combo keeps 5.5 kW -> $29,698.
        assert payload["options"]["rooftop"]["result"]["upfront_cost"] == pytest.approx(23600.0)
        assert payload["options"]["battery+rooftop"]["result"]["upfront_cost"] == pytest.approx(29698.0)

    def test_scoped_and_shared_sets_combine(self):
        payload = json.loads(run_cli(
            "--compare", "rooftop,battery+rooftop", "--json",
            "--set", "opportunity_rate=0.03", "--set", "rooftop:capacity_kw=8"))
        assert payload["options"]["rooftop"]["assumptions"]["capacity_kw"]["value"] == pytest.approx(8.0)
        for key in ("rooftop", "battery+rooftop"):
            assert payload["options"][key]["result"]["opportunity_rate"] == pytest.approx(0.03)


class TestCompareErrors:
    """Every rejection names what to do instead — a silent no-op would be the real failure."""

    def test_single_option_rejected(self):
        assert "at least two" in run_cli_fail("--compare", "community")

    def test_duplicate_option_rejected(self):
        assert "twice" in run_cli_fail("--compare", "community,community")

    def test_unknown_option_rejected(self):
        out = run_cli_fail("--compare", "community,nuclear")
        assert "unknown option" in out and "battery+rooftop" in out  # lists what IS known

    def test_unknown_shared_key_rejected_not_ignored(self):
        out = run_cli_fail("--compare", "community,balcony", "--set", "usable_kwh=9")
        assert "no compared option carries it" in out

    def test_scoped_set_to_uncompared_option_rejected(self):
        out = run_cli_fail("--compare", "community,balcony", "--set", "rooftop:capacity_kw=9")
        assert "isn't in --compare" in out

    def test_scoped_unknown_key_rejected(self):
        out = run_cli_fail("--compare", "community,balcony", "--set", "balcony:nope=9")
        assert "unknown assumption key for balcony" in out

    def test_non_numeric_value_rejected(self):
        assert "numeric" in run_cli_fail("--compare", "community,balcony", "--set", "capacity_kw=big")


class TestCompareText:
    """The human surface: the table, and the transparency rules that apply everywhere."""

    def test_table_lists_every_option(self):
        out = run_cli("--compare", "community,balcony,rooftop")
        for label in ("Community Solar", "Balcony / Plug-In Solar", "Rooftop Solar"):
            assert label in out
        assert "SHARED INPUTS" in out

    def test_community_shows_no_payback_or_npv(self):
        # $0 capital: payback/NPV are meaningless, not zero — the row must not invent them.
        line = next(l for l in run_cli("--compare", "community,balcony").splitlines()
                    if "Community Solar" in l and "$0" in l)
        assert "0.0 yr" not in line and "$0.00" not in line

    def test_unsourced_assumptions_flagged(self):
        out = run_cli("--compare", "community,balcony")
        assert "unsourced" in out and "Electrician install cost" in out

    def test_refine_instructions_shown(self):
        out = run_cli("--compare", "community,balcony")
        assert "--set option:key=value" in out and "--option KEY" in out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
