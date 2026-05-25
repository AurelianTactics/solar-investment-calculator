"""Capital-allocation engine — the comparison at the heart of STRATEGY.md.

For options that cost money upfront (balcony, rooftop, battery — *not* community solar), the
question is not just "does it pay back" but **"am I better off buying solar, or investing that same
capital elsewhere?"** This module answers that, with every number exposed (same transparency
mechanic as ``solar_calc``).

It compares two uses of the same upfront capital over a horizon, at one ``opportunity_rate`` (the
return you'd get investing the cash instead):

  (A) invest the cash:   terminal wealth = upfront_cost x (1 + opportunity_rate)^N
  (B) buy solar, invest each year's bill savings at opportunity_rate to the horizon.

Savings in year t escalate with electricity prices and decline with panel degradation:
  savings_t = savings_year1 x (1 + escalation)^(t-1) x (1 - degradation)^(t-1)

Headline outputs:
  - simple_payback_years   : upfront_cost / year-1 savings (the intuitive, undiscounted number)
  - lifetime_savings_nominal: undiscounted sum of savings over the horizon
  - npv                    : -upfront + sum_t savings_t / (1+opportunity_rate)^t.
                             NPV > 0  <=>  solar beats investing the cash. The capital verdict.
  - net_advantage_fv       : (B) - (A) in terminal dollars; same sign as npv (it is npv compounded).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class YearRow:
    year: int
    savings: float          # nominal $ saved that year
    cumulative: float       # nominal $ saved through that year


@dataclass(frozen=True)
class CapitalResult:
    upfront_cost: float
    annual_savings_year1: float
    horizon_years: int
    opportunity_rate: float
    escalation: float
    degradation: float
    simple_payback_years: Optional[float]   # None if year-1 savings <= 0 (never pays back)
    lifetime_savings_nominal: float
    lifetime_roi: float                     # lifetime nominal savings / upfront
    npv: float
    net_advantage_fv: float
    yearly: tuple[YearRow, ...]


def compare(
    upfront_cost: float,
    annual_savings_year1: float,
    horizon_years: int = 25,
    opportunity_rate: float = 0.07,
    escalation: float = 0.0,
    degradation: float = 0.0,
) -> CapitalResult:
    if upfront_cost < 0:
        raise ValueError("upfront_cost must be >= 0")
    if horizon_years < 1:
        raise ValueError("horizon_years must be >= 1")
    if opportunity_rate <= -1:
        raise ValueError("opportunity_rate must be > -1")
    if not (0.0 <= degradation < 1.0):
        raise ValueError("degradation must be in [0, 1)")

    rows: list[YearRow] = []
    cumulative = 0.0
    npv = -upfront_cost
    fv_savings = 0.0  # future value of the reinvested savings stream at the horizon
    for t in range(1, horizon_years + 1):
        savings_t = annual_savings_year1 * (1 + escalation) ** (t - 1) * (1 - degradation) ** (t - 1)
        cumulative += savings_t
        npv += savings_t / (1 + opportunity_rate) ** t
        fv_savings += savings_t * (1 + opportunity_rate) ** (horizon_years - t)
        rows.append(YearRow(year=t, savings=savings_t, cumulative=cumulative))

    fv_lump = upfront_cost * (1 + opportunity_rate) ** horizon_years
    net_advantage_fv = fv_savings - fv_lump

    simple_payback = (
        upfront_cost / annual_savings_year1 if annual_savings_year1 > 0 else None
    )
    lifetime_roi = (cumulative / upfront_cost) if upfront_cost > 0 else float("inf")

    return CapitalResult(
        upfront_cost=upfront_cost,
        annual_savings_year1=annual_savings_year1,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=escalation,
        degradation=degradation,
        simple_payback_years=simple_payback,
        lifetime_savings_nominal=cumulative,
        lifetime_roi=lifetime_roi,
        npv=npv,
        net_advantage_fv=net_advantage_fv,
        yearly=tuple(rows),
    )
