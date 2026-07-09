"""Spend-ledger tests: accumulation, restart persistence, cap enforcement, gitignore.

No network anywhere. Run with: pytest service/tests
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spend import SpendLedger, cost_usd  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def make_ledger(tmp_path, cap=5.0):
    return SpendLedger(path=str(tmp_path / "spend.json"), cap_usd=cap)


class TestCost:
    def test_opus_prices(self):
        # claude-opus-4-8: $5/MTok in, $25/MTok out.
        assert cost_usd(1_000_000, 0) == pytest.approx(5.0)
        assert cost_usd(0, 1_000_000) == pytest.approx(25.0)
        assert cost_usd(1000, 500) == pytest.approx(0.005 + 0.0125)


class TestLedger:
    def test_accumulates_across_calls(self, tmp_path):
        ledger = make_ledger(tmp_path)
        ledger.record(1000, 500)
        ledger.record(1000, 500)
        assert ledger.total_usd == pytest.approx(2 * (0.005 + 0.0125))

    def test_persists_across_restarts(self, tmp_path):
        make_ledger(tmp_path).record(200_000, 40_000)  # 1.0 + 1.0 = $2
        reopened = make_ledger(tmp_path)               # a fresh process reading the same file
        assert reopened.total_usd == pytest.approx(2.0)

    def test_blocks_when_cap_reached(self, tmp_path):
        ledger = make_ledger(tmp_path, cap=1.0)
        assert not ledger.over_cap
        ledger.record(200_000, 0)  # $1.00 — the cap is a ceiling: >= blocks
        assert ledger.over_cap

    def test_corrupt_ledger_fails_closed(self, tmp_path):
        path = tmp_path / "spend.json"
        path.write_text("{not json", encoding="utf-8")
        ledger = SpendLedger(path=str(path), cap_usd=5.0)
        assert ledger.over_cap  # unreadable state must never mean free spending

    def test_ledger_file_is_gitignored(self):
        with open(os.path.join(REPO_ROOT, ".gitignore"), encoding="utf-8") as fh:
            assert "service/.spend.json" in fh.read()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
