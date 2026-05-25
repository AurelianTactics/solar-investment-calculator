"""Balcony / plug-in solar — pure calculation core (source of truth for this option).

Models Maine plug-in ("balcony") solar, legalized by LD 1730 (2026). The load-bearing difference
from community solar and rooftop: **plug-in solar is NOT net-energy-billing-eligible**, so it saves
money only on the electricity it offsets *in real time* (self-consumption). Exported surplus earns
nothing. Each self-consumed kWh is worth the volumetric (per-kWh) retail rate it avoids — not the
all-in rate, since reducing usage never touches the fixed monthly charge.

Chain (every step returned for display):
  1. capacity        -> annual generation (kWh)
  2. generation      -> self-consumed kWh
  3. self-consumed   -> annual bill savings ($)
  4. costs           -> upfront capital ($)
  5. savings+capital -> the capital-allocation verdict (payback / NPV), via capital.compare

Sourced defaults trace to ../solar-investment-research/wiki/calculator-brief/balcony-answers.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import capital
from solar_calc import Step


@dataclass(frozen=True)
class BalconyResult:
    annual_generation_kwh: float
    self_consumed_kwh: float
    annual_savings: float
    upfront_cost: float
    capital: capital.CapitalResult
    steps: tuple[Step, ...]


def compute(
    capacity_kw: float,
    specific_yield_kwh_per_kw: float,
    self_consumption_fraction: float,
    volumetric_rate_per_kwh: float,
    kit_cost: float,
    electrician_cost: float,
    horizon_years: int = 25,
    opportunity_rate: float = 0.07,
    escalation: float = 0.03,
    degradation: float = 0.005,
) -> BalconyResult:
    if capacity_kw < 0:
        raise ValueError("capacity_kw must be >= 0")
    if not (0.0 <= self_consumption_fraction <= 1.0):
        raise ValueError("self_consumption_fraction must be in [0, 1]")
    if volumetric_rate_per_kwh < 0:
        raise ValueError("volumetric_rate_per_kwh must be >= 0")

    annual_generation = capacity_kw * specific_yield_kwh_per_kw
    self_consumed = annual_generation * self_consumption_fraction
    annual_savings = self_consumed * volumetric_rate_per_kwh
    upfront_cost = kit_cost + electrician_cost

    cap = capital.compare(
        upfront_cost=upfront_cost,
        annual_savings_year1=annual_savings,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=escalation,
        degradation=degradation,
    )

    steps = (
        Step(
            1,
            "Size -> annual generation",
            "generation = capacity_kw x specific_yield_kwh_per_kw",
            ("capacity_kw", "specific_yield_kwh_per_kw"),
            annual_generation,
            "kWh/yr",
        ),
        Step(
            2,
            "Generation -> self-consumed (the rest is exported, uncompensated)",
            "self_consumed = generation x self_consumption_fraction",
            ("self_consumption_fraction",),
            self_consumed,
            "kWh/yr",
        ),
        Step(
            3,
            "Self-consumed -> annual savings (no NEB credit for plug-in)",
            "annual_savings = self_consumed x volumetric_rate_per_kwh",
            ("volumetric_rate_per_kwh",),
            annual_savings,
            "$/yr",
        ),
        Step(
            4,
            "Costs -> upfront capital",
            "upfront = kit_cost + electrician_cost",
            ("kit_cost", "electrician_cost"),
            upfront_cost,
            "$",
        ),
    )

    return BalconyResult(
        annual_generation_kwh=annual_generation,
        self_consumed_kwh=self_consumed,
        annual_savings=annual_savings,
        upfront_cost=upfront_cost,
        capital=cap,
        steps=steps,
    )


def compute_from_assumptions(a: dict) -> BalconyResult:
    """Run ``compute`` from a merged dict of balcony + capital Assumption records."""
    return compute(
        capacity_kw=a["capacity_kw"].value,
        specific_yield_kwh_per_kw=a["specific_yield_kwh_per_kw"].value,
        self_consumption_fraction=a["self_consumption_fraction"].value,
        volumetric_rate_per_kwh=a["volumetric_rate_per_kwh"].value,
        kit_cost=a["kit_cost"].value,
        electrician_cost=a["electrician_cost"].value,
        horizon_years=int(a["horizon_years"].value),
        opportunity_rate=a["opportunity_rate"].value,
        escalation=a["electricity_escalation"].value,
        degradation=a["panel_degradation"].value,
    )
