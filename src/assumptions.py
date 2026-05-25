"""Assumption data model for the community-solar POC.

Every number used in the calculation is an *assumption*: a labeled, tagged, optionally-sourced
record. The transparency mechanic (R6-R8) lives here — a default with no source renders as
``unsourced - pending research`` and is never presented as established fact.

Phase 3 ships the three load-bearing defaults as ``unsourced - pending research``. Phase 4
re-tags them ``default (sourced)`` with citations into ../solar-investment-research once the
research brief's answers land. ``allocation_pct`` is a stated modeling choice, not external fact.
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
            label="All-in residential price per kWh",
            value=0.25,
            unit="$/kWh",
            tag=UNSOURCED,  # Phase 4 -> $0.306 (CMP), sourced
        ),
        "bill_offset_fraction": Assumption(
            key="bill_offset_fraction",
            label="Portion of the bill a community-solar credit offsets",
            value=0.60,
            unit="fraction",
            tag=UNSOURCED,  # Phase 4 -> 0.82 (CMP), sourced
        ),
        "subscription_discount_pct": Assumption(
            key="subscription_discount_pct",
            label="Subscription discount on the credit value you keep as savings",
            value=0.12,
            unit="fraction",
            tag=UNSOURCED,  # Phase 4 -> 0.15, sourced
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
