"""Assumption data model for the community-solar POC.

Every number used in the calculation is an *assumption*: a labeled, tagged, optionally-sourced
record. The transparency mechanic (R6-R8) lives here — a default with no source renders as
``unsourced - pending research`` and is never presented as established fact.

As of Phase 4 (2026-05-25) the three load-bearing defaults are ``default (sourced)``, citing the
research repo's calculator brief (../solar-investment-research/wiki/calculator-brief/answers.md).
Values are CMP defaults; a Versant user would edit them. ``allocation_pct`` is a stated modeling
choice, not external fact. The ``unsourced - pending research`` tag remains a first-class state for
any future assumption whose research hasn't landed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

# --- tags (R6) -------------------------------------------------------------
DEFAULT_SOURCED = "default (sourced)"
USER_PROVIDED = "user-provided"
UNSOURCED = "unsourced - pending research"


@dataclass(frozen=True)
class Source:
    title: str
    url: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class Assumption:
    key: str
    label: str
    value: float
    unit: str  # "$/kWh" | "fraction" | "$" | "kWh"
    tag: str
    source: Optional[Source] = None

    def with_user_value(self, value: float) -> "Assumption":
        """Return a copy re-tagged ``user-provided`` (R7, AE2). Editing clears the source."""
        return replace(self, value=value, tag=USER_PROVIDED, source=None)

    @property
    def is_unsourced(self) -> bool:
        return self.tag == UNSOURCED


def default_assumptions() -> dict[str, Assumption]:
    """The POC's shipped defaults. Returns a fresh dict each call (records are immutable)."""
    return {
        "price_per_kwh": Assumption(
            key="price_per_kwh",
            label="All-in residential price per kWh (CMP)",
            value=0.306,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine DOE — Electricity Prices (CMP, effective Jan 1 2026)",
                url="https://www.maine.gov/energy/electricity-prices",
                note="All-in average = $168.41 / 550 kWh. Display-only in the bill-first flow "
                "(it cancels out of the dollar result). Resets every Jan 1. See "
                "solar-investment-research/wiki/utilities/cmp-rates.md.",
            ),
        ),
        "bill_offset_fraction": Assumption(
            key="bill_offset_fraction",
            label="Portion of the bill a community-solar credit offsets (CMP)",
            value=0.82,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine OPA + Maine DOE — credit offsets per-kWh charges, not the fixed charge",
                url="https://www.maine.gov/meopa/electricity/renewable-energy/community_solar",
                note="(bill - fixed) / bill = ($168.41 - $30.21) / $168.41 ~= 0.82 for a typical "
                "550 kWh CMP bill; rises with usage. See "
                "solar-investment-research/wiki/mechanics/maine-bill-anatomy.md.",
            ),
        ),
        "subscription_discount_pct": Assumption(
            key="subscription_discount_pct",
            label="Subscription discount on the credit value you keep as savings",
            value=0.15,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine OPA (10-15%) + Solar Gardens (guaranteed 15% on CMP credits)",
                url="https://www.maine.gov/meopa/electricity/renewable-energy/community_solar",
                note="Discount on the credits, which offset ~82% of the bill, so it nets ~12% off "
                "the total bill (0.15 x 0.82). See "
                "solar-investment-research/wiki/options/community-solar-subscription.md.",
            ),
        ),
        "allocation_pct": Assumption(
            key="allocation_pct",
            label="Share of your usage the subscription is sized to cover",
            value=1.00,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: size the subscription to your usage",
                note="Stated default (100%), not an external citation. Over-subscribing wastes "
                "credits because unused credits expire after 12 months.",
            ),
        ),
    }
