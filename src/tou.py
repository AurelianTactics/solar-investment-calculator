"""Time-of-use arbitrage — the master equation and three-case branch, shared by the
installed battery (``battery.py``, optional ``tou_enrolled`` mode) and the plug-in DER battery
(``plugin_battery.py``, where time-of-use arbitrage is the whole point).

The model (sourced to the CMP time-of-use delivery-rate tariff, eff. 2026-07-01, via
../solar-investment-research/wiki/calculator-brief/plugin-battery-answers.md):

    TOU_savings_vs_flat = U x discount  -  R x penalty

where U is annual kWh, R is the *residual* on-peak kWh a battery does not shift,
``discount`` = flat delivery - off-peak delivery (what every kWh earns just by enrolling), and
``penalty`` = on-peak delivery - off-peak delivery (what every residual on-peak kWh costs).
All spreads are delivery-only: supply is flat and cancels. The penalty is the *penalty avoided*
per shifted kWh, NOT the saving vs. flat — modeling it as the saving double-counts the
enrollment discount (the exact trap the research handoff warns against).

The branch (who your baseline is decides what the battery earns):

  Case 1 — threshold check, no battery: time-of-use beats flat iff on_peak_share < discount/penalty
           (0.1582 for CMP, matching CMP's own ">=86% off-peak" guidance ~2 pts conservative).
  Case 2 — already under the line ("gravy"): the baseline is time-of-use-without-battery, so the
           battery's arbitrage is only the *incremental* penalty avoided: shifted_kwh x penalty.
  Case 3 — over the line ("rescue"): time-of-use-without-battery loses, so the baseline is FLAT ($0);
           the battery earns the whole net vs. flat, floored at 0 (below 0 you simply stay on
           the flat rate and the battery earns no arbitrage).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TouResult:
    on_peak_kwh: float
    threshold_share: float           # discount / penalty — the Case-1 break-even on-peak share
    under_threshold: bool            # True -> Case 2 territory (time-of-use already beats flat)
    case: int                        # 2 (gravy) or 3 (rescue) — the battery's case
    enrollment_only_savings: float   # U x discount - on_peak x penalty (Case 1; no battery; can be < 0)
    shifted_kwh: float               # residual_coverage x on_peak_kwh (what the battery shifts)
    residual_kwh: float              # (1 - residual_coverage) x on_peak_kwh (still bought on-peak)
    savings_vs_flat: float           # U x discount - residual x penalty (raw; can be < 0)
    arbitrage: float                 # what the battery earns per its case (>= 0)


def evaluate(
    annual_usage_kwh: float,
    on_peak_share: float,
    residual_coverage: float,
    enrollment_discount_per_kwh: float,
    residual_penalty_per_kwh: float,
) -> TouResult:
    if annual_usage_kwh < 0:
        raise ValueError("annual_usage_kwh must be >= 0")
    if not (0.0 <= on_peak_share <= 1.0):
        raise ValueError("on_peak_share must be in [0, 1]")
    if not (0.0 <= residual_coverage <= 1.0):
        raise ValueError("residual_coverage must be in [0, 1]")
    if enrollment_discount_per_kwh < 0:
        raise ValueError("enrollment_discount_per_kwh must be >= 0")
    if residual_penalty_per_kwh <= 0:
        raise ValueError("residual_penalty_per_kwh must be > 0")

    on_peak_kwh = annual_usage_kwh * on_peak_share
    threshold_share = enrollment_discount_per_kwh / residual_penalty_per_kwh
    under_threshold = on_peak_share < threshold_share
    enrollment_only = (annual_usage_kwh * enrollment_discount_per_kwh
                       - on_peak_kwh * residual_penalty_per_kwh)

    shifted_kwh = residual_coverage * on_peak_kwh
    residual_kwh = on_peak_kwh - shifted_kwh
    savings_vs_flat = (annual_usage_kwh * enrollment_discount_per_kwh
                       - residual_kwh * residual_penalty_per_kwh)

    if under_threshold:
        case = 2
        arbitrage = shifted_kwh * residual_penalty_per_kwh   # incremental; baseline = time-of-use alone
    else:
        case = 3
        arbitrage = max(0.0, savings_vs_flat)                # whole net vs. flat; baseline = flat

    return TouResult(
        on_peak_kwh=on_peak_kwh,
        threshold_share=threshold_share,
        under_threshold=under_threshold,
        case=case,
        enrollment_only_savings=enrollment_only,
        shifted_kwh=shifted_kwh,
        residual_kwh=residual_kwh,
        savings_vs_flat=savings_vs_flat,
        arbitrage=arbitrage,
    )
