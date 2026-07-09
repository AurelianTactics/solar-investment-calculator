"""Combined options — one mechanism behind battery+rooftop and battery+balcony.

A combo is stream-wise ADDITIVE: each component is computed by its own existing module with its
own escalation/degradation/horizon (battery: 10 yr, flat; PV: 25 yr, escalating/degrading), then
``capital.combine`` sums the per-year cashflows over the longer horizon and derives the combined
NPV/payback/verdict from the summed stream. Nothing about a component's own economics changes by
being in a combo.

Chain (every step returned for display):
  1-2. PV component      -> year-1 savings, upfront capital (its own module's chain)
  3-4. battery component -> year-1 value, upfront capital (its own module's chain)
  5.   interaction       -> extra annual value while the battery lives (default 0, unsourced)
  6.   components        -> combined upfront capital
  7.   components        -> combined year-1 savings
  8.   streams           -> combined horizon (battery stream ends early; PV continues)

The interaction assumption (``battery_pv_interaction_value_per_year``) is the honest slot for
pairing economics research that has NOT landed (e.g. battery uplift to PV self-consumption). It
defaults to 0 — the combo is exactly additive until research says otherwise — and rides the
battery stream (flat $/yr over the battery's horizon only).

Assumption namespacing: PV and shared capital keys stay bare (``capacity_kw``,
``horizon_years``...); battery keys carry a ``battery_`` prefix (``battery_federal_itc_pct``,
``battery_horizon_years``...) so colliding keys are resolved per-component, never shared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import balcony
import battery
import capital
import rooftop
from solar_calc import Step

BATTERY_PREFIX = "battery_"
INTERACTION_KEY = "battery_pv_interaction_value_per_year"

# battery.compute_from_assumptions expects these bare keys; in a combo they arrive prefixed.
_BATTERY_KEYS = (
    "usable_kwh", "installed_cost_per_kwh", "federal_itc_pct",
    "annual_bill_savings", "resilience_value_per_year", "horizon_years",
)

# Per-PV-option display metadata: which assumption keys each summary step traces to.
_PV_CONFIGS = {
    "rooftop": {
        "module": rooftop,
        "label": "Rooftop",
        "savings_uses": ("capacity_kw", "specific_yield_kwh_per_kw", "credit_value_per_kwh",
                         "annual_usage_kwh", "offset_cap_fraction"),
        "upfront_uses": ("capacity_kw", "installed_cost_per_w", "federal_itc_pct"),
    },
    "balcony": {
        "module": balcony,
        "label": "Balcony",
        "savings_uses": ("capacity_kw", "specific_yield_kwh_per_kw", "self_consumption_fraction",
                         "volumetric_rate_per_kwh"),
        "upfront_uses": ("kit_cost", "electrician_cost"),
    },
}


@dataclass(frozen=True)
class ComboResult:
    pv_option: str
    pv: Union[rooftop.RooftopResult, balcony.BalconyResult]
    battery: battery.BatteryResult
    interaction_value_per_year: float
    annual_savings: float        # combined year-1 (pv + battery + interaction)
    upfront_cost: float          # combined (pv + battery)
    capital: capital.CapitalResult
    steps: tuple[Step, ...]


def compute(pv_option: str, pv_result, battery_result: battery.BatteryResult,
            interaction_value_per_year: float = 0.0) -> ComboResult:
    """Combine already-computed component results into one additive verdict."""
    if pv_option not in _PV_CONFIGS:
        raise ValueError(f"unknown PV option for a combo: {pv_option!r}")
    cfg = _PV_CONFIGS[pv_option]

    # The interaction uplift rides the battery stream: flat $/yr while the battery lives.
    interaction_stream = capital.compare(
        upfront_cost=0.0,
        annual_savings_year1=interaction_value_per_year,
        horizon_years=battery_result.capital.horizon_years,
        opportunity_rate=battery_result.capital.opportunity_rate,
        escalation=0.0,
        degradation=0.0,
    )
    combined = capital.combine(
        [pv_result.capital, battery_result.capital, interaction_stream]
    )

    upfront = pv_result.upfront_cost + battery_result.upfront_cost
    year1 = pv_result.annual_savings + battery_result.annual_savings + interaction_value_per_year
    label = cfg["label"]

    steps = (
        Step(1, f"{label} component -> year-1 savings (its own chain; see --option {pv_option})",
             f"pv_savings = {pv_option} chain",
             cfg["savings_uses"], pv_result.annual_savings, "$/yr"),
        Step(2, f"{label} component -> upfront capital",
             f"pv_upfront = {pv_option} chain",
             cfg["upfront_uses"], pv_result.upfront_cost, "$"),
        Step(3, "Battery component -> year-1 value (its own chain; see --option battery)",
             "battery_value = battery chain",
             ("battery_annual_bill_savings", "battery_resilience_value_per_year"),
             battery_result.annual_savings, "$/yr"),
        Step(4, "Battery component -> upfront capital",
             "battery_upfront = battery chain",
             ("battery_usable_kwh", "battery_installed_cost_per_kwh", "battery_federal_itc_pct"),
             battery_result.upfront_cost, "$"),
        Step(5, "Interaction -> extra annual value while the battery lives (default 0)",
             "interaction = battery_pv_interaction_value_per_year (flat, battery years only)",
             (INTERACTION_KEY,), interaction_value_per_year, "$/yr"),
        Step(6, "Components -> combined upfront capital",
             "upfront = pv_upfront + battery_upfront",
             cfg["upfront_uses"] + ("battery_usable_kwh", "battery_installed_cost_per_kwh"),
             upfront, "$"),
        Step(7, "Components -> combined year-1 savings",
             "year1 = pv_savings + battery_value + interaction",
             (INTERACTION_KEY,), year1, "$/yr"),
        Step(8, "Streams -> combined horizon (battery cashflows stop at its own horizon)",
             "horizon = max(horizon_years, battery_horizon_years); per-year sums",
             ("horizon_years", "battery_horizon_years"),
             float(combined.horizon_years), "years"),
    )

    return ComboResult(
        pv_option=pv_option,
        pv=pv_result,
        battery=battery_result,
        interaction_value_per_year=interaction_value_per_year,
        annual_savings=year1,
        upfront_cost=upfront,
        capital=combined,
        steps=steps,
    )


def battery_view(a: dict) -> dict:
    """Project a combo assumption dict onto the bare keys battery.compute_from_assumptions expects."""
    view = {key: a[BATTERY_PREFIX + key] for key in _BATTERY_KEYS}
    view["opportunity_rate"] = a["opportunity_rate"]
    return view


def compute_from_assumptions(a: dict, pv_option: str) -> ComboResult:
    """Run both components from a merged combo assumption dict, then combine."""
    pv_result = _PV_CONFIGS[pv_option]["module"].compute_from_assumptions(a)
    battery_result = battery.compute_from_assumptions(battery_view(a))
    return compute(pv_option, pv_result, battery_result, a[INTERACTION_KEY].value)
