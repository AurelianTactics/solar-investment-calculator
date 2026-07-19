"""Plug-in / DIY DER battery — pure calculation core (source of truth for this option).

The buy-and-plug cousin of the installed battery: a low-cost battery (consumer power station or
DIY LFP build) the homeowner installs themselves to arbitrage CMP's optional TOU delivery rate.
The economics reduce to **one master equation and a three-way branch** (see ``tou.py``) — NOT a
capture-fraction multiply, which double-counts the enrollment discount against the penalty:

    TOU_savings_vs_flat = U x 0.058120  -  R x 0.367366     (CMP; delivery-only, supply cancels)

  Case 1 (threshold, no battery): TOU beats flat iff on_peak_share < 0.1582 — free money by
         just enrolling; shown so a user who's already under the line knows no hardware is needed.
  Case 2 (under the line, "gravy"): each shifted kWh is a clean $0.367366; break-even installed
         cost ~ $901/kWh over 10 yr — a cheap plug-in unit clears it easily.
  Case 3 (over the line, "rescue"): baseline is FLAT ($0); the battery must claw back the
         penalty before TOU beats flat, and the break-even $/kWh FALLS as on-peak share worsens
         ($908 at 16% -> $581 at 25% -> $363 at 40% for a 10,000 kWh home) — because the battery
         you need grows while the payoff stays capped at U x 0.058120. The cruel irony: the
         high-on-peak load that puts you here is usually winter electric heat, exactly what a
         small plug-in can't cover (the ``residual_coverage`` dial, unsourced).

The battery is sized to what it shifts (usable_kwh = shifted / cycles_per_year), so cost follows
the user's own load instead of a fixed unit size. ``on_peak_share`` is the user's own metered
number — the calculator does NOT split load by appliance (out of scope by design).

Chain (every step returned for display):
  1. usage x on-peak share -> on-peak kWh
  2. threshold check -> which case you're in (2 or 3)
  3. enrolling with NO battery -> the Case-1 answer ($/yr; > 0 means enrolling alone saves)
  4. coverage -> shifted on-peak kWh (the residual stays on-peak)
  5. shifted / cycles -> battery size needed (kWh)
  6. size x price -> gross cost ($)
  7. federal credit -> net upfront capital ($; 0% — 25D expired, no TPO for a self-install)
  8. TOU arbitrage for your case ($/yr)
  9. break-even installed cost for this case ($/kWh — the shopping number)
 10. arbitrage + resilience -> annual value ($/yr)
  then annual value + net cost -> capital-allocation verdict via capital.compare (10-yr life).

Sourced values trace to
../solar-investment-research/wiki/calculator-brief/plugin-battery-answers.md; the two honest
unknowns (``installed_cost_per_kwh``, ``residual_coverage``) ship tagged unsourced.
"""

from __future__ import annotations

from dataclasses import dataclass

import capital
import tou
from solar_calc import Step


@dataclass(frozen=True)
class PluginBatteryResult:
    tou: tou.TouResult
    case: int                        # 2 (gravy) or 3 (rescue)
    usable_kwh_needed: float         # battery sized to the shifted load
    gross_cost: float
    upfront_cost: float              # net of any federal credit
    tou_arbitrage: float
    resilience_value_per_year: float
    annual_savings: float            # arbitrage + resilience (fed to the capital engine)
    break_even_cost_per_kwh: float   # installed $/kWh at which the battery just pays for itself
    capital: capital.CapitalResult
    steps: tuple[Step, ...]


def compute(
    annual_usage_kwh: float,
    on_peak_share: float,
    residual_coverage: float,
    installed_cost_per_kwh: float,
    cycles_per_year: float,
    enrollment_discount_per_kwh: float,
    residual_penalty_per_kwh: float,
    value_per_usable_kwh_yr: float,
    federal_itc_pct: float,
    resilience_value_per_year: float,
    horizon_years: int = 10,
    opportunity_rate: float = 0.07,
) -> PluginBatteryResult:
    if installed_cost_per_kwh < 0:
        raise ValueError("installed_cost_per_kwh must be >= 0")
    if cycles_per_year <= 0:
        raise ValueError("cycles_per_year must be > 0")
    if not (0.0 <= federal_itc_pct <= 1.0):
        raise ValueError("federal_itc_pct must be in [0, 1]")

    t = tou.evaluate(
        annual_usage_kwh=annual_usage_kwh,
        on_peak_share=on_peak_share,
        residual_coverage=residual_coverage,
        enrollment_discount_per_kwh=enrollment_discount_per_kwh,
        residual_penalty_per_kwh=residual_penalty_per_kwh,
    )

    usable_kwh_needed = t.shifted_kwh / cycles_per_year
    gross_cost = usable_kwh_needed * installed_cost_per_kwh
    net_cost = gross_cost * (1.0 - federal_itc_pct)
    annual_savings = t.arbitrage + resilience_value_per_year

    # The shopping number. Case 2 uses the sourced per-usable-kWh value (which also nets out
    # ~10% round-trip charging losses, hence ~$901/kWh at 10 yr rather than 250 x penalty x 10);
    # Case 3 derives it from this home's own arbitrage and battery size (reproducing the brief's
    # depth table: $908 at 16% on-peak -> $363 at 40%, coverage 1.0, 10,000 kWh home).
    if t.case == 2:
        break_even = value_per_usable_kwh_yr * horizon_years
    else:
        break_even = (t.arbitrage * horizon_years / usable_kwh_needed
                      if usable_kwh_needed > 0 else 0.0)

    cap = capital.compare(
        upfront_cost=net_cost,
        annual_savings_year1=annual_savings,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=0.0,
        degradation=0.0,
    )

    arb_formula = (
        "case 2 (gravy): arb = shifted_kwh x residual_penalty_per_kwh (baseline: TOU already wins)"
        if t.case == 2
        else "case 3 (rescue): arb = max(0, usage x discount - residual_kwh x penalty) (baseline: flat)"
    )
    be_formula = (
        "break_even = value_per_usable_kwh_yr x horizon_years"
        if t.case == 2
        else "break_even = tou_arbitrage x horizon_years / usable_kwh_needed"
    )

    steps = (
        Step(1, "Usage x on-peak share -> on-peak kWh (weekday 5-9 p.m.)",
             "on_peak_kwh = annual_usage_kwh x on_peak_share",
             ("annual_usage_kwh", "on_peak_share"), t.on_peak_kwh, "kWh/yr"),
        Step(2, "Threshold check -> which TOU case you're in "
                f"(under {t.threshold_share:.4f} on-peak = case 2 gravy; over = case 3 rescue)",
             "case = 2 if on_peak_share < enrollment_discount / residual_penalty else 3",
             ("on_peak_share", "enrollment_discount_per_kwh", "residual_penalty_per_kwh"),
             float(t.case), "case"),
        Step(3, "Enrolling with NO battery (the Case-1 answer; > 0 means free money by enrolling)",
             "enrollment_only = usage x enrollment_discount - on_peak_kwh x residual_penalty",
             ("annual_usage_kwh", "on_peak_share", "enrollment_discount_per_kwh",
              "residual_penalty_per_kwh"), t.enrollment_only_savings, "$/yr"),
        Step(4, "Battery coverage -> shifted on-peak kWh (the rest stays on-peak)",
             "shifted_kwh = residual_coverage x on_peak_kwh",
             ("residual_coverage",), t.shifted_kwh, "kWh/yr"),
        Step(5, "Shifted load / cycles -> battery size needed",
             "usable_kwh_needed = shifted_kwh / cycles_per_year",
             ("cycles_per_year",), usable_kwh_needed, "kWh"),
        Step(6, "Size x price -> gross cost",
             "gross_cost = usable_kwh_needed x installed_cost_per_kwh",
             ("installed_cost_per_kwh",), gross_cost, "$"),
        Step(7, "Federal credit -> net upfront capital (25D expired; no TPO for a self-install)",
             "net_cost = gross_cost x (1 - federal_itc_pct)",
             ("federal_itc_pct",), net_cost, "$"),
        Step(8, f"TOU arbitrage for your case (case {t.case})",
             arb_formula, ("annual_usage_kwh", "on_peak_share", "residual_coverage",
                           "enrollment_discount_per_kwh", "residual_penalty_per_kwh"),
             t.arbitrage, "$/yr"),
        Step(9, "Break-even installed cost for this case (the shopping number)",
             be_formula, ("value_per_usable_kwh_yr", "horizon_years"),
             break_even, "$/kWh"),
        Step(10, "Arbitrage + resilience -> annual value",
             "annual_value = tou_arbitrage + resilience_value_per_year",
             ("resilience_value_per_year",), annual_savings, "$/yr"),
    )

    return PluginBatteryResult(
        tou=t,
        case=t.case,
        usable_kwh_needed=usable_kwh_needed,
        gross_cost=gross_cost,
        upfront_cost=net_cost,
        tou_arbitrage=t.arbitrage,
        resilience_value_per_year=resilience_value_per_year,
        annual_savings=annual_savings,
        break_even_cost_per_kwh=break_even,
        capital=cap,
        steps=steps,
    )


def compute_from_assumptions(a: dict) -> PluginBatteryResult:
    return compute(
        annual_usage_kwh=a["annual_usage_kwh"].value,
        on_peak_share=a["on_peak_share"].value,
        residual_coverage=a["residual_coverage"].value,
        installed_cost_per_kwh=a["installed_cost_per_kwh"].value,
        cycles_per_year=a["cycles_per_year"].value,
        enrollment_discount_per_kwh=a["enrollment_discount_per_kwh"].value,
        residual_penalty_per_kwh=a["residual_penalty_per_kwh"].value,
        value_per_usable_kwh_yr=a["value_per_usable_kwh_yr"].value,
        federal_itc_pct=a["federal_itc_pct"].value,
        resilience_value_per_year=a["resilience_value_per_year"].value,
        horizon_years=int(a["horizon_years"].value),
        opportunity_rate=a["opportunity_rate"].value,
    )
