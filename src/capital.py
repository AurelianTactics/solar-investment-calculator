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
from typing import Optional, Sequence


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


def combine(components: Sequence[CapitalResult]) -> CapitalResult:
    """Sum component cashflow streams into one combined verdict (the combo engine).

    Each component keeps its own escalation/degradation/horizon — those already shaped its
    ``yearly`` stream. This helper sums per-year cashflows over the LONGEST horizon (a shorter
    stream simply contributes nothing after its own horizon ends) and derives NPV, payback, and
    the verdict from the summed stream. NPV is additive across streams at one rate; payback is
    NOT — it must come from the combined stream, which is why this helper exists.

    The combined record reports ``escalation=0`` / ``degradation=0`` as placeholders: those are
    single-stream parameters with no meaning for a sum of differently-shaped streams. The real
    escalation/degradation live in each component's own CapitalResult.
    """
    if not components:
        raise ValueError("combine() needs at least one component stream")
    rates = {c.opportunity_rate for c in components}
    if len(rates) > 1:
        raise ValueError("all component streams must share one opportunity_rate")
    opportunity_rate = components[0].opportunity_rate

    horizon_years = max(c.horizon_years for c in components)
    upfront_cost = sum(c.upfront_cost for c in components)

    rows: list[YearRow] = []
    cumulative = 0.0
    npv = -upfront_cost
    fv_savings = 0.0
    for t in range(1, horizon_years + 1):
        savings_t = sum(c.yearly[t - 1].savings for c in components if t <= c.horizon_years)
        cumulative += savings_t
        npv += savings_t / (1 + opportunity_rate) ** t
        fv_savings += savings_t * (1 + opportunity_rate) ** (horizon_years - t)
        rows.append(YearRow(year=t, savings=savings_t, cumulative=cumulative))

    fv_lump = upfront_cost * (1 + opportunity_rate) ** horizon_years
    annual_savings_year1 = rows[0].savings
    simple_payback = (
        upfront_cost / annual_savings_year1 if annual_savings_year1 > 0 else None
    )
    lifetime_roi = (cumulative / upfront_cost) if upfront_cost > 0 else float("inf")

    return CapitalResult(
        upfront_cost=upfront_cost,
        annual_savings_year1=annual_savings_year1,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=0.0,
        degradation=0.0,
        simple_payback_years=simple_payback,
        lifetime_savings_nominal=cumulative,
        lifetime_roi=lifetime_roi,
        npv=npv,
        net_advantage_fv=fv_savings - fv_lump,
        yearly=tuple(rows),
    )
