"""Tests for the shared tool core — the payload builder behind /ask, MCP, and these tests.

Two things are being held here, and they're the reasons the module exists:

1. **Parity is a test, not a claim.** Every payload ``tools_core.calculate()`` returns must equal
   what ``python src/cli.py --option <key> --json`` prints for the same inputs. If the two ever
   drift, an agent and a human asking the same question get different numbers — the exact failure
   this repo's whole verification discipline is built to prevent.
2. **The clamp rejects rather than clamps.** An out-of-range override must produce an error, never
   a quietly different answer.

No network anywhere. Run with: pytest service/tests
"""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools_core  # noqa: E402

CLI = os.path.join(os.path.dirname(__file__), "..", "..", "src", "cli.py")


def run_cli(*args):
    res = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


class TestCliParity:
    """The claim: an agent and a human get the same numbers. Stated as an equality."""

    @pytest.mark.parametrize("option", [
        "community", "balcony", "rooftop", "battery", "plugin-battery",
        "battery+rooftop", "battery+balcony",
    ])
    def test_defaults_match_cli_json(self, option):
        payload, ignored = tools_core.calculate(option)
        assert payload == run_cli("--option", option, "--json")
        assert ignored == {}

    def test_override_matches_cli_set(self):
        payload, _ = tools_core.calculate("rooftop", {"capacity_kw": 8})
        assert payload == run_cli("--option", "rooftop", "--json", "--set", "capacity_kw=8")

    def test_overridden_value_is_tagged_user_provided(self):
        # An extracted or agent-supplied number is not a source.
        payload, _ = tools_core.calculate("rooftop", {"capacity_kw": 8})
        assert payload["assumptions"]["capacity_kw"]["tag"] == "user-provided"

    def test_community_bill_matches_cli(self):
        payload, _ = tools_core.calculate("community", {"monthly_bill": 220})
        assert payload == run_cli("--bill", "220", "--json")

    def test_compare_rows_are_each_options_own_payload(self):
        # Tabulated, never recomputed: every row must equal what calculate() says alone.
        result = tools_core.compare(["community", "rooftop"])
        for key in ("community", "rooftop"):
            alone, _ = tools_core.calculate(key)
            assert result["options"][key] == alone


class TestClamp:
    """R20 — what makes public, no-auth exposure honest."""

    @pytest.mark.parametrize("key", ["horizon_years", "battery_horizon_years"])
    def test_absurd_horizon_is_rejected_not_materialized(self, key):
        option = "battery+rooftop" if key.startswith("battery_") else "rooftop"
        with pytest.raises(tools_core.ToolError) as e:
            tools_core.calculate(option, {key: 1e9})
        assert "between 1 and 100" in str(e.value)

    def test_rejection_happens_before_any_computation(self):
        # If this ever starts passing by computing first, the vector is open again: the point is
        # that no YearRow list is ever built. A 1e9-year horizon would not return in test time.
        with pytest.raises(tools_core.ToolError):
            tools_core.calculate("rooftop", {"horizon_years": float("inf")})

    def test_boundary_values_are_allowed(self):
        payload, _ = tools_core.calculate("rooftop", {"horizon_years": 100})
        assert payload["result"]["horizon_years"] == 100

    def test_zero_and_negative_horizons_rejected(self):
        for bad in (0, -5):
            with pytest.raises(tools_core.ToolError):
                tools_core.calculate("rooftop", {"horizon_years": bad})

    def test_nan_is_rejected(self):
        # NaN propagates silently through float math and JSON-encodes as null — an error is better.
        with pytest.raises(tools_core.ToolError):
            tools_core.calculate("rooftop", {"capacity_kw": float("nan")})

    def test_non_numeric_is_rejected(self):
        with pytest.raises(tools_core.ToolError):
            tools_core.calculate("rooftop", {"capacity_kw": "eight"})

    def test_the_clamp_reaches_the_ask_path_too(self):
        # /ask routes through tools_core precisely so it inherits this. Extraction.inputs is an
        # open dict[str, float], so without it a routed question could carry the same payload.
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agent import Extraction, compute_payload

        with pytest.raises(ValueError):
            compute_payload(Extraction(option="rooftop", inputs={"horizon_years": 1e9}))


class TestToolSurface:
    def test_list_options_covers_every_option(self):
        keys = [o["key"] for o in tools_core.list_options()]
        assert keys == list(tools_core.ALL_OPTION_KEYS)
        assert all(o["label"] and o["blurb"] for o in tools_core.list_options())
        assert [o["key"] for o in tools_core.list_options() if o["needs_bill"]] == ["community"]

    def test_get_assumptions_keys_are_the_keys_calculate_accepts(self):
        # The contract an agent relies on: read the ledger, then override by the same keys. Each
        # key is fed back its OWN current value, so this tests the key mapping without tripping
        # any option's range validation.
        for option in ("community", "rooftop", "battery", "battery+rooftop"):
            shown = tools_core.get_assumptions(option)["assumptions"]
            echo = {k: a["value"] for k, a in shown.items()}
            _, ignored = tools_core.calculate(option, echo)
            assert ignored == {}, f"{option}: {sorted(ignored)}"

    def test_assumptions_carry_source_provenance(self):
        a = tools_core.get_assumptions("rooftop")["assumptions"]["installed_cost_per_w"]
        assert a["tag"] == "default (sourced)"
        assert a["source"]["title"] and a["source"]["what_is_it"]
        assert a["explain"]

    def test_unsourced_assumptions_say_so(self):
        a = tools_core.get_assumptions("plugin-battery")["assumptions"]["installed_cost_per_kwh"]
        assert a["is_unsourced"] and a["source"] is None

    def test_unknown_option_is_a_tool_error(self):
        with pytest.raises(tools_core.ToolError):
            tools_core.calculate("nuclear")

    def test_unmapped_input_is_surfaced_not_dropped(self):
        _, ignored = tools_core.calculate("community", {"capacity_kw": 8})
        assert ignored == {"capacity_kw": 8}

    def test_battery_prefix_mismatch_is_tolerated(self):
        # A caller may send bare or battery_-prefixed keys for a combo; both must land.
        _, ignored = tools_core.calculate("battery+rooftop", {"usable_kwh": 20})
        assert ignored == {}

    def test_compare_needs_at_least_two_options(self):
        with pytest.raises(tools_core.ToolError):
            tools_core.compare(["rooftop"])

    def test_compare_rejects_duplicates(self):
        with pytest.raises(tools_core.ToolError):
            tools_core.compare(["rooftop", "rooftop"])

    def test_compare_summary_marks_community_capital_as_not_applicable(self):
        summary = {r["option"]: r for r in
                   tools_core.compare(["community", "rooftop"])["summary"]}
        assert summary["community"]["npv"] is None          # not 0 — it doesn't apply
        assert summary["community"]["simple_payback_years"] is None
        assert summary["rooftop"]["npv"] is not None

    def test_shared_input_moves_every_option_carrying_it(self):
        result = tools_core.compare(["rooftop", "battery+rooftop"], {"annual_usage_kwh": 12000})
        for key in ("rooftop", "battery+rooftop"):
            asm = result["options"][key]["assumptions"]["annual_usage_kwh"]
            assert asm["value"] == pytest.approx(12000)
            assert asm["tag"] == "user-provided"

    def test_shared_input_no_option_carries_is_an_error_not_a_no_op(self):
        with pytest.raises(tools_core.ToolError):
            tools_core.compare(["community", "balcony"], {"not_a_real_key": 1})


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
