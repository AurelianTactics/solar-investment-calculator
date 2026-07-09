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
            label="Federal tax credit on battery cost",
            value=0.0,
            unit="fraction",
            tag=DEFAULT_SOURCED,
            explain=(
                "The share of the battery's cost the federal government returns as a tax "
                "credit. The 30% residential credit (25D) covered home batteries of 3 kWh or "
                "more until it expired December 31, 2025 — so a 2026 buyer gets zero. That "
                "removed the single biggest subsidy from home-battery economics. Set it to "
                "0.30 only if your install qualified before the deadline."
            ),
            source=Source(
                title="Battery 25D credit EXPIRED Dec 31, 2025 (was 30%, ≥3 kWh)",
                url="https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
                note="A 2026 cash/loan buyer gets $0 federal credit. See battery-answers.md.",
                what_is_it=_WHAT_REWIRING,
            ),
        ),
        "annual_bill_savings": Assumption(
            key="annual_bill_savings",
            label="Annual electricity-bill savings from the battery",
            value=0.0,
            unit="$",
            tag=DEFAULT_SOURCED,
            explain=(
                "Money the battery saves on the bill itself each year — by storing cheap power "
                "and using it when power is expensive. Maine residential rates are mostly flat "
                "(no big day/night price spread), and rooftop export is already credited at "
                "retail value, so there's essentially nothing to arbitrage: the honest default "
                "is $0. Raise it only if you're on a real time-of-use rate with a spread worth "
                "chasing."
            ),
            source=Source(
                title="Modeling choice: ~$0 for a typical Maine residential customer",
                note="No strong residential TOU arbitrage, and NEB already credits rooftop export "
                "at retail — so a battery adds little bill savings. Raise it if you have a real "
                "price spread to arbitrage.",
                what_is_it=(
                    "A modeling choice this calculator states openly: with flat residential "
                    "rates and retail-value NEB credits, there is no price spread for a battery "
                    "to earn. The reasoning is in the note; there is no external study behind "
                    "the $0 — it follows from how Maine rates are structured."
                ),
            ),
        ),
        "resilience_value_per_year": Assumption(
            key="resilience_value_per_year",
            label="What backup power during outages is worth to you per year",
            value=200.0,
            unit="$",
            tag=UNSOURCED,
            explain=(
                "What not losing power in an outage is worth to YOU each year — the real "
                "reason Mainers buy batteries. It's inherently personal: spoiled food, a sump "
                "pump that must run, medical equipment, working from home through an ice "
                "storm. It's kept separate from bill savings so the pure-economics verdict "
                "stays honest. No researched number exists; $200 is a placeholder meant to "
                "make you think about your own answer."
            ),
            source=None,
        ),
        "horizon_years": Assumption(
            key="horizon_years",
            label="Analysis horizon (battery warranty life)",
            value=10.0,
            unit="years",
            tag=DEFAULT_SOURCED,
            explain=(
                "How many years of battery value the comparison counts — set to the 10-year "
                "warranty, after which capacity is no longer guaranteed. That's much shorter "
                "than the 25-year panel horizon, which is a big part of why battery economics "
                "look worse than PV: the same upfront cost has fewer years to earn its keep. "
                "In a combo, the battery keeps this horizon while the panels keep theirs."
            ),
            source=Source(
                title="Tesla Powerwall warranty — 10 years (70% capacity retention)",
                url="https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
                note="Battery economics use a 10-yr horizon, not the 25-yr PV horizon.",
                what_is_it=(
                    "The manufacturer's own warranty terms (Tesla guarantees 70% capacity "
                    "retention at 10 years), as reported in EnergySage's marketplace review — "
                    "the industry's definition of the battery's dependable life."
                ),
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
