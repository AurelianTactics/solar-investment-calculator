"""Rooftop solar — pure calculation core (source of truth for this option).

Owned rooftop is the high-capital option. It is net-energy-billing-eligible: generation produces
kWh credits that offset the volumetric (per-kWh) retail charges, but excess credits expire after 12
months, so the value of generation is **capped near annual usage**. The 2026 headline: the 30%
federal residential credit (25D) expired Dec 31, 2025, so a cash/loan buyer's default credit is 0.

Chain (every step returned for display):
  1. size            -> annual generation (kWh)
  2. generation      -> effective kWh credited (capped at usage; surplus expires)
  3. effective       -> annual bill savings ($)
  4. size & $/W      -> gross system cost ($)
  5. federal credit  -> net upfront capital ($)
  then savings + net cost -> capital-allocation verdict via capital.compare.

Sourced defaults trace to ../solar-investment-research/wiki/calculator-brief/rooftop-answers.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import capital
from solar_calc import Step


@dataclass(frozen=True)
class RooftopResult:
    annual_generation_kwh: float
    effective_kwh: float
    annual_savings: float
    gross_cost: float
    upfront_cost: float          # net of the federal credit
    capital: capital.CapitalResult
    steps: tuple[Step, ...]


def compute(
    capacity_kw: float,
    specific_yield_kwh_per_kw: float,
    installed_cost_per_w: float,
    federal_itc_pct: float,
    credit_value_per_kwh: float,
    annual_usage_kwh: float,
    offset_cap_fraction: float = 1.0,
    horizon_years: int = 25,
    opportunity_rate: float = 0.07,
    escalation: float = 0.03,
    degradation: float = 0.005,
) -> RooftopResult:
    if capacity_kw < 0:
        raise ValueError("capacity_kw must be >= 0")
    if not (0.0 <= federal_itc_pct <= 1.0):
        raise ValueError("federal_itc_pct must be in [0, 1]")
    if installed_cost_per_w < 0 or credit_value_per_kwh < 0 or annual_usage_kwh < 0:
        raise ValueError("costs, rates, and usage must be >= 0")

    annual_generation = capacity_kw * specific_yield_kwh_per_kw
    effective_kwh = min(annual_generation, annual_usage_kwh * offset_cap_fraction)
    annual_savings = effective_kwh * credit_value_per_kwh
    gross_cost = capacity_kw * 1000.0 * installed_cost_per_w
    net_cost = gross_cost * (1.0 - federal_itc_pct)

    cap = capital.compare(
        upfront_cost=net_cost,
        annual_savings_year1=annual_savings,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=escalation,
        degradation=degradation,
    )

    steps = (
        Step(1, "Size -> annual generation",
             "generation = capacity_kw x specific_yield_kwh_per_kw",
             ("capacity_kw", "specific_yield_kwh_per_kw"), annual_generation, "kWh/yr"),
        Step(2, "Generation -> effective kWh (NEB; surplus beyond usage expires)",
             "effective = min(generation, annual_usage_kwh x offset_cap_fraction)",
             ("annual_usage_kwh", "offset_cap_fraction"), effective_kwh, "kWh/yr"),
        Step(3, "Effective -> annual savings",
             "annual_savings = effective x credit_value_per_kwh",
             ("credit_value_per_kwh",), annual_savings, "$/yr"),
        Step(4, "Size & price -> gross system cost",
             "gross_cost = capacity_kw x 1000 x installed_cost_per_w",
             ("capacity_kw", "installed_cost_per_w"), gross_cost, "$"),
        Step(5, "Federal credit -> net upfront capital",
             "net_cost = gross_cost x (1 - federal_itc_pct)",
             ("federal_itc_pct",), net_cost, "$"),
    )

    return RooftopResult(
        annual_generation_kwh=annual_generation,
        effective_kwh=effective_kwh,
        annual_savings=annual_savings,
        gross_cost=gross_cost,
        upfront_cost=net_cost,
        capital=cap,
        steps=steps,
    )


def compute_from_assumptions(a: dict) -> RooftopResult:
    return compute(
        capacity_kw=a["capacity_kw"].value,
        specific_yield_kwh_per_kw=a["specific_yield_kwh_per_kw"].value,
        installed_cost_per_w=a["installed_cost_per_w"].value,
        federal_itc_pct=a["federal_itc_pct"].value,
        credit_value_per_kwh=a["credit_value_per_kwh"].value,
        annual_usage_kwh=a["annual_usage_kwh"].value,
        offset_cap_fraction=a["offset_cap_fraction"].value,
        horizon_years=int(a["horizon_years"].value),
        opportunity_rate=a["opportunity_rate"].value,
        escalation=a["electricity_escalation"].value,
        degradation=a["panel_degradation"].value,
    )
