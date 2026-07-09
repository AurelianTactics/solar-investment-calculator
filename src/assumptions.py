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


def capital_assumptions() -> dict[str, Assumption]:
    """Shared financial assumptions for the capital-bearing options (balcony/rooftop/battery).

    These drive ``capital.compare``. ``opportunity_rate`` is the crux of STRATEGY.md's
    capital-allocation comparison; all four are stated modeling choices the user should tune, not
    external citations.
    """
    return {
        "opportunity_rate": Assumption(
            key="opportunity_rate",
            label="Opportunity cost — return if you invested the cash instead",
            value=0.07,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: long-run diversified-market return",
                note="Stated default (7%/yr nominal), not a citation. This is the hurdle solar must "
                "beat: NPV > 0 means buying solar beats investing this capital at this rate.",
            ),
        ),
        "electricity_escalation": Assumption(
            key="electricity_escalation",
            label="Annual electricity-price escalation",
            value=0.03,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: conservative long-run electricity inflation",
                note="Stated default (3%/yr). Maine's recent rises were far steeper (NRCM cites a "
                "68% CMP increase over five years); 3% is deliberately conservative — raise it to "
                "stress-test.",
            ),
        ),
        "panel_degradation": Assumption(
            key="panel_degradation",
            label="Annual panel output degradation",
            value=0.005,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: industry-standard ~0.5%/yr degradation",
                note="Stated default (0.5%/yr). Applies to PV generation (balcony/rooftop), not to "
                "battery throughput.",
            ),
        ),
        "horizon_years": Assumption(
            key="horizon_years",
            label="Analysis horizon (system life)",
            value=25.0,
            unit="years",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: 25-year PV horizon",
                note="Stated default (25 yr), the common panel-warranty life. Batteries typically "
                "warrant ~10 yr — shorten the horizon when modeling battery-only economics.",
            ),
        ),
    }


def balcony_assumptions() -> dict[str, Assumption]:
    """Balcony / plug-in solar defaults. Sourced to the research repo's balcony brief
    (../solar-investment-research/wiki/calculator-brief/balcony-answers.md).

    Savings mechanic: plug-in solar is NOT net-energy-billing-eligible (Maine LD 1730), so it saves
    only on electricity self-consumed in real time, valued at the volumetric retail rate.
    """
    return {
        "capacity_kw": Assumption(
            key="capacity_kw",
            label="System size (plug-in)",
            value=1.2,
            unit="kW",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine LD 1730 — maximum permitted plug-in size is 1,200 W",
                url="https://mainemorningstar.com/2026/04/03/maine-renters-may-soon-be-able-to-access-solar-power-after-passage-of-plug-in-bill/",
                note="1.2 kW is the legal max; see balcony-answers.md.",
            ),
        ),
        "specific_yield_kwh_per_kw": Assumption(
            key="specific_yield_kwh_per_kw",
            label="Annual production per kW (Maine)",
            value=1200.0,
            unit="kWh/kW/yr",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine PV yield (~1,200 kWh/kW/yr), consistent with the OPA $388/yr anchor",
                url="https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/",
                note="Implied by OPA $388/yr ÷ $0.27/kWh ÷ 1.2 kW. See balcony-answers.md.",
            ),
        ),
        "self_consumption_fraction": Assumption(
            key="self_consumption_fraction",
            label="Share of generation used on-site (rest is exported, uncompensated)",
            value=1.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: the OPA $388/yr anchor implies near-full self-consumption",
                note="Stated default (100%). Plug-in solar earns NOTHING for exported surplus (not "
                "NEB-eligible), so lower this if a 1.2 kW kit out-produces your daytime baseload.",
            ),
        ),
        "volumetric_rate_per_kwh": Assumption(
            key="volumetric_rate_per_kwh",
            label="Volumetric retail rate a self-consumed kWh avoids (CMP)",
            value=0.27,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine DOE — CMP per-kWh (volumetric) charges",
                url="https://www.maine.gov/energy/electricity-prices",
                note="Self-consumption avoids per-kWh charges, not the fixed charge. See "
                "solar-investment-research/wiki/utilities/cmp-rates.md.",
            ),
        ),
        "kit_cost": Assumption(
            key="kit_cost",
            label="Plug-in kit cost",
            value=1200.0,
            unit="$",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="NRCM — U.S. plug-in kits ~$1,000-1,500 today (falling)",
                url="https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/",
                note="Midpoint of the $1,000-1,500 range; an 800 W Ikea kit is ~$500 in Germany.",
            ),
        ),
        "electrician_cost": Assumption(
            key="electrician_cost",
            label="Electrician install cost (required for kits over 420 W)",
            value=300.0,
            unit="$",
            tag=UNSOURCED,
            source=None,
        ),
    }


def rooftop_assumptions() -> dict[str, Assumption]:
    """Rooftop solar defaults. Sourced to
    ../solar-investment-research/wiki/calculator-brief/rooftop-answers.md.

    Owned rooftop is net-energy-billing-eligible: kWh credits offset volumetric charges, but excess
    credits expire after 12 months, so value caps near annual usage. The headline 2026 fact: the
    30% federal credit (25D) expired Dec 31, 2025 — a cash/loan buyer gets $0, so the default ITC
    is 0, not 0.30.
    """
    return {
        "capacity_kw": Assumption(
            key="capacity_kw",
            label="System size (rooftop)",
            value=5.5,
            unit="kW",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Sized to a typical CMP home (~6,600 kWh/yr at ~1,200 kWh/kW)",
                note="Editable; size to your own usage. Oversizing wastes credits (they expire at "
                "12 months). See rooftop-answers.md.",
            ),
        ),
        "specific_yield_kwh_per_kw": Assumption(
            key="specific_yield_kwh_per_kw",
            label="Annual production per kW (Maine)",
            value=1200.0,
            unit="kWh/kW/yr",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine PV yield (~1,200 kWh/kW/yr)",
                url="https://www.energysage.com/local-data/solar-panel-cost/me/",
                note="Standard Maine production figure. See rooftop-answers.md.",
            ),
        ),
        "installed_cost_per_w": Assumption(
            key="installed_cost_per_w",
            label="Installed cost per watt (Maine)",
            value=2.95,
            unit="$/W",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="EnergySage — Maine average $2.95/W (May 2026), before incentives",
                url="https://www.energysage.com/local-data/solar-panel-cost/me/",
                note="~$33,198 for an average 11.26 kW system; scales ~linearly with size.",
            ),
        ),
        "federal_itc_pct": Assumption(
            key="federal_itc_pct",
            label="Federal tax credit on system cost",
            value=0.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Federal 25D residential solar credit EXPIRED Dec 31, 2025 (was 30%)",
                url="https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
                note="A 2026 cash/loan buyer gets $0 federal credit. Set to 0.30 only if you "
                "installed by the 2025 deadline. See rooftop-answers.md.",
            ),
        ),
        "credit_value_per_kwh": Assumption(
            key="credit_value_per_kwh",
            label="NEB credit value per kWh (volumetric, CMP)",
            value=0.27,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Maine DOE — CMP per-kWh (volumetric) charge a NEB credit offsets",
                url="https://www.maine.gov/energy/electricity-prices",
                note="Credits offset per-kWh charges, not the fixed charge. See "
                "solar-investment-research/wiki/utilities/cmp-rates.md.",
            ),
        ),
        "annual_usage_kwh": Assumption(
            key="annual_usage_kwh",
            label="Your annual electricity usage",
            value=6600.0,
            unit="kWh",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Typical CMP residential usage (~550 kWh/month)",
                note="Caps the value of generation (NEB credits beyond usage expire). Edit to your "
                "own annual kWh.",
            ),
        ),
        "offset_cap_fraction": Assumption(
            key="offset_cap_fraction",
            label="Share of usage that generation is credited against",
            value=1.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: value generation up to usage only",
                note="Stated default (100%). NEB credits bank but expire after 12 months, so "
                "generation beyond annual usage earns ~nothing.",
            ),
        ),
    }


def battery_assumptions() -> dict[str, Assumption]:
    """Home battery defaults. Sourced to
    ../solar-investment-research/wiki/calculator-brief/battery-answers.md.

    The honest framing: a battery doesn't pay for itself on Maine bill economics (no strong
    arbitrage, no federal credit since 25D expired). Its value is resilience — modeled as a separate,
    user-set ``resilience_value_per_year`` kept apart from bill savings so the pure-economics verdict
    stays honest. Note ``horizon_years`` here is 10 (battery warranty), overriding the 25-yr PV
    default from capital_assumptions().
    """
    return {
        "usable_kwh": Assumption(
            key="usable_kwh",
            label="Usable battery capacity",
            value=13.5,
            unit="kWh",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Tesla Powerwall 3 usable capacity (EnergySage)",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="13.5 kWh is the standard home-battery unit. See battery-answers.md.",
            ),
        ),
        "installed_cost_per_kwh": Assumption(
            key="installed_cost_per_kwh",
            label="Installed battery cost per kWh",
            value=998.0,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="EnergySage Marketplace average — $998/kWh (2026)",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="~$13,473 all-in for a 13.5 kWh Powerwall 3 before incentives.",
            ),
        ),
        "federal_itc_pct": Assumption(
            key="federal_itc_pct",
            label="Federal tax credit on battery cost",
            value=0.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Battery 25D credit EXPIRED Dec 31, 2025 (was 30%, ≥3 kWh)",
                url="https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
                note="A 2026 cash/loan buyer gets $0 federal credit. See battery-answers.md.",
            ),
        ),
        "annual_bill_savings": Assumption(
            key="annual_bill_savings",
            label="Annual electricity-bill savings from the battery",
            value=0.0,
            unit="$",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Modeling choice: ~$0 for a typical Maine residential customer",
                note="No strong residential TOU arbitrage, and NEB already credits rooftop export "
                "at retail — so a battery adds little bill savings. Raise it if you have a real "
                "price spread to arbitrage.",
            ),
        ),
        "resilience_value_per_year": Assumption(
            key="resilience_value_per_year",
            label="What backup power during outages is worth to you per year",
            value=200.0,
            unit="$",
            tag=UNSOURCED,
            source=None,
        ),
        "horizon_years": Assumption(
            key="horizon_years",
            label="Analysis horizon (battery warranty life)",
            value=10.0,
            unit="years",
            tag=DEFAULT_SOURCED,
            source=Source(
                title="Tesla Powerwall warranty — 10 years (70% capacity retention)",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="Battery economics use a 10-yr horizon, not the 25-yr PV horizon.",
            ),
        ),
    }


# --- combined options (battery + PV) ----------------------------------------

BATTERY_PREFIX = "battery_"


def _interaction_assumption(pv_label: str) -> Assumption:
    return Assumption(
        key="battery_pv_interaction_value_per_year",
        label=f"Extra annual value from pairing the battery with {pv_label} (interaction)",
        value=0.0,
        unit="$",
        tag=UNSOURCED,
        source=Source(
            title="Open research: battery+PV pairing economics",
            note="No sourced number yet — see docs/options-integration-notes.md, open item "
            "'battery+rooftop pairing economics'. Default 0 keeps the combo exactly additive "
            "(each component valued on its own). Rides the battery stream: flat $/yr over the "
            "battery horizon only.",
        ),
    )


def _combo_assumptions(pv_builder, pv_label: str) -> dict[str, Assumption]:
    """Merged assumptions for a battery+PV combo.

    Merge order (documented, per the battery precedent): shared capital defaults first (25-yr PV
    horizon, escalation, degradation, opportunity rate), then the PV option's own keys (bare —
    ``capacity_kw`` etc. keep their familiar names), then the battery's keys re-keyed under the
    ``battery_`` prefix so collisions (``federal_itc_pct``, ``horizon_years``) are resolved
    per-component, never shared. Finally the combo-only interaction slot.
    """
    merged: dict[str, Assumption] = {}
    merged.update(capital_assumptions())
    merged.update(pv_builder())
    for key, asm in battery_assumptions().items():
        prefixed = BATTERY_PREFIX + key
        merged[prefixed] = replace(asm, key=prefixed)
    merged["battery_pv_interaction_value_per_year"] = _interaction_assumption(pv_label)
    return merged


def battery_rooftop_assumptions() -> dict[str, Assumption]:
    """battery+rooftop combo defaults: rooftop keys bare, battery keys ``battery_``-prefixed."""
    return _combo_assumptions(rooftop_assumptions, "rooftop solar")


def battery_balcony_assumptions() -> dict[str, Assumption]:
    """battery+balcony combo defaults: balcony keys bare, battery keys ``battery_``-prefixed."""
    return _combo_assumptions(balcony_assumptions, "plug-in solar")
