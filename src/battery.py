"""Home battery storage — pure calculation core (source of truth for this option).

The honest option: a battery does NOT pay for itself on Maine electricity economics. With no strong
residential arbitrage and no federal credit (the 25D battery credit expired Dec 31, 2025), modeled
bill savings are ~$0 and the NPV is strongly negative. Its real value is **resilience** (backup
power), modeled as a separate, user-set ``resilience_value_per_year`` kept apart from bill savings
so the pure-economics verdict stays honest.

Chain (every step returned for display):
  1. capacity & price -> gross system cost ($)
  2. federal credit   -> net upfront capital ($)
  3. bill savings + resilience -> annual value ($)
  then annual value + net cost -> capital-allocation verdict (10-yr horizon) via capital.compare.

Sourced defaults trace to ../solar-investment-research/wiki/calculator-brief/battery-answers.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import capital
from solar_calc import Step


@dataclass(frozen=True)
class BatteryResult:
    gross_cost: float
    upfront_cost: float          # net of any federal credit
    annual_bill_savings: float
    resilience_value_per_year: float
    annual_savings: float        # bill savings + resilience (the value fed to the capital engine)
    capital: capital.CapitalResult
    steps: tuple[Step, ...]


def compute(
    usable_kwh: float,
    installed_cost_per_kwh: float,
    federal_itc_pct: float,
    annual_bill_savings: float,
    resilience_value_per_year: float,
    horizon_years: int = 10,
    opportunity_rate: float = 0.07,
) -> BatteryResult:
    if usable_kwh < 0 or installed_cost_per_kwh < 0:
        raise ValueError("capacity and cost must be >= 0")
    if not (0.0 <= federal_itc_pct <= 1.0):
        raise ValueError("federal_itc_pct must be in [0, 1]")

    gross_cost = usable_kwh * installed_cost_per_kwh
    net_cost = gross_cost * (1.0 - federal_itc_pct)
    annual_savings = annual_bill_savings + resilience_value_per_year

    # A battery's throughput value doesn't escalate/degrade like PV generation in this simple model.
    cap = capital.compare(
        upfront_cost=net_cost,
        annual_savings_year1=annual_savings,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=0.0,
        degradation=0.0,
    )

    steps = (
        Step(1, "Capacity & price -> gross system cost",
             "gross_cost = usable_kwh x installed_cost_per_kwh",
             ("usable_kwh", "installed_cost_per_kwh"), gross_cost, "$"),
        Step(2, "Federal credit -> net upfront capital",
             "net_cost = gross_cost x (1 - federal_itc_pct)",
             ("federal_itc_pct",), net_cost, "$"),
        Step(3, "Bill savings + resilience -> annual value",
             "annual_value = annual_bill_savings + resilience_value_per_year",
             ("annual_bill_savings", "resilience_value_per_year"), annual_savings, "$/yr"),
    )

    return BatteryResult(
        gross_cost=gross_cost,
        upfront_cost=net_cost,
        annual_bill_savings=annual_bill_savings,
        resilience_value_per_year=resilience_value_per_year,
        annual_savings=annual_savings,
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
    )
