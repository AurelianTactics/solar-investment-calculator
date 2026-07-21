"""Plug-in / DIY DER battery — pure calculation core (source of truth for this option).

The buy-and-plug cousin of the installed battery: a low-cost battery (consumer power station or
DIY LFP build) the homeowner installs themselves to arbitrage CMP's optional time-of-use delivery rate.

**Scope (2026-07-20): this option models ONE situation — the home already under the time-of-use line.**
The master equation (see ``tou.py``) is

    TOU_savings_vs_flat = U x 0.058120  -  R x 0.367366     (CMP; delivery-only, supply cancels)

and it splits on a single threshold: time-of-use beats flat with no battery at all iff
``on_peak_share < 0.1582``. This module answers only for homes under that line, where the story
is one clean sentence: **enrolling in time-of-use already lowers your bill, and the battery adds arbitrage
on top of it.** The baseline is time-of-use-without-a-battery, so the battery earns exactly the on-peak
penalty it avoids on each kWh it shifts — ``shifted_kwh x penalty``, no netting, no floor.

A home *over* the line is a different question with a different baseline (flat), where the battery
must first claw back the enrollment penalty before time-of-use wins at all, and where the break-even price
falls as the on-peak share worsens. Presenting both through one set of outputs is what made this
option unreadable, so the over-the-line case is **out of scope and backlogged**
(`docs/BACKLOG.md`) rather than half-modeled: ``compute`` raises with a plain-English explanation
instead of quietly returning numbers from a model the caller didn't ask for.

The battery is sized to what it shifts (usable_kwh = shifted / cycles_per_year), so cost follows
the user's own load instead of a fixed unit size. ``on_peak_share`` is the user's own metered
number — the calculator does NOT split load by appliance (out of scope by design).

Chain (every step returned for display):
  1. usage x on-peak share -> on-peak kWh
  2. threshold check -> confirm you're under the line (the precondition for this option)
  3. enrolling with NO battery -> what the rate change alone saves ($/yr; the battery's baseline)
  4. coverage -> shifted on-peak kWh (the residual stays on-peak)
  5. shifted / cycles -> battery size needed (kWh)
  6. size x price -> gross cost ($)
  7. federal credit -> net upfront capital ($; 0% — 25D expired, no TPO for a self-install)
  8. time-of-use arbitrage the battery adds on top of enrolling ($/yr)
  9. break-even installed cost ($/kWh — the shopping number)
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


class OutOfScope(ValueError):
    """The home isn't in the situation this option models (on-peak share over the time-of-use line).

    A ``ValueError`` subclass so every existing surface already handles it: the CLI turns it into
    ``cli.py: error: <message>``, and the web mirror renders it as an inline notice.
    """


@dataclass(frozen=True)
class PluginBatteryResult:
    tou: tou.TouResult
    usable_kwh_needed: float         # battery sized to the shifted load
    gross_cost: float
    upfront_cost: float              # net of any federal credit
    enrollment_only_savings: float   # what enrolling alone saves before the battery ($/yr, > 0)
    tou_arbitrage: float             # what the battery adds on top of enrolling
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

    if not t.under_threshold:
        raise OutOfScope(
            f"plug-in battery models only homes already under the time-of-use on-peak line "
            f"(on_peak_share < {t.threshold_share:.4f}); yours is {on_peak_share:.4f}. Over the "
            f"line, enrolling in time-of-use loses money before the battery even starts, so the battery "
            f"has to rescue the enrollment rather than add to it - a different calculation that "
            f"isn't modeled yet (see docs/BACKLOG.md). Measure your real on-peak share from your "
            f"utility's hourly download, or compare the installed battery option instead."
        )

    usable_kwh_needed = t.shifted_kwh / cycles_per_year
    gross_cost = usable_kwh_needed * installed_cost_per_kwh
    net_cost = gross_cost * (1.0 - federal_itc_pct)
    annual_savings = t.arbitrage + resilience_value_per_year

    # The shopping number: what one kWh of battery earns per year, times the horizon. The sourced
    # per-usable-kWh value nets out the ~10% round-trip charging loss, hence ~$901/kWh at 10 yr
    # rather than 250 x penalty x 10. Buy under it and the battery pays for itself; over it (a
    # $998/kWh Powerwall) it doesn't.
    break_even = value_per_usable_kwh_yr * horizon_years

    cap = capital.compare(
        upfront_cost=net_cost,
        annual_savings_year1=annual_savings,
        horizon_years=horizon_years,
        opportunity_rate=opportunity_rate,
        escalation=0.0,
        degradation=0.0,
    )

    steps = (
        Step(1, "Usage x on-peak share -> on-peak kWh (weekday 5-9 p.m.)",
             "on_peak_kwh = annual_usage_kwh x on_peak_share",
             ("annual_usage_kwh", "on_peak_share"), t.on_peak_kwh, "kWh/yr"),
        Step(2, f"Threshold check -> the most on-peak kWh a home can use and still win on time-of-use "
                f"alone ({t.threshold_share * 100:.1f}% of usage); you're at "
                f"{on_peak_share * 100:.1f}%, under it, so this option applies",
             "on_peak_ceiling = annual_usage_kwh x enrollment_discount_per_kwh "
             "/ residual_penalty_per_kwh",
             ("on_peak_share", "enrollment_discount_per_kwh", "residual_penalty_per_kwh"),
             t.threshold_share * annual_usage_kwh, "kWh/yr"),
        Step(3, "Switching to time-of-use with NO battery -> what the rate change alone saves "
                "(the battery's baseline)",
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
        Step(8, "Time-of-use arbitrage the battery adds on top of enrolling (each shifted kWh dodges the "
                "on-peak penalty)",
             "tou_arbitrage = shifted_kwh x residual_penalty_per_kwh",
             ("residual_coverage", "residual_penalty_per_kwh"), t.arbitrage, "$/yr"),
        Step(9, "Break-even installed cost (the shopping number: pay less than this per kWh and "
                "the battery pays for itself)",
             "break_even = value_per_usable_kwh_yr x horizon_years",
             ("value_per_usable_kwh_yr", "horizon_years"), break_even, "$/kWh"),
        Step(10, "Arbitrage + resilience -> annual value",
             "annual_value = tou_arbitrage + resilience_value_per_year",
             ("resilience_value_per_year",), annual_savings, "$/yr"),
    )

    return PluginBatteryResult(
        tou=t,
        usable_kwh_needed=usable_kwh_needed,
        gross_cost=gross_cost,
        upfront_cost=net_cost,
        enrollment_only_savings=t.enrollment_only_savings,
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
