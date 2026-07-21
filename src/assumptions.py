"""Assumption data model for the calculator (all options).

Every number used in the calculation is an *assumption*: a labeled, tagged, optionally-sourced
record. The transparency mechanic (R6-R8) lives here — a default with no source renders as
``unsourced - pending research`` and is never presented as established fact.

As of Phase 4 (2026-05-25) the three load-bearing community defaults are ``default (sourced)``,
citing the research repo's calculator brief (../solar-investment-research/wiki/calculator-brief/).
Values are CMP defaults; a Versant user would edit them. ``allocation_pct`` is a stated modeling
choice, not external fact. The ``unsourced - pending research`` tag remains a first-class state for
any assumption whose research hasn't landed.

Since the options expansion (2026-07-09) every assumption also carries ``explain`` — a
newcomer-grade plain-English explanation (what the number means, why it matters to YOUR savings,
what moves it) — and every source carries ``what_is_it`` (what kind of document the source is, who
publishes it, why it's credible). Both flow to the CLI text render, ``--json``, and the web mirror.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

# --- tags (R6) -------------------------------------------------------------
DEFAULT_SOURCED = "default (sourced)"
USER_PROVIDED = "user-provided"
UNSOURCED = "unsourced - pending research"

# what_is_it boilerplate for the two most-cited publishers (kept as constants so the prose stays
# consistent everywhere the source appears).
_WHAT_MAINE_DOE = (
    "The Maine Governor's Energy Office's published electricity-price page — the state "
    "government's own summary of each utility's current approved rates. The rates are set in "
    "public filings with the Maine PUC, so this is the authoritative statement of what CMP "
    "customers actually pay."
)
_WHAT_ENERGYSAGE = (
    "EnergySage is a national solar marketplace that publishes state-by-state cost and product "
    "data aggregated from real installer quotes. Market data rather than government statistics, "
    "but drawn from thousands of actual transactions and updated frequently."
)
_WHAT_REWIRING = (
    "Rewiring America — a national electrification nonprofit — maintains a plain-English tracker "
    "of federal energy incentives. It documents the 25D residential credit's expiry; the "
    "underlying authority is the federal tax code itself."
)
_WHAT_NRCM = (
    "An explainer by the Natural Resources Council of Maine, a long-standing Maine environmental "
    "nonprofit. Advocacy-adjacent but factual journalism; its figures cross-check against the "
    "state Public Advocate's published numbers."
)
_WHAT_MODELING_CHOICE = (
    "Not an external document — a modeling choice stated by this calculator, with the reasoning "
    "written down in the note so you can check (and change) it. It is 'sourced' in the sense that "
    "the choice is documented, not that an outside authority published the number."
)
_WHAT_CMP_TOU = (
    "Central Maine Power's own published tariff page for its optional residential Time-of-Use "
    "delivery rate (effective July 1, 2026). Utility rates are approved in public filings with "
    "the Maine PUC, so this is the authoritative statement of the on-peak, off-peak, and flat "
    "delivery prices the arithmetic uses."
)
_CMP_TOU_URL = "https://www.cmpco.com/time-of-use-delivery-rate"


@dataclass(frozen=True)
class Source:
    title: str
    url: Optional[str] = None
    note: Optional[str] = None
    # What kind of document this is, who publishes it, and why it's credible — written for
    # someone who has never heard of the publisher (R12).
    what_is_it: Optional[str] = None


@dataclass(frozen=True)
class Assumption:
    key: str
    label: str
    value: float
    unit: str  # "$/kWh" | "fraction" | "$" | "kWh"
    tag: str
    source: Optional[Source] = None
    # Newcomer-grade plain-English depth: what this number means, why it matters to your savings,
    # and what makes it bigger or smaller (R11). Optional-with-default so construction sites and
    # tests that build ad-hoc Assumptions keep working.
    explain: str = ""

    def with_user_value(self, value: float) -> "Assumption":
        """Return a copy re-tagged ``user-provided`` (R7, AE2). Editing clears the source but
        keeps ``explain`` — the meaning of the number doesn't change when you supply your own."""
        return replace(self, value=value, tag=USER_PROVIDED, source=None)

    @property
    def is_unsourced(self) -> bool:
        return self.tag == UNSOURCED


def default_assumptions() -> dict[str, Assumption]:
    """The community-solar shipped defaults. Returns a fresh dict each call (records are immutable)."""
    return {
        "default_monthly_bill": Assumption(
            key="default_monthly_bill",
            label="Average Maine monthly electricity bill (used when you haven't entered yours)",
            value=168.41,
            unit="$",
            tag=DEFAULT_SOURCED,
            explain=(
                "The starting bill the estimate uses before you've told us yours — the average "
                "CMP residential bill for a typical 550 kWh month. Every dollar figure scales "
                "with the bill, so replacing this with your own bill (top of any recent "
                "statement) is the first and easiest personalization. A bigger bill means "
                "proportionally bigger community-solar savings."
            ),
            source=Source(
                title="Maine DOE — CMP average residential bill $168.41 @ 550 kWh (eff. Jan 1 2026)",
                url="https://www.maine.gov/energy/electricity-prices",
                note="See solar-investment-research/wiki/utilities/cmp-rates.md. Used only until "
                "a real bill is entered; then the estimate re-tags user-provided.",
                what_is_it=_WHAT_MAINE_DOE,
            ),
        ),
        "price_per_kwh": Assumption(
            key="price_per_kwh",
            label="All-in residential price per kWh (CMP)",
            value=0.306,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "The all-in price you pay for each unit (kilowatt-hour) of electricity — supply, "
                "delivery, and the fixed monthly charge averaged in. The calculator uses it to "
                "translate your dollar bill into an electricity amount. In the bill-first flow it "
                "barely moves the dollar savings (it cancels out of the math); what it changes is "
                "the usage figure shown. Rates reset every January 1, and Versant territory "
                "differs from CMP."
            ),
            source=Source(
                title="Maine DOE — Electricity Prices (CMP, effective Jan 1 2026)",
                url="https://www.maine.gov/energy/electricity-prices",
                note="All-in average = $168.41 / 550 kWh. Display-only in the bill-first flow "
                "(it cancels out of the dollar result). Resets every Jan 1. See "
                "solar-investment-research/wiki/utilities/cmp-rates.md.",
                what_is_it=_WHAT_MAINE_DOE,
            ),
        ),
        "bill_offset_fraction": Assumption(
            key="bill_offset_fraction",
            label="Portion of the bill a community-solar credit offsets (CMP)",
            value=0.82,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "Community-solar credits can only reduce the parts of your bill charged per unit "
                "of electricity used. Every bill also contains a fixed monthly charge — the flat "
                "fee for being connected to the grid (about $30 for CMP) — that credits can never "
                "touch. This fraction is the share of a typical bill that is NOT the fixed "
                "charge, i.e. the offsettable part. If you use more electricity, the fixed charge "
                "becomes a smaller share of your bill, so this fraction (and your savings) rises."
            ),
            source=Source(
                title="Maine OPA + Maine DOE — credit offsets per-kWh charges, not the fixed charge",
                url="https://www.maine.gov/meopa/electricity/renewable-energy/community_solar",
                note="(bill - fixed) / bill = ($168.41 - $30.21) / $168.41 ~= 0.82 for a typical "
                "550 kWh CMP bill; rises with usage. See "
                "solar-investment-research/wiki/mechanics/maine-bill-anatomy.md.",
                what_is_it=(
                    "Consumer guidance from Maine's Office of the Public Advocate — the state "
                    "agency whose whole job is representing ratepayers — combined with the Maine "
                    "DOE's official rate tables. Government consumer-protection material, not a "
                    "solar seller's pitch."
                ),
            ),
        ),
        "subscription_discount_pct": Assumption(
            key="subscription_discount_pct",
            label="Subscription discount on the credit value you keep as savings",
            value=0.15,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "Community solar works like buying gift cards at a markdown: the solar farm puts "
                "bill credits on your account, you pay the farm for those credits at a discount, "
                "and the discount is the only money you actually keep. At 15%, every $100 of "
                "credits costs you $85 — $15 stays in your pocket. A bigger discount means "
                "proportionally bigger savings, which makes this the single biggest lever in the "
                "whole estimate. Always check the discount in the contract you're offered."
            ),
            source=Source(
                title="Maine OPA (10-15%) + Solar Gardens (guaranteed 15% on CMP credits)",
                url="https://www.maine.gov/meopa/electricity/renewable-energy/community_solar",
                note="Discount on the credits, which offset ~82% of the bill, so it nets ~12% off "
                "the total bill (0.15 x 0.82). See "
                "solar-investment-research/wiki/options/community-solar-subscription.md.",
                what_is_it=(
                    "Two sources: the Maine Office of the Public Advocate (a state ratepayer-"
                    "advocate agency) publishes the typical 10-15% range in its consumer "
                    "guidance, and Solar Gardens — an actual Maine community-solar provider — "
                    "publicly guarantees 15% on CMP credits. Neutral government guidance plus a "
                    "real market offer you can verify."
                ),
            ),
        ),
        "allocation_pct": Assumption(
            key="allocation_pct",
            label="Share of your usage the subscription is sized to cover",
            value=1.00,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "How big a subscription you buy, measured against your own electricity usage. At "
                "100%, your share of the solar farm is sized to generate credits covering "
                "essentially all of your usage. Below 100% you're only saving on part of your "
                "bill; above 100% is actively wasteful, because credits you can't use expire "
                "after 12 months — you'd be paying the farm for credits that vanish. Providers "
                "typically size you to about 100% from your usage history."
            ),
            source=Source(
                title="Modeling choice: size the subscription to your usage",
                note="Stated default (100%), not an external citation. Over-subscribing wastes "
                "credits because unused credits expire after 12 months.",
                what_is_it=_WHAT_MODELING_CHOICE,
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
            explain=(
                "The yearly return you'd expect if, instead of buying solar, you invested the "
                "same money elsewhere — say a diversified stock-index fund. It's the hurdle "
                "solar has to clear: the NPV verdict asks whether solar's future savings, "
                "discounted at this rate, beat simply investing the cash. Raise it and solar "
                "looks worse; lower it (your money would otherwise sit in a savings account) and "
                "solar looks better. This single knob can flip the verdict."
            ),
            source=Source(
                title="Modeling choice: long-run diversified-market return",
                note="Stated default (7%/yr nominal), not a citation. This is the hurdle solar must "
                "beat: NPV > 0 means buying solar beats investing this capital at this rate.",
                what_is_it=(
                    "A modeling choice stated by this calculator. 7%/yr is the common shorthand "
                    "for long-run diversified stock-market returns, but it is deliberately "
                    "editable — your realistic alternative return is personal, and it drives the "
                    "verdict."
                ),
            ),
        ),
        "electricity_escalation": Assumption(
            key="electricity_escalation",
            label="Annual electricity-price escalation",
            value=0.03,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "How fast electricity prices rise each year. Solar savings grow with the price "
                "of the electricity you avoid buying, so higher escalation makes every future "
                "year's savings larger and the investment case stronger. Maine's recent history "
                "has been far steeper than 3% (CMP rose ~68% over five years), so the default is "
                "deliberately conservative — raise it to stress-test the other direction."
            ),
            source=Source(
                title="Modeling choice: conservative long-run electricity inflation",
                note="Stated default (3%/yr). Maine's recent rises were far steeper (NRCM cites a "
                "68% CMP increase over five years); 3% is deliberately conservative — raise it to "
                "stress-test.",
                what_is_it=(
                    "A modeling choice stated by this calculator, set conservatively at 3%/yr. "
                    "The note cites NRCM's figure on recent CMP increases for context, but the "
                    "3% itself is our stated default, not a forecast from any study."
                ),
            ),
        ),
        "panel_degradation": Assumption(
            key="panel_degradation",
            label="Annual panel output degradation",
            value=0.005,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "Solar panels produce slightly less electricity each year as they age — the "
                "industry standard is about half a percent per year, which compounds to roughly "
                "12% less output by year 25. It quietly trims each future year's savings. Panel "
                "warranties typically guarantee degradation stays at or below this level, so "
                "raising it models a worse-than-warranty panel. Doesn't apply to batteries."
            ),
            source=Source(
                title="Modeling choice: industry-standard ~0.5%/yr degradation",
                note="Stated default (0.5%/yr). Applies to PV generation (balcony/rooftop), not to "
                "battery throughput.",
                what_is_it=(
                    "A modeling choice using the industry-standard figure that panel "
                    "manufacturers publish in their performance-warranty sheets (~0.5%/yr). Not "
                    "tied to a single cited document — it's the standard engineering default."
                ),
            ),
        ),
        "horizon_years": Assumption(
            key="horizon_years",
            label="Analysis horizon (system life)",
            value=25.0,
            unit="years",
            tag=DEFAULT_SOURCED,
            explain=(
                "How many years of savings the comparison counts before it stops. 25 years is "
                "the length of a typical solar-panel performance warranty, so it's the standard "
                "planning life for PV. A longer horizon gives solar more years to pay off and "
                "favors buying; a shorter one favors keeping the cash invested. Batteries use "
                "their own shorter 10-year horizon."
            ),
            source=Source(
                title="Modeling choice: 25-year PV horizon",
                note="Stated default (25 yr), the common panel-warranty life. Batteries typically "
                "warrant ~10 yr — shorten the horizon when modeling battery-only economics.",
                what_is_it=(
                    "A modeling choice matching the 25-year performance warranty most panel "
                    "manufacturers publish — the industry's own definition of a panel's "
                    "dependable life."
                ),
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
            explain=(
                "The size of the plug-in kit in kilowatts — the most power it can produce in "
                "perfect sun. Maine's plug-in solar law (LD 1730) caps kits at 1,200 watts "
                "(1.2 kW), so the default is the legal maximum. More capacity means more "
                "generation and more savings, but above 1.2 kW isn't a plug-in kit anymore — "
                "it's a permitted rooftop install."
            ),
            source=Source(
                title="Maine LD 1730 — maximum permitted plug-in size is 1,200 W",
                url="https://mainemorningstar.com/2026/04/03/maine-renters-may-soon-be-able-to-access-solar-power-after-passage-of-plug-in-bill/",
                note="1.2 kW is the legal max; see balcony-answers.md.",
                what_is_it=(
                    "A report by Maine Morning Star, a nonprofit Maine news outlet, on the "
                    "plug-in solar bill (LD 1730). Journalism rather than the statute itself — "
                    "reliable for the headline fact (the 1,200 W cap), traceable to the bill "
                    "text if you want the letter of the law."
                ),
            ),
        ),
        "specific_yield_kwh_per_kw": Assumption(
            key="specific_yield_kwh_per_kw",
            label="Annual production per kW (Maine)",
            value=1200.0,
            unit="kWh/kW/yr",
            tag=DEFAULT_SOURCED,
            explain=(
                "How much electricity one kilowatt of panels actually produces over a year in "
                "Maine's real climate — clouds, snow, and winter sun angles included. Multiply "
                "by system size to get annual output. Sunnier states run higher; shading, a bad "
                "tilt, or a north-facing balcony would drag yours below the default. This is "
                "the physics knob of the whole estimate."
            ),
            source=Source(
                title="Maine PV yield (~1,200 kWh/kW/yr), consistent with the OPA $388/yr anchor",
                url="https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/",
                note="Implied by OPA $388/yr ÷ $0.27/kWh ÷ 1.2 kW. See balcony-answers.md.",
                what_is_it=_WHAT_NRCM,
            ),
        ),
        "self_consumption_fraction": Assumption(
            key="self_consumption_fraction",
            label="Share of generation used on-site (rest is exported, uncompensated)",
            value=1.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "The share of the kit's output you use at the moment it's produced. This matters "
                "because plug-in solar earns NOTHING for surplus pushed to the grid — it isn't "
                "eligible for Maine's net-energy-billing credits. Only power you consume in real "
                "time saves money. If nobody's home at midday and the kit out-produces your "
                "fridge-and-router baseload, lower this: every unused kWh is worth $0."
            ),
            source=Source(
                title="Modeling choice: the OPA $388/yr anchor implies near-full self-consumption",
                note="Stated default (100%). Plug-in solar earns NOTHING for exported surplus (not "
                "NEB-eligible), so lower this if a 1.2 kW kit out-produces your daytime baseload.",
                what_is_it=(
                    "A modeling choice: the state Public Advocate's $388/yr savings figure only "
                    "works out if nearly all output is used on-site, so the default assumes "
                    "that. It's the most optimistic defensible setting — check it against your "
                    "own daytime usage."
                ),
            ),
        ),
        "volumetric_rate_per_kwh": Assumption(
            key="volumetric_rate_per_kwh",
            label="Volumetric retail rate a self-consumed kWh avoids (CMP)",
            value=0.27,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "What each avoided kWh is actually worth to you: the per-unit charges (supply "
                "plus delivery) that disappear when your panels power the house instead of the "
                "grid. It's lower than the all-in price because the fixed monthly charge never "
                "changes no matter how little you draw. When rates rise, every self-consumed "
                "kWh becomes worth more and the kit pays back faster."
            ),
            source=Source(
                title="Maine DOE — CMP per-kWh (volumetric) charges",
                url="https://www.maine.gov/energy/electricity-prices",
                note="Self-consumption avoids per-kWh charges, not the fixed charge. See "
                "solar-investment-research/wiki/utilities/cmp-rates.md.",
                what_is_it=_WHAT_MAINE_DOE,
            ),
        ),
        "kit_cost": Assumption(
            key="kit_cost",
            label="Plug-in kit cost",
            value=1200.0,
            unit="$",
            tag=DEFAULT_SOURCED,
            explain=(
                "The purchase price of the panel-plus-microinverter kit itself — most of the "
                "upfront cost. Payback scales directly with it: a $500 kit with the same output "
                "pays back in less than half the time of a $1,200 one. Prices are falling fast, "
                "and Europe's mature plug-in market sells similar kits far cheaper, so shopping "
                "around genuinely changes the verdict."
            ),
            source=Source(
                title="NRCM — U.S. plug-in kits ~$1,000-1,500 today (falling)",
                url="https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/",
                note="Midpoint of the $1,000-1,500 range; an 800 W Ikea kit is ~$500 in Germany.",
                what_is_it=_WHAT_NRCM,
            ),
        ),
        "electrician_cost": Assumption(
            key="electrician_cost",
            label="Electrician install cost (required for kits over 420 W)",
            value=300.0,
            unit="$",
            tag=UNSOURCED,
            explain=(
                "What an electrician charges to check your circuit and install the dedicated "
                "outlet Maine requires for plug-in kits over 420 W. It adds straight to the "
                "upfront cost and stretches the payback. No researched Maine figure has landed "
                "yet — $300 is a placeholder, so get a local quote and put the real number in."
            ),
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
            explain=(
                "How much solar you put on the roof, in kilowatts. Size drives both generation "
                "(your savings) and cost almost linearly, so it mostly scales the whole answer "
                "up or down. The catch: sizing beyond your own usage is wasted money, because "
                "surplus net-energy-billing credits expire after 12 months. The default is "
                "sized to fully offset a typical CMP home's usage."
            ),
            source=Source(
                title="Sized to a typical CMP home (~6,600 kWh/yr at ~1,200 kWh/kW)",
                note="Editable; size to your own usage. Oversizing wastes credits (they expire at "
                "12 months). See rooftop-answers.md.",
                what_is_it=_WHAT_MODELING_CHOICE,
            ),
        ),
        "specific_yield_kwh_per_kw": Assumption(
            key="specific_yield_kwh_per_kw",
            label="Annual production per kW (Maine)",
            value=1200.0,
            unit="kWh/kW/yr",
            tag=DEFAULT_SOURCED,
            explain=(
                "How much electricity one kilowatt of panels produces over a year in Maine's "
                "real climate — clouds, snow, and winter sun angles included. Multiply by "
                "system size for annual output. A shaded roof, a steep north face, or heavy "
                "snow cover pulls it down; an ideal south-facing pitch can beat it slightly."
            ),
            source=Source(
                title="Maine PV yield (~1,200 kWh/kW/yr)",
                url="https://www.energysage.com/local-data/solar-panel-cost/me/",
                note="Standard Maine production figure. See rooftop-answers.md.",
                what_is_it=_WHAT_ENERGYSAGE,
            ),
        ),
        "installed_cost_per_w": Assumption(
            key="installed_cost_per_w",
            label="Installed cost per watt (Maine)",
            value=2.95,
            unit="$/W",
            tag=DEFAULT_SOURCED,
            explain=(
                "The going rate for professionally installed rooftop solar in Maine, per watt "
                "of capacity — panels, inverter, racking, labor, permitting, all of it. "
                "Multiply by system size in watts for the sticker price. It's the denominator "
                "of the whole investment case: every dime off this number shortens payback, "
                "which is why competing quotes matter more than any other shopping step."
            ),
            source=Source(
                title="EnergySage — Maine average $2.95/W (May 2026), before incentives",
                url="https://www.energysage.com/local-data/solar-panel-cost/me/",
                note="~$33,198 for an average 11.26 kW system; scales ~linearly with size.",
                what_is_it=_WHAT_ENERGYSAGE,
            ),
        ),
        "federal_itc_pct": Assumption(
            key="federal_itc_pct",
            label="Federal tax credit on system cost",
            value=0.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "The share of the system's cost the federal government returns to you as a tax "
                "credit. For years it was 30% — but the residential credit (called 25D) expired "
                "December 31, 2025, so a 2026 cash or loan buyer gets zero. That one change "
                "added years to typical Maine paybacks. Set it back to 0.30 only if your "
                "install qualified before the deadline."
            ),
            source=Source(
                title="Federal 25D residential solar credit EXPIRED Dec 31, 2025 (was 30%)",
                url="https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
                note="A 2026 cash/loan buyer gets $0 federal credit. Set to 0.30 only if you "
                "installed by the 2025 deadline. See rooftop-answers.md.",
                what_is_it=_WHAT_REWIRING,
            ),
        ),
        "credit_value_per_kwh": Assumption(
            key="credit_value_per_kwh",
            label="NEB credit value per kWh (volumetric, CMP)",
            value=0.27,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "What each net-energy-billing (NEB) credit is worth. Every kWh your panels "
                "send to the grid earns a credit that offsets the per-kWh portion of your bill "
                "— but, like all credits, it can never touch the fixed monthly charge, so its "
                "value is the volumetric rate, not the all-in price. When rates rise, existing "
                "systems earn more per kWh."
            ),
            source=Source(
                title="Maine DOE — CMP per-kWh (volumetric) charge a NEB credit offsets",
                url="https://www.maine.gov/energy/electricity-prices",
                note="Credits offset per-kWh charges, not the fixed charge. See "
                "solar-investment-research/wiki/utilities/cmp-rates.md.",
                what_is_it=_WHAT_MAINE_DOE,
            ),
        ),
        "annual_usage_kwh": Assumption(
            key="annual_usage_kwh",
            label="Your annual electricity usage",
            value=6600.0,
            unit="kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "How much electricity your home actually uses in a year. It caps what solar "
                "can earn you: generation beyond your usage produces credits that expire after "
                "12 months, worth roughly nothing. Your utility bill's usage history has the "
                "real number — replacing this default with your own figure is the single most "
                "valuable personalization you can make."
            ),
            source=Source(
                title="Typical CMP residential usage (~550 kWh/month)",
                note="Caps the value of generation (NEB credits beyond usage expire). Edit to your "
                "own annual kWh.",
                what_is_it=(
                    "A modeling choice: ~550 kWh/month is the typical CMP residential figure "
                    "used across the state's own rate documents. Replace it with the actual "
                    "total from twelve months of your own bills."
                ),
            ),
        ),
        "offset_cap_fraction": Assumption(
            key="offset_cap_fraction",
            label="Share of usage that generation is credited against",
            value=1.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "A conservatism knob: the share of your annual usage the calculator lets "
                "generation be credited against. At 100%, every generated kWh counts up to "
                "your full annual usage. Lower it to model situations where crediting works "
                "out worse — for example if your usage and the sun are badly mismatched across "
                "seasons and some credits expire before you can use them."
            ),
            source=Source(
                title="Modeling choice: value generation up to usage only",
                note="Stated default (100%). NEB credits bank but expire after 12 months, so "
                "generation beyond annual usage earns ~nothing.",
                what_is_it=_WHAT_MODELING_CHOICE,
            ),
        ),
    }


# --- time-of-use arbitrage inputs (shared by battery's tou_enrolled mode and plugin-battery) ---------

def _tou_shared_assumptions() -> dict[str, Assumption]:
    """The master-equation inputs (see ``src/tou.py``): the two CMP delivery-rate spreads plus the
    two load-shape numbers only the user can supply. District-aware by editing: the source notes
    carry the Versant "Home Eco" values so a Versant user can --set them in."""
    return {
        "annual_usage_kwh": Assumption(
            key="annual_usage_kwh",
            label="Your annual electricity usage",
            value=6600.0,
            unit="kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "How much electricity your home uses in a year. In the time-of-use model it scales the "
                "enrollment discount: every kWh you use earns the flat-vs-off-peak delivery "
                "discount just by being enrolled, so a bigger home has a bigger arbitrage "
                "ceiling. Your utility bill's usage history has the real number — use it."
            ),
            source=Source(
                title="Typical CMP residential usage (~550 kWh/month)",
                note="Scales the time-of-use enrollment discount (usage x $0.058120/kWh ceiling). Edit "
                "to your own annual kWh.",
                what_is_it=(
                    "A modeling choice: ~550 kWh/month is the typical CMP residential figure "
                    "used across the state's own rate documents. Replace it with the actual "
                    "total from twelve months of your own bills."
                ),
            ),
        ),
        "on_peak_share": Assumption(
            key="on_peak_share",
            label="Share of your usage during on-peak hours (weekday 5-9 p.m.)",
            value=0.25,
            unit="fraction",
            tag=UNSOURCED,
            explain=(
                "The fraction of your electricity used on weekdays between 5 and 9 p.m. — the "
                "single number that decides which time-of-use case you're in. Under 15.8%, the time-of-use rate "
                "beats the flat rate even with no battery (free money by enrolling); over it, "
                "the on-peak penalty (3.6x the flat rate) bites and a battery has to rescue "
                "you. Nobody can guess this for you: download your hourly usage from your "
                "utility's website and measure it. The 25% default is only a placeholder for a "
                "typical evening-heavy home."
            ),
            source=None,
        ),
        "residual_coverage": Assumption(
            key="residual_coverage",
            label="Share of on-peak usage the battery can actually shift off-peak",
            value=0.7,
            unit="fraction",
            tag=UNSOURCED,
            explain=(
                "How much of your 5-9 p.m. load the battery can actually serve. A single-outlet "
                "plug-in unit covers whatever is plugged into it; a multi-circuit subpanel setup "
                "covers more. The hard part is winter electric heat — often the biggest on-peak "
                "load and exactly what a small battery can't carry — which is why this dial "
                "(0.5-0.9 is the plausible range) is the model's load-bearing unknown. No "
                "researched Maine figure has landed; 0.7 is a placeholder."
            ),
            source=None,
        ),
        "enrollment_discount_per_kwh": Assumption(
            key="enrollment_discount_per_kwh",
            label="Time-of-use enrollment discount per kWh (flat minus off-peak delivery, CMP)",
            value=0.058120,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "What every kWh you use earns simply by being enrolled in the time-of-use rate, as long "
                "as it's bought off-peak: the flat delivery rate ($0.119590) minus the off-peak "
                "delivery rate ($0.061470). Multiply by your annual usage and you have the "
                "absolute ceiling on time-of-use savings — what a magic free battery covering "
                "everything would earn. Delivery-only: the supply price is the same on both "
                "rates and cancels out."
            ),
            source=Source(
                title="CMP time-of-use delivery-rate tariff (eff. Jul 1, 2026): $0.119590 flat - $0.061470 off-peak",
                url=_CMP_TOU_URL,
                note="Versant's 'Home Eco' time-of-use rate (BHD Rate A-4 / MPD A-4M) has a much thinner "
                "spread — set this and the penalty so their difference matches its ~$0.101 "
                "(BHD) / ~$0.099 (MPD) peak-vs-off-peak gap; its on-peak runs only ~6% above "
                "flat, so enrolling there is nearly risk-free and works weekends too. See "
                "solar-investment-research/wiki/utilities/versant-rates.md.",
                what_is_it=_WHAT_CMP_TOU,
            ),
        ),
        "residual_penalty_per_kwh": Assumption(
            key="residual_penalty_per_kwh",
            label="On-peak penalty per residual kWh (on-peak minus off-peak delivery, CMP)",
            value=0.367366,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "What every kWh you still buy during weekday 5-9 p.m. costs you versus buying "
                "it off-peak: the on-peak delivery rate ($0.428836, about 3.6x the flat rate) "
                "minus the off-peak rate ($0.061470). It's also what every kWh a battery SHIFTS "
                "off-peak avoids — but it is the penalty avoided, not the saving versus the "
                "flat rate, which is why the model never multiplies it by your whole usage."
            ),
            source=Source(
                title="CMP time-of-use delivery-rate tariff (eff. Jul 1, 2026): $0.428836 on-peak - $0.061470 off-peak",
                url=_CMP_TOU_URL,
                note="The threshold on-peak share (below which time-of-use beats flat with no battery) "
                "is discount / penalty = 0.1582 — matching CMP's own '>=86% off-peak' guidance. "
                "Versant Home Eco's penalty is only ~$0.10 with on-peak ~6% above flat: thin "
                "arbitrage, near-zero enrollment risk.",
                what_is_it=_WHAT_CMP_TOU,
            ),
        ),
    }


def battery_assumptions() -> dict[str, Assumption]:
    """Home battery defaults. Sourced to
    ../solar-investment-research/wiki/calculator-brief/battery-answers.md (refreshed 2026-07-16).

    The honest framing: a battery doesn't pay for itself on Maine bill economics (flat-rate
    default, no owner-bought federal credit since 25D expired). Its value is resilience — modeled
    as a separate, user-set ``resilience_value_per_year`` kept apart from bill savings so the
    pure-economics verdict stays honest. The one real lever is the off-by-default ``tou_enrolled``
    mode (optional time-of-use delivery rate; conditional, delivery-only). ``horizon_years`` is 13 — the
    expected LFP *service life*, not the 10-year *warranty* (kept as ``warranty_years``, the risk
    floor) — overriding the 25-yr PV default from capital_assumptions().
    """
    return {
        **_tou_shared_assumptions(),
        "tou_enrolled": Assumption(
            key="tou_enrolled",
            label="Enrolled in the optional time-of-use delivery rate? (0 = no, 1 = yes)",
            value=0.0,
            unit="0 or 1",
            tag=DEFAULT_SOURCED,
            explain=(
                "Whether you've switched from the default flat delivery rate to the optional "
                "time-of-use rate (CMP's 'Rate TOU', Versant's 'Home Eco'). Off by default because "
                "most homes are on the flat rate, where a battery has nothing to arbitrage. "
                "Turn it on (set to 1) and the battery faces the three-case time-of-use math: under a "
                "15.8% on-peak share the rate alone wins and the battery adds gravy; over it, "
                "the battery has to rescue the enrollment from the 3.6x on-peak penalty."
            ),
            source=Source(
                title="Modeling choice: time-of-use arbitrage is an optional, off-by-default mode",
                note="Enrollment is a choice, not the default — and CMP's spread is fat but "
                "conditional (needs ~86% off-peak), so the mode ships off. Versant's Home Eco "
                "is thin but nearly risk-free.",
                what_is_it=_WHAT_MODELING_CHOICE,
            ),
        ),
        "usable_kwh": Assumption(
            key="usable_kwh",
            label="Usable battery capacity",
            value=13.5,
            unit="kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "How much energy the battery can actually store and give back, in "
                "kilowatt-hours. It sets both the price (batteries are sold by capacity) and "
                "what an outage looks like — 13.5 kWh runs a typical home's essentials "
                "(fridge, heat circulators, lights, internet) for roughly a day. More capacity "
                "costs proportionally more; it doesn't improve the bill economics."
            ),
            source=Source(
                title="Tesla Powerwall 3 usable capacity (EnergySage)",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="13.5 kWh is the standard home-battery unit. See battery-answers.md.",
                what_is_it=(
                    "EnergySage's product review of the Tesla Powerwall 3, the most commonly "
                    "installed home battery. EnergySage is a national solar/storage marketplace; "
                    "its reviews combine manufacturer specifications with real installer-quote "
                    "data from its own platform."
                ),
            ),
        ),
        "installed_cost_per_kwh": Assumption(
            key="installed_cost_per_kwh",
            label="Installed battery cost per kWh",
            value=998.0,
            unit="$/kWh",
            tag=DEFAULT_SOURCED,
            explain=(
                "The installed price per kilowatt-hour of storage — hardware plus electrician, "
                "permits, and commissioning. Multiply by capacity for the sticker price. This "
                "number is what makes battery economics hard: at ~$1,000/kWh, a whole-home "
                "battery costs as much as a used car, while its yearly bill savings in Maine "
                "are close to zero. Falling prices move this verdict more than anything else."
            ),
            source=Source(
                title="EnergySage Marketplace average — $998/kWh (2026)",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="~$13,473 all-in for a 13.5 kWh Powerwall 3 before incentives.",
                what_is_it=_WHAT_ENERGYSAGE,
            ),
        ),
        "federal_itc_pct": Assumption(
            key="federal_itc_pct",
            label="Federal credit reaching you (owner-bought 0; lease/PPA pass-through unknown)",
            value=0.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "The share of the battery's cost that federal incentives actually return to "
                "you. This is now a two-path financing switch, not a single rate. Owner-bought "
                "(cash or loan): the 30% residential credit (25D) expired December 31, 2025, so "
                "a 2026 buyer gets zero — the default. Lease/PPA (third-party-owned): the "
                "commercial 48E credit survives for standalone storage — the provider claims up "
                "to 30% and passes some of it through as lower payments — but how much reaches "
                "a Maine homeowner is an open research question, so don't pencil in a number "
                "you weren't quoted. Set this above 0 only to model a pass-through you can "
                "verify in an actual lease offer."
            ),
            source=Source(
                title="25D EXPIRED Dec 31, 2025 (owner-bought: $0); 48E survives via lease/PPA",
                url="https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
                note="48E covers standalone storage begun before 2033 (FEOC content rules "
                "apply: >=55% non-PFE in 2026); the installer claims it on Form 3468 — the "
                "homeowner never files Form 5695. Pass-through % to a Maine homeowner is "
                "unsourced. See battery-answers.md answer 2.",
                what_is_it=_WHAT_REWIRING,
            ),
        ),
        "annual_bill_savings": Assumption(
            key="annual_bill_savings",
            label="Annual electricity-bill savings from the battery (outside the time-of-use mode)",
            value=0.0,
            unit="$",
            tag=DEFAULT_SOURCED,
            explain=(
                "Money the battery saves on the bill itself each year, outside the time-of-use "
                "arbitrage modeled separately. On the default flat rate (CMP Rate A: delivery "
                "AND supply both flat) there is no intraday price spread, and rooftop export "
                "is already credited at retail value under net energy billing — so the honest "
                "default is $0. Residential time-of-use arbitrage DOES exist, but it's conditional and "
                "delivery-only, so it lives in its own switch (tou_enrolled) rather than being "
                "buried here."
            ),
            source=Source(
                title="Modeling choice: ~$0 on the default flat rate (arbitrage lives in the time-of-use mode)",
                note="CMP's optional time-of-use delivery rate (eff. Jul 1, 2026) is a genuine but conditional, "
                "delivery-only arbitrage — modeled by the off-by-default tou_enrolled mode, not "
                "by this number. On the flat rate there is no spread; NEB already credits "
                "rooftop export at retail.",
                what_is_it=(
                    "A modeling choice this calculator states openly: with a flat rate and "
                    "retail-value NEB credits, there is no price spread for a battery to earn "
                    "outside the optional time-of-use rate. The reasoning is in the note; the time-of-use rates "
                    "themselves are sourced on the arbitrage assumptions."
                ),
            ),
        ),
        "resilience_value_per_year": Assumption(
            key="resilience_value_per_year",
            label="What backup power during outages is worth to you per year",
            value=0.0,
            unit="$",
            tag=UNSOURCED,
            explain=(
                "What not losing power in an outage is worth to YOU each year — the real "
                "reason Mainers buy batteries. It's inherently personal: spoiled food, a sump "
                "pump that must run, medical equipment, working from home through an ice "
                "storm. It's kept separate from bill savings so the pure-economics verdict "
                "stays honest. No researched number exists and no one can price your outage "
                "for you, so the default is $0: the verdict you see counts only money the "
                "battery demonstrably saves. Put your own number here and the ledger will "
                "carry it."
            ),
            source=None,
        ),
        "annual_degradation": Assumption(
            key="annual_degradation",
            label="Annual battery capacity fade",
            value=0.03,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "How much usable capacity the battery loses each year as its cells age. LFP "
                "chemistry (Powerwall 3) fades roughly 1-4% a year, and the fade continues "
                "past the warranty's 70%-at-10-years floor. The model trims each future "
                "year's value by this rate, the battery equivalent of panel degradation. "
                "Deep-cycling daily to chase time-of-use savings pushes you toward the fast end."
            ),
            source=Source(
                title="Modeling choice: ~3%/yr LFP capacity fade (1-4%/yr range)",
                note="Bracketed by the LFP literature and the 70%@10yr warranty point; a "
                "measured Powerwall 3 curve (plus a Maine cold-climate adjustment) would "
                "replace it. See battery-answers.md answer 3.",
                what_is_it=_WHAT_MODELING_CHOICE,
            ),
        ),
        "warranty_years": Assumption(
            key="warranty_years",
            label="Warranty term (the guarantee floor — not the expected life)",
            value=10.0,
            unit="years",
            tag=DEFAULT_SOURCED,
            explain=(
                "How long the manufacturer guarantees the battery (Tesla: 70% capacity "
                "retention at 10 years, unlimited cycles for a solar home). Like a car "
                "warranty, it's a floor, not a life expectancy — which is why the analysis "
                "horizon below is longer. This number doesn't enter the math; it's here so "
                "the risk window (years beyond warranty are on you) stays visible next to "
                "the service-life horizon the dollars are computed over."
            ),
            source=Source(
                title="Tesla Powerwall warranty — 10 years, 70% capacity retention",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="Unlimited cycles for solar use (throughput capped only for non-solar "
                "use) — a signal Tesla doesn't expect death at year 10. The warranty is the "
                "risk floor; the horizon models the expected life.",
                what_is_it=(
                    "The manufacturer's own warranty terms, as reported in EnergySage's "
                    "marketplace review — the industry's definition of the battery's "
                    "guaranteed (not expected) life."
                ),
            ),
        ),
        "horizon_years": Assumption(
            key="horizon_years",
            label="Analysis horizon (expected battery service life)",
            value=13.0,
            unit="years",
            tag=DEFAULT_SOURCED,
            explain=(
                "How many years of battery value the comparison counts — set to the expected "
                "service life of an LFP battery like the Powerwall 3 (~12-15 years, default "
                "13), not the 10-year warranty, which is a guarantee floor the way a car "
                "warranty is. Still much shorter than the 25-year panel horizon. Honest "
                "caveat: with ~$0 bill savings the extra years add ~$0 each, so the longer "
                "horizon nudges NPV without flipping the resilience-not-ROI verdict — its "
                "real effect is that you shouldn't budget a year-10 replacement."
            ),
            source=Source(
                title="Expected Powerwall 3 service life ~12-15 yr (default 13); warranty is 10",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="Warranty (10 yr, 70% retention) != life. Model the ~13-yr expected life "
                "with continued ~3%/yr fade; keep warranty_years as the separate risk window. "
                "See battery-answers.md answer 3.",
                what_is_it=(
                    "A modeling choice anchored to the manufacturer's warranty terms and "
                    "LFP-lifespan reporting (EnergySage review plus battery-life explainers): "
                    "the warranty floor is 10 years, the reported expected service life "
                    "~12-15."
                ),
            ),
        ),
    }


def plugin_battery_assumptions() -> dict[str, Assumption]:
    """Plug-in / DIY DER battery defaults. Sourced to
    ../solar-investment-research/wiki/calculator-brief/plugin-battery-answers.md.

    The time-of-use arbitrage model (see ``src/plugin_battery.py``), scoped to homes already under the
    0.1582 on-peak line: the arbitrage *rates* and the algebra are sourced/exact; the two
    load-bearing unknowns — ``installed_cost_per_kwh`` and ``residual_coverage`` — ship honestly
    tagged ``unsourced``. ``on_peak_share`` is the user's own metered number, and this option
    overrides the shared 0.25 default with an under-the-line placeholder so the defaults describe
    a home the option actually models. ``horizon_years`` here is 10 (consumer power-station
    service life), overriding the 25-yr PV default from capital_assumptions().
    """
    return {
        **_tou_shared_assumptions(),
        "on_peak_share": Assumption(
            key="on_peak_share",
            label="Share of your usage during on-peak hours (weekday 5-9 p.m.)",
            value=0.12,
            unit="fraction",
            tag=UNSOURCED,
            explain=(
                "The fraction of your electricity used on weekdays between 5 and 9 p.m. — the "
                "number that decides whether this option applies to you at all. Under 15.8%, the "
                "time-of-use rate already beats the flat rate with no battery, and a plug-in battery "
                "adds arbitrage on top of that: this is the situation the calculator models. "
                "Over 15.8%, the on-peak penalty (3.6x the flat rate) means enrolling loses "
                "money until a battery rescues it — a different calculation that isn't built "
                "yet, so the calculator says so instead of guessing. Nobody can estimate this "
                "for you: download your hourly usage from your utility's website and measure it. "
                "The 12% default is only a placeholder for an off-peak-leaning home."
            ),
            source=None,
        ),
        "cycles_per_year": Assumption(
            key="cycles_per_year",
            label="Charge/discharge cycles per year (one per on-peak weekday)",
            value=250.0,
            unit="cycles/yr",
            tag=DEFAULT_SOURCED,
            explain=(
                "How many times a year the battery runs its daily routine: charge off-peak, "
                "discharge through the 5-9 p.m. window. On-peak hours exist only on non-holiday "
                "weekdays, so ~250 cycles a year is the ceiling. It also sizes the battery: the "
                "kWh you want shifted per year, divided by the cycles available to shift them, "
                "is the usable capacity you need to buy."
            ),
            source=Source(
                title="Modeling choice: 250 weekday cycles/yr (CMP on-peak is weekdays 5-9 p.m.)",
                note="~52 weeks x 5 weekdays minus holidays. Derived from the CMP tariff's "
                "on-peak definition; the count itself is a stated modeling choice.",
                what_is_it=_WHAT_MODELING_CHOICE,
            ),
        ),
        "value_per_usable_kwh_yr": Assumption(
            key="value_per_usable_kwh_yr",
            label="Arbitrage value per usable kWh of battery per year",
            value=90.13,
            unit="$/kWh/yr",
            tag=DEFAULT_SOURCED,
            explain=(
                "What one kWh of battery capacity earns per year once you're on the time-of-use rate: "
                "250 weekday cycles times the on-peak price avoided, net of the ~10% round-trip "
                "charging loss. Multiply by the analysis horizon and you get the break-even "
                "installed cost — about $901/kWh over 10 years — which is why a cheap plug-in "
                "unit clears it and a $998/kWh Powerwall doesn't."
            ),
            source=Source(
                title="CMP time-of-use tariff arithmetic: 250 x ($0.428836 - $0.061470/0.90) ~= $90.13",
                url=_CMP_TOU_URL,
                note="Exact algebra on the sourced tariff rates with a 0.90 round-trip "
                "efficiency. Break-even ~= $901/kWh simple over 10 yr (~$633 at 7% NPV). See "
                "plugin-battery-answers.md (the under-the-line case).",
                what_is_it=_WHAT_CMP_TOU,
            ),
        ),
        "installed_cost_per_kwh": Assumption(
            key="installed_cost_per_kwh",
            label="Plug-in battery cost per usable kWh",
            value=600.0,
            unit="$/kWh",
            tag=UNSOURCED,
            explain=(
                "What a buy-and-plug battery costs per usable kWh. Ballparks: consumer power "
                "stations (EcoFlow, Bluetti, Anker) run roughly $500-700/kWh; a DIY LFP "
                "battery plus inverter more like $300-500/kWh. Compare whatever you find "
                "against the break-even $/kWh the calculator reports — that single comparison "
                "is the verdict. No verbatim price page has been ingested yet, so $600 is a "
                "placeholder: price a real unit before deciding."
            ),
            source=None,
        ),
        "federal_itc_pct": Assumption(
            key="federal_itc_pct",
            label="Federal tax credit on battery cost",
            value=0.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "The share of the cost the federal government returns as a tax credit: zero. "
                "The residential credit (25D) expired December 31, 2025, and the surviving "
                "commercial path (48E) reaches homeowners only through a lease/PPA provider — "
                "which a self-installed plug-in battery doesn't have. Unlike the installed "
                "battery, there's no financing structure that changes this answer."
            ),
            source=Source(
                title="25D expired Dec 31, 2025; no third-party-ownership path for a self-install",
                url="https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
                note="A 2026 buy-and-plug buyer gets $0 federal credit. See "
                "plugin-battery-answers.md.",
                what_is_it=_WHAT_REWIRING,
            ),
        ),
        "resilience_value_per_year": Assumption(
            key="resilience_value_per_year",
            label="What backup power during outages is worth to you per year",
            value=0.0,
            unit="$",
            tag=UNSOURCED,
            explain=(
                "What not losing power in an outage is worth to YOU each year. A plug-in "
                "battery doubles as portable backup — fridge, phones, a sump pump through an "
                "ice storm — which for many buyers is the real reason to own one, with the "
                "time-of-use arbitrage as the kicker. Kept separate from the arbitrage so "
                "the pure-economics verdict stays honest. No researched number exists and no "
                "one can price your outage for you, so the default is $0: the verdict you "
                "see counts only money the battery demonstrably saves. Put your own number "
                "here and the ledger will carry it."
            ),
            source=None,
        ),
        "horizon_years": Assumption(
            key="horizon_years",
            label="Analysis horizon (plug-in battery service life)",
            value=10.0,
            unit="years",
            tag=DEFAULT_SOURCED,
            explain=(
                "How many years of value the comparison counts — a stated ~10-year service "
                "life for a consumer power station cycled daily. Shorter than the installed "
                "battery's 13-year horizon because the hardware is cheaper and the daily "
                "time-of-use cycling works it harder. The Case-2 break-even scales directly with "
                "this: ~$901/kWh at 10 years, ~$1,172 at 13."
            ),
            source=Source(
                title="Modeling choice: 10-yr consumer power-station horizon",
                note="A stated planning life, not a warranty citation — plug-in units "
                "typically warrant 2-5 yr; LFP cell cycle life supports ~10 at one cycle/day. "
                "See plugin-battery-answers.md.",
                what_is_it=_WHAT_MODELING_CHOICE,
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
        explain=(
            "Extra value that might exist because the battery and the panels work together — "
            "for example storing midday solar you'd otherwise export and using it at night. In "
            "Maine this is usually near zero, because net energy billing already credits "
            "exported power at retail value, leaving little for the battery to add. The "
            "default is 0, which keeps the combo exactly additive (each component valued on "
            "its own). If research lands a real number, it applies during the battery's years "
            "only."
        ),
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
