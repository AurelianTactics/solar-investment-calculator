"""Completeness gate for assumption explanations (R11) and source explanations (R12).

Every assumption must carry a newcomer-grade ``explain`` (what the number means, why it matters
to YOUR savings, what moves it), and every sourced default must say what its source *is*
(``Source.what_is_it``: what kind of document, who publishes it, why it's credible).

The builder list is discovered by introspection so a newly added builder (or a new assumption in
an existing one) fails this gate until its prose lands.

Run with: pytest tests
"""

import inspect
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import assumptions as asm_mod  # noqa: E402
from assumptions import DEFAULT_SOURCED  # noqa: E402

CLI = os.path.join(os.path.dirname(__file__), "..", "src", "cli.py")


def all_builders():
    """Every public zero-arg builder that returns a dict of Assumptions."""
    found = []
    for name, fn in vars(asm_mod).items():
        if name.endswith("_assumptions") and inspect.isfunction(fn) and not name.startswith("_"):
            if not inspect.signature(fn).parameters:
                found.append((name, fn))
    assert len(found) >= 7, f"builder discovery broke: only found {[n for n, _ in found]}"
    return found


def every_assumption():
    for builder_name, fn in all_builders():
        for key, asm in fn().items():
            yield builder_name, key, asm


class TestExplainCompleteness:
    def test_every_assumption_has_newcomer_grade_explain(self):
        missing = [
            f"{b}:{k}" for b, k, a in every_assumption()
            if not (getattr(a, "explain", "") or "").strip() or len(a.explain.strip()) < 40
        ]
        assert not missing, f"assumptions without a real explanation: {missing}"

    def test_every_sourced_default_says_what_its_source_is(self):
        missing = [
            f"{b}:{k}" for b, k, a in every_assumption()
            if a.tag == DEFAULT_SOURCED
            and (a.source is None or not (getattr(a.source, "what_is_it", "") or "").strip())
        ]
        assert not missing, f"sourced defaults whose source lacks what_is_it: {missing}"

    def test_offset_fraction_explanation_meets_the_quality_bar(self):
        # The assumption the user named as the quality bar: a community-solar newcomer should
        # understand it from the expanded text alone (no jargon left unexplained).
        a = asm_mod.default_assumptions()["bill_offset_fraction"]
        text = a.explain.lower()
        assert "fixed" in text, "should explain the fixed charge the credits can't touch"
        assert len(a.explain) > 100


class TestUserValuePreservesExplain:
    def test_with_user_value_keeps_explain_clears_source(self):
        a = asm_mod.default_assumptions()["bill_offset_fraction"]
        edited = a.with_user_value(0.9)
        assert edited.explain == a.explain
        assert edited.source is None
        assert edited.value == 0.9


class TestJsonSchema:
    def run_json(self, *args):
        res = subprocess.run(
            [sys.executable, CLI, *args, "--json"], capture_output=True, text=True, timeout=60
        )
        assert res.returncode == 0, res.stderr
        return json.loads(res.stdout)

    def test_community_json_carries_explain_and_what_is_it(self):
        payload = self.run_json("--bill", "150")
        asm = payload["assumptions"]["bill_offset_fraction"]
        assert asm["explain"].strip()
        assert asm["source"]["what_is_it"].strip()

    def test_combo_json_carries_explain(self):
        payload = self.run_json("--option", "battery+rooftop")
        asm = payload["assumptions"]["battery_pv_interaction_value_per_year"]
        assert asm["explain"].strip()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
