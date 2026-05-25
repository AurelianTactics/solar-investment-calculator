"""Community-solar savings — the pure calculation core (source of truth).

Models Maine community solar via Net Energy Billing: the subscriber's usage generates kWh bill
credits, and the subscriber buys those credits from the provider at a discount. Net savings is the
discount on the credits the subscription generates, measured against the do-nothing baseline (the
full utility bill). Reports $/yr, $/mo, % off, and $0 capital. No payback/NPV (R5).

The chain (every step is returned for display — R9):
  1. bill -> annual spend
  2. bill -> usage (kWh)
  3. usage -> credits the subscription generates
  4. credits -> savings

In the bill-first flow, ``price_per_kwh`` cancels out of the dollar result (it only sets the
displayed usage); the load-bearing numbers are ``bill_offset_fraction`` and
``subscription_discount_pct``. See the POC plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Step:
    n: int
    label: str
    formula: str
    uses: tuple[str, ...]  # assumption keys this step depends on
    value: float
    unit: str


@dataclass(frozen=True)
class Result:
    annual_spend: float
    monthly_usage_kwh: float
    annual_usage_kwh: float
    credit_value_per_kwh: float
    credits_generated: float
    annual_savings: float
    monthly_savings: float
    pct_off: float
    capital: float
    steps: tuple[Step, ...]


def compute(
    monthly_bill: float,
    price_per_kwh: float,
    bill_offset_fraction: float,
    subscription_discount_pct: float,
    allocation_pct: float = 1.0,
    annual_usage_kwh: Optional[float] = None,
) -> Result:
    if monthly_bill < 0:
        raise ValueError("monthly_bill must be >= 0")
    if price_per_kwh <= 0:
        raise ValueError("price_per_kwh must be > 0")

    annual_spend = monthly_bill * 12.0
    monthly_usage_kwh = monthly_bill / price_per_kwh
    used_annual_usage = (
        annual_usage_kwh if annual_usage_kwh is not None else monthly_usage_kwh * 12.0
    )
    credit_value_per_kwh = price_per_kwh * bill_offset_fraction
    credits_generated = used_annual_usage * allocation_pct * credit_value_per_kwh
    annual_savings = credits_generated * subscription_discount_pct
    monthly_savings = annual_savings / 12.0
    pct_off = (annual_savings / annual_spend) if annual_spend else 0.0

    steps = (
        Step(
            1,
            "Bill -> annual spend (do-nothing baseline)",
            "annual_spend = monthly_bill x 12",
            (),
            annual_spend,
            "$/yr",
        ),
        Step(
            2,
            "Bill -> estimated usage",
            "annual_usage = (monthly_bill / price_per_kwh) x 12",
            ("price_per_kwh",),
            used_annual_usage,
            "kWh/yr",
        ),
        Step(
            3,
            "Usage -> credits the subscription generates",
            "credits = annual_usage x allocation_pct x (price_per_kwh x bill_offset_fraction)",
            ("price_per_kwh", "bill_offset_fraction", "allocation_pct"),
            credits_generated,
            "$/yr",
        ),
        Step(
            4,
            "Credits -> savings (the discount you keep)",
            "annual_savings = credits x subscription_discount_pct",
            ("subscription_discount_pct",),
            annual_savings,
            "$/yr",
        ),
    )

    return Result(
        annual_spend=annual_spend,
        monthly_usage_kwh=monthly_usage_kwh,
        annual_usage_kwh=used_annual_usage,
        credit_value_per_kwh=credit_value_per_kwh,
        credits_generated=credits_generated,
        annual_savings=annual_savings,
        monthly_savings=monthly_savings,
        pct_off=pct_off,
        capital=0.0,
        steps=steps,
    )


def compute_from_assumptions(assumptions: dict, annual_usage_kwh: Optional[float] = None) -> Result:
    """Convenience: run ``compute`` from a dict of Assumption records (see assumptions.py)."""
    return compute(
        monthly_bill=assumptions["monthly_bill"].value,
        price_per_kwh=assumptions["price_per_kwh"].value,
        bill_offset_fraction=assumptions["bill_offset_fraction"].value,
        subscription_discount_pct=assumptions["subscription_discount_pct"].value,
        allocation_pct=assumptions["allocation_pct"].value,
        annual_usage_kwh=annual_usage_kwh,
    )
