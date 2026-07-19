"""Home battery storage — pure calculation core (source of truth for this option).

The honest option: a battery does NOT pay for itself on Maine electricity economics. On the
default flat rate (CMP Rate A: delivery AND supply both flat) there is no intraday spread, the
owner-bought federal credit is gone (25D expired Dec 31, 2025), modeled bill savings are ~$0 and
the NPV is strongly negative. Its real value is **resilience** (backup power), modeled as a
separate, user-set ``resilience_value_per_year`` kept apart from bill savings so the
pure-economics verdict stays honest.

The one real bill-savings lever is an **optional TOU delivery rate** (CMP Rate TOU, eff.
2026-07-01; Versant "Home Eco" A-4/A-4M), modeled as the off-by-default ``tou_enrolled`` mode:
the installed battery faces the identical three-case math as the plug-in DER battery (see
``tou.py``) — it's just a more expensive device, so it fails more break-evens. Off by default;
a few hundred $/yr at most; it does not flip the resilience-not-ROI verdict.

Chain (every step returned for display):
  1. capacity & price -> gross system cost ($)
  2. federal credit   -> net upfront capital ($)
  3. TOU mode         -> annual arbitrage value ($/yr; 0 unless tou_enrolled)
  4. bill savings + arbitrage + resilience -> annual value ($)
  then annual value + net cost -> capital-allocation verdict via capital.compare over the
  expected ~13-yr service life (NOT the 10-yr warranty) with ~3%/yr LFP capacity fade.

Sourced defaults trace to ../solar-investment-research/wiki/calculator-brief/battery-answers.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import capital
import tou
from solar_calc import Step


@dataclass(frozen=True)
class BatteryResult:
    gross_cost: float
    upfront_cost: float          # net of any federal credit
    annual_bill_savings: float
    tou_arbitrage: float         # 0 unless tou_enrolled
    resilience_value_per_year: float
    annual_savings: float        # bill savings + arbitrage + resilience (fed to the capital engine)
    tou: Optional[tou.TouResult]  # the case breakdown when enrolled, else None
    capital: capital.CapitalResult
    steps: tuple[Step, ...]


def compute(
    usable_kwh: float,
    installed_cost_per_kwh: float,
    federal_itc_pct: float,
    annual_bill_savings: float,
    resilience_value_per_year: float,
    horizon_years: int = 13,
    opportunity_rate: float = 0.07,
    annual_degradation: float = 0.03,
    tou_enrolled: bool = False,
    annual_usage_kwh: float = 0.0,
    on_peak_share: float = 0.0,
    residual_coverage: float = 0.0,
    enrollment_discount_per_kwh: float = 0.0,
    residual_penalty_per_kwh: float = 0.367366,
) -> BatteryResult:
    if usable_kwh < 0 or installed_cost_per_kwh < 0:
        raise ValueError("capacity and cost must be >= 0")
    if not (0.0 <= federal_itc_pct <= 1.0):
        raise ValueError("federal_itc_pct must be in [0, 1]")

    gross_cost = usable_kwh * installed_cost_per_kwh
    net_cost = gross_cost * (1.0 - federal_itc_pct)

    tou_result: Optional[tou.TouResult] = None
    if tou_enrolled:
        tou_result = tou.evaluate(
            annual_usage_kwh=annual_usage_kwh,
            on_peak_share=on_peak_share,
            residual_coverage=residual_coverage,
            enrollment_discount_per_kwh=enrollment_discount_per_kwh,
            residual_penalty_per_kwh=residual_penalty_per_kwh,
        )
    tou_arbitrage = tou_result.arbitrage if tou_result else 0.0
    annual_savings = annual_bill_savings + tou_arbitrage + resilience_value_per_year

    # Throughput value doesn't ride electricity-price escalation in this simple model, but LFP
    # capacity fades ~1-4%/yr (default 3%), trimming each later year's value.
    cap = capital.compare(
        upfront_cost=net_cost,
        annual_savings_year1=annual_savings,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=0.0,
        degradation=annual_degradation,
    )

    if tou_result:
        tou_formula = (
            "case 2 (gravy): arb = shifted_kwh x residual_penalty_per_kwh"
            if tou_result.case == 2
            else "case 3 (rescue): arb = max(0, usage x discount - residual_kwh x penalty)"
        )
        tou_label = (f"TOU mode ON -> Case {tou_result.case} arbitrage "
                     f"(threshold: on-peak share < {tou_result.threshold_share:.4f})")
    else:
        tou_formula = "tou_arbitrage = 0 (tou_enrolled = 0: staying on the flat rate)"
        tou_label = "TOU mode off (default) -> no arbitrage on a flat rate"

    steps = (
        Step(1, "Capacity & price -> gross system cost",
             "gross_cost = usable_kwh x installed_cost_per_kwh",
             ("usable_kwh", "installed_cost_per_kwh"), gross_cost, "$"),
        Step(2, "Federal credit -> net upfront capital",
             "net_cost = gross_cost x (1 - federal_itc_pct)",
             ("federal_itc_pct",), net_cost, "$"),
        Step(3, tou_label, tou_formula,
             ("tou_enrolled", "annual_usage_kwh", "on_peak_share", "residual_coverage",
              "enrollment_discount_per_kwh", "residual_penalty_per_kwh"),
             tou_arbitrage, "$/yr"),
        Step(4, "Bill savings + TOU arbitrage + resilience -> annual value",
             "annual_value = annual_bill_savings + tou_arbitrage + resilience_value_per_year",
             ("annual_bill_savings", "resilience_value_per_year"), annual_savings, "$/yr"),
    )

    return BatteryResult(
        gross_cost=gross_cost,
        upfront_cost=net_cost,
        annual_bill_savings=annual_bill_savings,
        tou_arbitrage=tou_arbitrage,
        resilience_value_per_year=resilience_value_per_year,
        annual_savings=annual_savings,
        tou=tou_result,
        capital=cap,
        steps=steps,
    )


def compute_from_assumptions(a: dict) -> BatteryResult:
    return compute(
        usable_kwh=a["usable_kwh"].value,
        installed_cost_per_kwh=a["installed_cost_per_kwh"].value,
        federal_itc_pct=a["federal_itc_pct"].value,
        annual_bill_savings=a["annual_bill_savings"].value,
        resilience_value_per_year=a["resilience_value_per_year"].value,
        horizon_years=int(a["horizon_years"].value),
        opportunity_rate=a["opportunity_rate"].value,
        annual_degradation=a["annual_degradation"].value,
        tou_enrolled=bool(a["tou_enrolled"].value),
        annual_usage_kwh=a["annual_usage_kwh"].value,
        on_peak_share=a["on_peak_share"].value,
        residual_coverage=a["residual_coverage"].value,
        enrollment_discount_per_kwh=a["enrollment_discount_per_kwh"].value,
        residual_penalty_per_kwh=a["residual_penalty_per_kwh"].value,
    )
