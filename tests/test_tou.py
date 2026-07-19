"""Formula-correctness tests for the shared TOU three-case engine (src/tou.py).

The rates are exact algebra on the CMP Rate TOU tariff (eff. 2026-07-01):
  discount = flat - off-peak = 0.119590 - 0.061470 = 0.058120
  penalty  = on-peak - off-peak = 0.428836 - 0.061470 = 0.367366
  threshold on-peak share = discount / penalty = 0.158207... (the brief's 0.1582)

Run with: pytest tests
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import tou  # noqa: E402

D, P = 0.058120, 0.367366


def ev(usage=6600.0, share=0.25, coverage=0.7, discount=D, penalty=P):
    return tou.evaluate(usage, share, coverage, discount, penalty)


class TestThreshold:
    def test_threshold_is_discount_over_penalty(self):
        assert ev().threshold_share == pytest.approx(D / P)
        assert ev().threshold_share == pytest.approx(0.1582, abs=5e-5)

    def test_case_classification_around_the_line(self):
        assert ev(share=0.15).case == 2
        assert ev(share=0.15).under_threshold
        assert ev(share=0.16).case == 3
        assert not ev(share=0.16).under_threshold

    def test_enrollment_only_savings_change_sign_at_the_line(self):
        # Case 1 is the no-battery check: positive under the line, negative over it.
        assert ev(share=0.10).enrollment_only_savings > 0
        assert ev(share=0.25).enrollment_only_savings < 0
        # and exactly U x d - on_peak x p:
        assert ev(share=0.10).enrollment_only_savings == pytest.approx(
            6600 * D - 660 * P)


class TestMasterEquation:
    def test_savings_vs_flat(self):
        # U x d - R x p with R = (1 - coverage) x on-peak
        r = ev()
        assert r.on_peak_kwh == pytest.approx(1650.0)
        assert r.shifted_kwh == pytest.approx(1155.0)
        assert r.residual_kwh == pytest.approx(495.0)
        assert r.savings_vs_flat == pytest.approx(6600 * D - 495 * P)

    def test_case2_arbitrage_is_incremental_shifted_kwh_only(self):
        # Under the line the enrollment discount is NOT the battery's to claim.
        r = ev(share=0.10)
        assert r.arbitrage == pytest.approx(r.shifted_kwh * P)
        assert r.arbitrage < r.savings_vs_flat  # the flat-vs-TOU win is bigger than its share

    def test_case3_arbitrage_is_net_vs_flat_floored_at_zero(self):
        r = ev(share=0.25)
        assert r.arbitrage == pytest.approx(r.savings_vs_flat)
        deep = ev(share=0.40, coverage=0.2)
        assert deep.savings_vs_flat < 0
        assert deep.arbitrage == 0.0

    def test_full_coverage_earns_the_ceiling(self):
        # A battery shifting everything earns exactly the enrollment ceiling U x d in Case 3.
        r = ev(share=0.25, coverage=1.0)
        assert r.arbitrage == pytest.approx(6600 * D)

    def test_ceiling_table_from_the_handoff(self):
        # usage x 0.058120 — the magic-free-battery maximum, per the handoff's table.
        for usage, ceiling in [(5000, 290.60), (10000, 581.20), (15000, 871.80), (20000, 1162.40)]:
            r = ev(usage=usage, share=0.25, coverage=1.0)
            assert r.arbitrage == pytest.approx(ceiling, abs=0.005)


class TestGuards:
    @pytest.mark.parametrize("kwargs", [
        dict(usage=-1.0),
        dict(share=1.5),
        dict(share=-0.1),
        dict(coverage=1.1),
        dict(discount=-0.01),
        dict(penalty=0.0),
    ])
    def test_rejects_out_of_range(self, kwargs):
        with pytest.raises(ValueError):
            ev(**kwargs)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
