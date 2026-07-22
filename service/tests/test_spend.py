"""Spend-ledger tests: accumulation, restart persistence, the rolling daily window, cap
enforcement, fail-closed posture, gitignore.

No network anywhere. Run with: pytest service/tests
"""

import datetime
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spend import SpendLedger, cost_usd  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def make_ledger(tmp_path, cap=5.0):
    return SpendLedger(path=str(tmp_path / "spend.json"), cap_usd=cap)


class TestCost:
    def test_sonnet_prices(self):
        # claude-sonnet-5: $3/MTok in, $15/MTok out (standard rate).
        assert cost_usd(1_000_000, 0) == pytest.approx(3.0)
        assert cost_usd(0, 1_000_000) == pytest.approx(15.0)
        assert cost_usd(1000, 500) == pytest.approx(0.003 + 0.0075)


class TestLedger:
    def test_accumulates_across_calls(self, tmp_path):
        ledger = make_ledger(tmp_path)
        ledger.record(1000, 500)
        ledger.record(1000, 500)
        assert ledger.total_usd == pytest.approx(2 * cost_usd(1000, 500))

    def test_persists_across_restarts(self, tmp_path):
        make_ledger(tmp_path).record(200_000, 40_000)  # some spend, exact rate aside
        reopened = make_ledger(tmp_path)               # a fresh process reading the same file
        assert reopened.total_usd == pytest.approx(cost_usd(200_000, 40_000))

    def test_blocks_when_cap_reached(self, tmp_path):
        boundary = cost_usd(200_000, 0)                # cap set to exactly one recording's cost
        ledger = make_ledger(tmp_path, cap=boundary)
        assert not ledger.over_cap
        ledger.record(200_000, 0)  # lands exactly on the cap — the ceiling is inclusive (>= blocks)
        assert ledger.over_cap

    def test_corrupt_ledger_fails_closed(self, tmp_path):
        path = tmp_path / "spend.json"
        path.write_text("{not json", encoding="utf-8")
        ledger = SpendLedger(path=str(path), cap_usd=5.0)
        assert ledger.over_cap  # unreadable state must never mean free spending

    def test_ledger_file_is_gitignored(self):
        with open(os.path.join(REPO_ROOT, ".gitignore"), encoding="utf-8") as fh:
            assert "service/.spend.json" in fh.read()


class TestDailyWindow:
    """The cap is $X per day, not $X ever — otherwise a public deploy blows a fuse once and
    serves cap_exceeded until a human deletes a file."""

    def test_yesterdays_spend_does_not_count_against_today(self, tmp_path):
        path = tmp_path / "spend.json"
        path.write_text(json.dumps({"day": "2020-01-01", "total_usd": 99.0, "calls": 7}),
                        encoding="utf-8")
        ledger = SpendLedger(path=str(path), cap_usd=1.0)
        assert ledger.total_usd == 0.0
        assert not ledger.over_cap

    def test_recording_after_a_rollover_starts_from_zero(self, tmp_path):
        path = tmp_path / "spend.json"
        path.write_text(json.dumps({"day": "2020-01-01", "total_usd": 99.0, "calls": 7}),
                        encoding="utf-8")
        ledger = SpendLedger(path=str(path), cap_usd=5.0)
        ledger.record(200_000, 0)
        assert ledger.total_usd == pytest.approx(cost_usd(200_000, 0))  # this call only, not 100.0
        assert json.loads(path.read_text(encoding="utf-8"))["day"] == SpendLedger.today()

    def test_same_day_still_accumulates(self, tmp_path):
        ledger = make_ledger(tmp_path)
        ledger.record(200_000, 0)
        ledger.record(200_000, 0)
        assert ledger.total_usd == pytest.approx(2 * cost_usd(200_000, 0))

    def test_a_pre_daily_window_file_reads_as_a_new_day(self, tmp_path):
        # Files written by the cumulative-forever version carry no "day" key at all. Treating
        # them as today would import an arbitrary lifetime total into one day's budget.
        path = tmp_path / "spend.json"
        path.write_text(json.dumps({"total_usd": 4.9, "calls": 300}), encoding="utf-8")
        assert SpendLedger(path=str(path), cap_usd=5.0).total_usd == 0.0

    def test_corrupt_still_fails_closed_under_the_new_window(self, tmp_path):
        # The rollover logic must not become an accidental "unreadable == fresh budget" path.
        path = tmp_path / "spend.json"
        path.write_text('{"day": "2020-01-01", "total_usd": "not-a-number"}', encoding="utf-8")
        assert SpendLedger(path=str(path), cap_usd=5.0).over_cap

    def test_window_is_utc(self, tmp_path):
        assert SpendLedger.today() == datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
