// Solar investment calculator — web UI (question-first, all six option states).
//
// This JS is a FAITHFUL MIRROR of the Python source of truth (../src/*.py). On load it re-runs the
// hand-verified worked example for EVERY option — including the two combos — via verifyAll(); if
// any diverges, or this file throws at all, a red banner appears and tells you not to trust the
// numbers. The Python suite (pytest tests) remains the metric.
//
// Layout contract with tools/verify_web.py: selectOption(key) stays a GLOBAL function accepting
// all six option keys ("community", "balcony", "rooftop", "battery", "battery+rooftop",
// "battery+balcony"); results render `.big` and `.step-label`; the question box is `#question`;
// the fallback notice is `#notice.show`.

const TAGS = {
  DEFAULT_SOURCED: "default (sourced)",
  USER_PROVIDED: "user-provided",
  UNSOURCED: "unsourced - pending research",
};

const S = (title, url, note, whatIsIt) => ({ title, url: url || null, note: note || null, what_is_it: whatIsIt || null });
const A = (key, label, value, unit, tag, source, explain) => ({ key, label, value, unit, tag, source: source || null, explain: explain || "" });

// what_is_it boilerplate mirrored from src/assumptions.py so the prose stays in sync.
const WHAT_MAINE_DOE = "The Maine Governor's Energy Office's published electricity-price page — the state government's own summary of each utility's current approved rates. The rates are set in public filings with the Maine PUC, so this is the authoritative statement of what CMP customers actually pay.";
const WHAT_ENERGYSAGE = "EnergySage is a national solar marketplace that publishes state-by-state cost and product data aggregated from real installer quotes. Market data rather than government statistics, but drawn from thousands of actual transactions and updated frequently.";
const WHAT_REWIRING = "Rewiring America — a national electrification nonprofit — maintains a plain-English tracker of federal energy incentives. It documents the 25D residential credit's expiry; the underlying authority is the federal tax code itself.";
const WHAT_NRCM = "An explainer by the Natural Resources Council of Maine, a long-standing Maine environmental nonprofit. Advocacy-adjacent but factual journalism; its figures cross-check against the state Public Advocate's published numbers.";
const WHAT_MODELING_CHOICE = "Not an external document — a modeling choice stated by this calculator, with the reasoning written down so you can check (and change) it. It is 'sourced' in the sense that the choice is documented, not that an outside authority published the number.";

const DEFAULT_MONTHLY_BILL = 168.41; // Maine DOE — CMP average residential bill @ 550 kWh (sourced)

// The local agent service (service/app.py). The page must work fully without it (R7):
// any network error, timeout, non-OK status, or structured error body -> form flow + notice.
const SERVICE_URL = "http://127.0.0.1:8765/ask";
const ASK_TIMEOUT_MS = 4000;

// --- capital-allocation engine (mirror of src/capital.py) ------------------
function capitalCompare({ upfrontCost, annualSavingsYear1, horizonYears = 25, opportunityRate = 0.07, escalation = 0, degradation = 0 }) {
  const rows = [];
  let cumulative = 0, npv = -upfrontCost, fvSavings = 0;
  for (let t = 1; t <= horizonYears; t++) {
    const s = annualSavingsYear1 * Math.pow(1 + escalation, t - 1) * Math.pow(1 - degradation, t - 1);
    cumulative += s;
    npv += s / Math.pow(1 + opportunityRate, t);
    fvSavings += s * Math.pow(1 + opportunityRate, horizonYears - t);
    rows.push({ year: t, savings: s, cumulative });
  }
  const fvLump = upfrontCost * Math.pow(1 + opportunityRate, horizonYears);
  return {
    upfrontCost, annualSavingsYear1, horizonYears, opportunityRate, escalation, degradation,
    simplePaybackYears: annualSavingsYear1 > 0 ? upfrontCost / annualSavingsYear1 : null,
    lifetimeSavingsNominal: cumulative,
    lifetimeRoi: upfrontCost > 0 ? cumulative / upfrontCost : Infinity,
    npv, netAdvantageFv: fvSavings - fvLump, yearly: rows,
  };
}

// mirror of src/capital.py combine(): sum component streams over the longest horizon.
function capitalCombine(components) {
  if (!components.length) throw new Error("combine needs at least one component stream");
  const rate = components[0].opportunityRate;
  if (components.some((c) => c.opportunityRate !== rate)) throw new Error("component streams must share one opportunity_rate");
  const horizon = Math.max(...components.map((c) => c.horizonYears));
  const upfront = components.reduce((s, c) => s + c.upfrontCost, 0);
  const rows = [];
  let cumulative = 0, npv = -upfront, fvSavings = 0;
  for (let t = 1; t <= horizon; t++) {
    const s = components.reduce((acc, c) => acc + (t <= c.horizonYears ? c.yearly[t - 1].savings : 0), 0);
    cumulative += s;
    npv += s / Math.pow(1 + rate, t);
    fvSavings += s * Math.pow(1 + rate, horizon - t);
    rows.push({ year: t, savings: s, cumulative });
  }
  const year1 = rows[0].savings;
  return {
    upfrontCost: upfront, annualSavingsYear1: year1, horizonYears: horizon, opportunityRate: rate,
    escalation: 0, degradation: 0, // placeholders — each component stream carries its own
    simplePaybackYears: year1 > 0 ? upfront / year1 : null,
    lifetimeSavingsNominal: cumulative,
    lifetimeRoi: upfront > 0 ? cumulative / upfront : Infinity,
    npv, netAdvantageFv: fvSavings - upfront * Math.pow(1 + rate, horizon), yearly: rows,
  };
}

// --- community solar (mirror of src/solar_calc.py) -------------------------
function computeCommunity({ monthlyBill, pricePerKwh, billOffsetFraction, subscriptionDiscountPct, allocationPct = 1.0, annualUsageKwh = null }) {
  if (monthlyBill < 0) throw new Error("monthly_bill must be >= 0");
  if (pricePerKwh <= 0) throw new Error("price_per_kwh must be > 0");
  const annualSpend = monthlyBill * 12;
  const monthlyUsageKwh = monthlyBill / pricePerKwh;
  const annualUsage = annualUsageKwh != null ? annualUsageKwh : monthlyUsageKwh * 12;
  const creditsGenerated = annualUsage * allocationPct * (pricePerKwh * billOffsetFraction);
  const annualSavings = creditsGenerated * subscriptionDiscountPct;
  return {
    annualSavings, monthlySavings: annualSavings / 12,
    pctOff: annualSpend ? annualSavings / annualSpend : 0, capital: 0,
    annualSpend, annualUsageKwh: annualUsage, creditsGenerated,
    steps: [
      { n: 1, label: "Bill → annual spend (do-nothing baseline)", formula: "annual_spend = monthly_bill × 12", value: annualSpend, unit: "$/yr" },
      { n: 2, label: "Bill → estimated usage", formula: "annual_usage = (monthly_bill ÷ price_per_kwh) × 12", value: annualUsage, unit: "kWh/yr" },
      { n: 3, label: "Usage → credits the subscription generates", formula: "credits = annual_usage × allocation_pct × (price_per_kwh × bill_offset_fraction)", value: creditsGenerated, unit: "$/yr" },
      { n: 4, label: "Credits → savings (the discount you keep)", formula: "annual_savings = credits × subscription_discount_pct", value: annualSavings, unit: "$/yr" },
    ],
  };
}

// --- balcony / plug-in (mirror of src/balcony.py) --------------------------
function computeBalcony(p) {
  if (p.selfConsumption < 0 || p.selfConsumption > 1) throw new Error("self_consumption_fraction must be in [0,1]");
  const generation = p.capacityKw * p.specificYield;
  const selfConsumed = generation * p.selfConsumption;
  const annualSavings = selfConsumed * p.volumetricRate;
  const upfront = p.kitCost + p.electricianCost;
  return {
    annualSavings, upfrontCost: upfront,
    capital: capitalCompare({ upfrontCost: upfront, annualSavingsYear1: annualSavings, horizonYears: p.horizonYears, opportunityRate: p.opportunityRate, escalation: p.escalation, degradation: p.degradation }),
    steps: [
      { n: 1, label: "Size → annual generation", formula: "generation = capacity_kw × specific_yield_kwh_per_kw", value: generation, unit: "kWh/yr" },
      { n: 2, label: "Generation → self-consumed (rest is exported, uncompensated)", formula: "self_consumed = generation × self_consumption_fraction", value: selfConsumed, unit: "kWh/yr" },
      { n: 3, label: "Self-consumed → annual savings (no NEB credit for plug-in)", formula: "annual_savings = self_consumed × volumetric_rate_per_kwh", value: annualSavings, unit: "$/yr" },
      { n: 4, label: "Costs → upfront capital", formula: "upfront = kit_cost + electrician_cost", value: upfront, unit: "$" },
    ],
  };
}

// --- rooftop (mirror of src/rooftop.py) ------------------------------------
function computeRooftop(p) {
  if (p.federalItcPct < 0 || p.federalItcPct > 1) throw new Error("federal_itc_pct must be in [0,1]");
  const generation = p.capacityKw * p.specificYield;
  const effective = Math.min(generation, p.annualUsageKwh * p.offsetCapFraction);
  const annualSavings = effective * p.creditValuePerKwh;
  const gross = p.capacityKw * 1000 * p.installedCostPerW;
  const net = gross * (1 - p.federalItcPct);
  return {
    annualSavings, upfrontCost: net,
    capital: capitalCompare({ upfrontCost: net, annualSavingsYear1: annualSavings, horizonYears: p.horizonYears, opportunityRate: p.opportunityRate, escalation: p.escalation, degradation: p.degradation }),
    steps: [
      { n: 1, label: "Size → annual generation", formula: "generation = capacity_kw × specific_yield_kwh_per_kw", value: generation, unit: "kWh/yr" },
      { n: 2, label: "Generation → effective kWh (NEB; surplus beyond usage expires)", formula: "effective = min(generation, annual_usage_kwh × offset_cap_fraction)", value: effective, unit: "kWh/yr" },
      { n: 3, label: "Effective → annual savings", formula: "annual_savings = effective × credit_value_per_kwh", value: annualSavings, unit: "$/yr" },
      { n: 4, label: "Size & price → gross system cost", formula: "gross_cost = capacity_kw × 1000 × installed_cost_per_w", value: gross, unit: "$" },
      { n: 5, label: "Federal credit → net upfront capital", formula: "net_cost = gross_cost × (1 − federal_itc_pct)", value: net, unit: "$" },
    ],
  };
}

// --- battery (mirror of src/battery.py) ------------------------------------
function computeBattery(p) {
  if (p.federalItcPct < 0 || p.federalItcPct > 1) throw new Error("federal_itc_pct must be in [0,1]");
  const gross = p.usableKwh * p.installedCostPerKwh;
  const net = gross * (1 - p.federalItcPct);
  const annualSavings = p.annualBillSavings + p.resilienceValuePerYear;
  return {
    annualSavings, upfrontCost: net,
    capital: capitalCompare({ upfrontCost: net, annualSavingsYear1: annualSavings, horizonYears: p.horizonYears, opportunityRate: p.opportunityRate, escalation: 0, degradation: 0 }),
    steps: [
      { n: 1, label: "Capacity & price → gross system cost", formula: "gross_cost = usable_kwh × installed_cost_per_kwh", value: gross, unit: "$" },
      { n: 2, label: "Federal credit → net upfront capital", formula: "net_cost = gross_cost × (1 − federal_itc_pct)", value: net, unit: "$" },
      { n: 3, label: "Bill savings + resilience → annual value", formula: "annual_value = annual_bill_savings + resilience_value_per_year", value: annualSavings, unit: "$/yr" },
    ],
  };
}

// --- combo (mirror of src/combo.py): stream-wise additive -------------------
function computeCombo(pvKey, pvResult, batteryResult, interaction) {
  // The interaction uplift rides the battery stream: flat $/yr while the battery lives.
  const interactionStream = capitalCompare({
    upfrontCost: 0, annualSavingsYear1: interaction,
    horizonYears: batteryResult.capital.horizonYears,
    opportunityRate: batteryResult.capital.opportunityRate, escalation: 0, degradation: 0,
  });
  const combined = capitalCombine([pvResult.capital, batteryResult.capital, interactionStream]);
  const upfront = pvResult.upfrontCost + batteryResult.upfrontCost;
  const year1 = pvResult.annualSavings + batteryResult.annualSavings + interaction;
  const pvLabel = pvKey === "rooftop" ? "Rooftop" : "Balcony";
  return {
    annualSavings: year1, upfrontCost: upfront, capital: combined,
    steps: [
      { n: 1, label: `${pvLabel} component → year-1 savings (its own chain)`, formula: `pv_savings = ${pvKey} chain`, value: pvResult.annualSavings, unit: "$/yr" },
      { n: 2, label: `${pvLabel} component → upfront capital`, formula: `pv_upfront = ${pvKey} chain`, value: pvResult.upfrontCost, unit: "$" },
      { n: 3, label: "Battery component → year-1 value (its own chain)", formula: "battery_value = battery chain", value: batteryResult.annualSavings, unit: "$/yr" },
      { n: 4, label: "Battery component → upfront capital", formula: "battery_upfront = battery chain", value: batteryResult.upfrontCost, unit: "$" },
      { n: 5, label: "Interaction → extra annual value while the battery lives (default 0)", formula: "interaction = battery_pv_interaction_value_per_year (flat, battery years only)", value: interaction, unit: "$/yr" },
      { n: 6, label: "Components → combined upfront capital", formula: "upfront = pv_upfront + battery_upfront", value: upfront, unit: "$" },
      { n: 7, label: "Components → combined year-1 savings", formula: "year1 = pv_savings + battery_value + interaction", value: year1, unit: "$/yr" },
      { n: 8, label: "Streams → combined horizon (battery cashflows stop at its own horizon)", formula: "horizon = max(horizon_years, battery_horizon_years); per-year sums", value: combined.horizonYears, unit: "years" },
    ],
  };
}

// --- shared capital financial assumptions (mirror of capital_assumptions()) -
function capitalDefaults() {
  return {
    opportunity_rate: A("opportunity_rate", "Opportunity cost — return if you invested the cash instead", 0.07, "fraction", TAGS.DEFAULT_SOURCED,
      S("Modeling choice: long-run diversified-market return (7%/yr)", null, "The hurdle solar must beat: NPV > 0 means buying beats investing the cash at this rate.",
        "A modeling choice stated by this calculator. 7%/yr is the common shorthand for long-run diversified stock-market returns, but it is deliberately editable — your realistic alternative return is personal, and it drives the verdict."),
      "The yearly return you'd expect if, instead of buying solar, you invested the same money elsewhere — say a diversified stock-index fund. It's the hurdle solar has to clear: the NPV verdict asks whether solar's future savings, discounted at this rate, beat simply investing the cash. Raise it and solar looks worse; lower it and solar looks better. This single knob can flip the verdict."),
    electricity_escalation: A("electricity_escalation", "Annual electricity-price escalation", 0.03, "fraction", TAGS.DEFAULT_SOURCED,
      S("Modeling choice: conservative 3%/yr", null, "Maine's recent rises were far steeper; 3% is deliberately conservative.",
        "A modeling choice stated by this calculator, set conservatively at 3%/yr. The note cites NRCM's figure on recent CMP increases for context, but the 3% itself is our stated default, not a forecast from any study."),
      "How fast electricity prices rise each year. Solar savings grow with the price of the electricity you avoid buying, so higher escalation makes every future year's savings larger and the investment case stronger. Maine's recent history has been far steeper than 3% (CMP rose ~68% over five years), so the default is deliberately conservative."),
    panel_degradation: A("panel_degradation", "Annual panel output degradation", 0.005, "fraction", TAGS.DEFAULT_SOURCED,
      S("Modeling choice: industry-standard ~0.5%/yr", null, "Applies to PV generation, not battery throughput.",
        "A modeling choice using the industry-standard figure that panel manufacturers publish in their performance-warranty sheets (~0.5%/yr). Not tied to a single cited document — it's the standard engineering default."),
      "Solar panels produce slightly less electricity each year as they age — about half a percent per year, compounding to roughly 12% less output by year 25. It quietly trims each future year's savings. Warranties typically guarantee degradation stays at or below this level. Doesn't apply to batteries."),
    horizon_years: A("horizon_years", "Analysis horizon (system life)", 25, "years", TAGS.DEFAULT_SOURCED,
      S("Modeling choice: 25-year PV horizon", null, "Batteries warrant ~10 yr — that option overrides this.",
        "A modeling choice matching the 25-year performance warranty most panel manufacturers publish — the industry's own definition of a panel's dependable life."),
      "How many years of savings the comparison counts before it stops. 25 years is the length of a typical solar-panel performance warranty, so it's the standard planning life for PV. A longer horizon gives solar more years to pay off; a shorter one favors keeping the cash invested. Batteries use their own shorter 10-year horizon."),
  };
}

// --- option registry -------------------------------------------------------
const OPTIONS = {
  community: {
    label: "Community Solar",
    blurb: "Zero upfront capital. You subscribe to an off-site solar farm and buy its bill credits at a discount.",
    needsBill: true,
    describe: (a, ctx) => `community solar on a ${money(ctx.bill)} monthly bill — zero upfront capital, you keep the discount on the credits`,
    followup: "your annual kWh usage (it's in your bill's usage history) — it replaces the bill→usage estimate with the real number",
    defaults: () => ({
      price_per_kwh: A("price_per_kwh", "All-in residential price per kWh (CMP)", 0.306, "$/kWh", TAGS.DEFAULT_SOURCED,
        S("Maine DOE — Electricity Prices (CMP, eff. Jan 1 2026)", "https://www.maine.gov/energy/electricity-prices", "Display-only in the bill-first flow; resets each Jan 1.", WHAT_MAINE_DOE),
        "The all-in price you pay for each unit (kilowatt-hour) of electricity — supply, delivery, and the fixed monthly charge averaged in. The calculator uses it to translate your dollar bill into an electricity amount. In the bill-first flow it barely moves the dollar savings (it cancels out of the math); what it changes is the usage figure shown."),
      bill_offset_fraction: A("bill_offset_fraction", "Portion of the bill a community-solar credit offsets (CMP)", 0.82, "fraction", TAGS.DEFAULT_SOURCED,
        S("Maine OPA + Maine DOE — credit offsets per-kWh charges, not the fixed charge", "https://www.maine.gov/meopa/electricity/renewable-energy/community_solar", "(bill − fixed)/bill ≈ 0.82 for a 550 kWh CMP bill; rises with usage.",
          "Consumer guidance from Maine's Office of the Public Advocate — the state agency whose whole job is representing ratepayers — combined with the Maine DOE's official rate tables. Government consumer-protection material, not a solar seller's pitch."),
        "Community-solar credits can only reduce the parts of your bill charged per unit of electricity used. Every bill also contains a fixed monthly charge — the flat fee for being connected to the grid (about $30 for CMP) — that credits can never touch. This fraction is the share of a typical bill that is NOT the fixed charge, i.e. the offsettable part. If you use more electricity, the fixed charge becomes a smaller share of your bill, so this fraction (and your savings) rises."),
      subscription_discount_pct: A("subscription_discount_pct", "Subscription discount on the credit value you keep", 0.15, "fraction", TAGS.DEFAULT_SOURCED,
        S("Maine OPA (10–15%) + Solar Gardens (guaranteed 15% on CMP credits)", "https://www.maine.gov/meopa/electricity/renewable-energy/community_solar", "Discount on credits, which offset ~82% of the bill → ~12% off the total bill.",
          "Two sources: the Maine Office of the Public Advocate (a state ratepayer-advocate agency) publishes the typical 10–15% range in its consumer guidance, and Solar Gardens — an actual Maine community-solar provider — publicly guarantees 15% on CMP credits. Neutral government guidance plus a real market offer you can verify."),
        "Community solar works like buying gift cards at a markdown: the solar farm puts bill credits on your account, you pay the farm for those credits at a discount, and the discount is the only money you actually keep. At 15%, every $100 of credits costs you $85 — $15 stays in your pocket. A bigger discount means proportionally bigger savings, which makes this the single biggest lever in the whole estimate."),
      allocation_pct: A("allocation_pct", "Share of your usage the subscription is sized to cover", 1.0, "fraction", TAGS.DEFAULT_SOURCED,
        S("Modeling choice: size the subscription to your usage", null, "Over-subscribing wastes credits (they expire after 12 months).", WHAT_MODELING_CHOICE),
        "How big a subscription you buy, measured against your own electricity usage. At 100%, your share of the solar farm is sized to generate credits covering essentially all of your usage. Below 100% you're only saving on part of your bill; above 100% is actively wasteful, because credits you can't use expire after 12 months — you'd be paying the farm for credits that vanish."),
    }),
    run: (a, ctx) => computeCommunity({
      monthlyBill: ctx.bill, pricePerKwh: a.price_per_kwh.value, billOffsetFraction: a.bill_offset_fraction.value,
      subscriptionDiscountPct: a.subscription_discount_pct.value, allocationPct: a.allocation_pct.value,
      annualUsageKwh: ctx.annualUsage,
    }),
  },
  balcony: {
    label: "Balcony / Plug-In Solar",
    blurb: "Small plug-in kit (Maine LD 1730, ≤1.2 kW). NOT net-energy-billing-eligible — it only saves on what you self-consume in real time.",
    describe: (a) => `a ${a.capacity_kw.value} kW plug-in kit — it saves only on power you use the moment it's made`,
    followup: "the share of the kit's output you'd actually use in real time (your daytime baseload) — exported surplus is worth $0",
    defaults: () => ({
      capacity_kw: A("capacity_kw", "System size (plug-in)", 1.2, "kW", TAGS.DEFAULT_SOURCED,
        S("Maine LD 1730 — 1,200 W maximum", "https://mainemorningstar.com/2026/04/03/maine-renters-may-soon-be-able-to-access-solar-power-after-passage-of-plug-in-bill/", null,
          "A report by Maine Morning Star, a nonprofit Maine news outlet, on the plug-in solar bill (LD 1730). Journalism rather than the statute itself — reliable for the headline fact (the 1,200 W cap), traceable to the bill text if you want the letter of the law."),
        "The size of the plug-in kit in kilowatts — the most power it can produce in perfect sun. Maine's plug-in solar law (LD 1730) caps kits at 1,200 watts (1.2 kW), so the default is the legal maximum. More capacity means more generation and more savings, but above 1.2 kW isn't a plug-in kit anymore — it's a permitted rooftop install."),
      specific_yield_kwh_per_kw: A("specific_yield_kwh_per_kw", "Annual production per kW (Maine)", 1200, "kWh/kW/yr", TAGS.DEFAULT_SOURCED,
        S("Maine PV yield; consistent with the OPA $388/yr anchor", "https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/", null, WHAT_NRCM),
        "How much electricity one kilowatt of panels actually produces over a year in Maine's real climate — clouds, snow, and winter sun angles included. Multiply by system size to get annual output. Sunnier states run higher; shading, a bad tilt, or a north-facing balcony would drag yours below the default."),
      self_consumption_fraction: A("self_consumption_fraction", "Share of generation used on-site (rest exported, uncompensated)", 1.0, "fraction", TAGS.DEFAULT_SOURCED,
        S("Modeling choice: OPA $388/yr anchor implies near-full self-consumption", null, "Plug-in earns NOTHING for exported surplus — lower this if it out-produces your daytime load.",
          "A modeling choice: the state Public Advocate's $388/yr savings figure only works out if nearly all output is used on-site, so the default assumes that. It's the most optimistic defensible setting — check it against your own daytime usage."),
        "The share of the kit's output you use at the moment it's produced. This matters because plug-in solar earns NOTHING for surplus pushed to the grid — it isn't eligible for Maine's net-energy-billing credits. Only power you consume in real time saves money. If nobody's home at midday and the kit out-produces your fridge-and-router baseload, lower this: every unused kWh is worth $0."),
      volumetric_rate_per_kwh: A("volumetric_rate_per_kwh", "Volumetric retail rate a self-consumed kWh avoids (CMP)", 0.27, "$/kWh", TAGS.DEFAULT_SOURCED,
        S("Maine DOE — CMP per-kWh (volumetric) charges", "https://www.maine.gov/energy/electricity-prices", "Self-consumption avoids per-kWh charges, not the fixed charge.", WHAT_MAINE_DOE),
        "What each avoided kWh is actually worth to you: the per-unit charges (supply plus delivery) that disappear when your panels power the house instead of the grid. It's lower than the all-in price because the fixed monthly charge never changes no matter how little you draw."),
      kit_cost: A("kit_cost", "Plug-in kit cost", 1200, "$", TAGS.DEFAULT_SOURCED,
        S("NRCM — U.S. kits ~$1,000–1,500 (falling)", "https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/", "Midpoint of the range; an 800 W Ikea kit is ~$500 in Germany.", WHAT_NRCM),
        "The purchase price of the panel-plus-microinverter kit itself — most of the upfront cost. Payback scales directly with it: a $500 kit with the same output pays back in less than half the time of a $1,200 one. Prices are falling fast, so shopping around genuinely changes the verdict."),
      electrician_cost: A("electrician_cost", "Electrician install cost (required over 420 W)", 300, "$", TAGS.UNSOURCED, null,
        "What an electrician charges to check your circuit and install the dedicated outlet Maine requires for plug-in kits over 420 W. It adds straight to the upfront cost and stretches the payback. No researched Maine figure has landed yet — $300 is a placeholder, so get a local quote and put the real number in."),
      ...capitalDefaults(),
    }),
    run: (a) => computeBalcony({
      capacityKw: a.capacity_kw.value, specificYield: a.specific_yield_kwh_per_kw.value, selfConsumption: a.self_consumption_fraction.value,
      volumetricRate: a.volumetric_rate_per_kwh.value, kitCost: a.kit_cost.value, electricianCost: a.electrician_cost.value,
      horizonYears: a.horizon_years.value, opportunityRate: a.opportunity_rate.value, escalation: a.electricity_escalation.value, degradation: a.panel_degradation.value,
    }),
  },
  rooftop: {
    label: "Rooftop Solar",
    blurb: "High-capital, net-energy-billing-eligible. The 30% federal credit EXPIRED Dec 31, 2025 — a 2026 cash/loan buyer's default credit is 0.",
    describe: (a) => `${a.capacity_kw.value} kW of rooftop solar — NEB credits up to your usage, checked against investing the cash`,
    followup: "your real annual kWh usage — it caps what generation can earn, and a competing installer quote ($ per watt)",
    defaults: () => ({
      capacity_kw: A("capacity_kw", "System size (rooftop)", 5.5, "kW", TAGS.DEFAULT_SOURCED,
        S("Sized to a typical CMP home (~6,600 kWh/yr at ~1,200 kWh/kW)", null, "Oversizing wastes credits (they expire at 12 months).", WHAT_MODELING_CHOICE),
        "How much solar you put on the roof, in kilowatts. Size drives both generation (your savings) and cost almost linearly, so it mostly scales the whole answer up or down. The catch: sizing beyond your own usage is wasted money, because surplus net-energy-billing credits expire after 12 months."),
      specific_yield_kwh_per_kw: A("specific_yield_kwh_per_kw", "Annual production per kW (Maine)", 1200, "kWh/kW/yr", TAGS.DEFAULT_SOURCED,
        S("Maine PV yield (~1,200 kWh/kW/yr)", "https://www.energysage.com/local-data/solar-panel-cost/me/", null, WHAT_ENERGYSAGE),
        "How much electricity one kilowatt of panels produces over a year in Maine's real climate — clouds, snow, and winter sun angles included. A shaded roof, a steep north face, or heavy snow cover pulls it down; an ideal south-facing pitch can beat it slightly."),
      installed_cost_per_w: A("installed_cost_per_w", "Installed cost per watt (Maine)", 2.95, "$/W", TAGS.DEFAULT_SOURCED,
        S("EnergySage — Maine average $2.95/W (May 2026), before incentives", "https://www.energysage.com/local-data/solar-panel-cost/me/", null, WHAT_ENERGYSAGE),
        "The going rate for professionally installed rooftop solar in Maine, per watt of capacity — panels, inverter, racking, labor, permitting, all of it. It's the denominator of the whole investment case: every dime off this number shortens payback, which is why competing quotes matter more than any other shopping step."),
      federal_itc_pct: A("federal_itc_pct", "Federal tax credit on system cost", 0.0, "fraction", TAGS.DEFAULT_SOURCED,
        S("Federal 25D residential solar credit EXPIRED Dec 31, 2025 (was 30%)", "https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit", "A 2026 cash/loan buyer gets $0. Set to 0.30 only if installed by the 2025 deadline.", WHAT_REWIRING),
        "The share of the system's cost the federal government returns to you as a tax credit. For years it was 30% — but the residential credit (called 25D) expired December 31, 2025, so a 2026 cash or loan buyer gets zero. That one change added years to typical Maine paybacks."),
      credit_value_per_kwh: A("credit_value_per_kwh", "NEB credit value per kWh (volumetric, CMP)", 0.27, "$/kWh", TAGS.DEFAULT_SOURCED,
        S("Maine DOE — CMP per-kWh charge a NEB credit offsets", "https://www.maine.gov/energy/electricity-prices", null, WHAT_MAINE_DOE),
        "What each net-energy-billing (NEB) credit is worth. Every kWh your panels send to the grid earns a credit that offsets the per-kWh portion of your bill — but, like all credits, it can never touch the fixed monthly charge, so its value is the volumetric rate, not the all-in price."),
      annual_usage_kwh: A("annual_usage_kwh", "Your annual electricity usage", 6600, "kWh", TAGS.DEFAULT_SOURCED,
        S("Typical CMP residential usage (~550 kWh/month)", null, "Caps the value of generation (NEB credits beyond usage expire).",
          "A modeling choice: ~550 kWh/month is the typical CMP residential figure used across the state's own rate documents. Replace it with the actual total from twelve months of your own bills."),
        "How much electricity your home actually uses in a year. It caps what solar can earn you: generation beyond your usage produces credits that expire after 12 months, worth roughly nothing. Replacing this default with your own figure is the single most valuable personalization you can make."),
      offset_cap_fraction: A("offset_cap_fraction", "Share of usage that generation is credited against", 1.0, "fraction", TAGS.DEFAULT_SOURCED,
        S("Modeling choice: value generation up to usage only", null, "Surplus credits expire at 12 months.", WHAT_MODELING_CHOICE),
        "A conservatism knob: the share of your annual usage the calculator lets generation be credited against. At 100%, every generated kWh counts up to your full annual usage. Lower it to model situations where crediting works out worse — for example a bad seasonal mismatch where some credits expire before you can use them."),
      ...capitalDefaults(),
    }),
    run: (a) => computeRooftop({
      capacityKw: a.capacity_kw.value, specificYield: a.specific_yield_kwh_per_kw.value, installedCostPerW: a.installed_cost_per_w.value,
      federalItcPct: a.federal_itc_pct.value, creditValuePerKwh: a.credit_value_per_kwh.value, annualUsageKwh: a.annual_usage_kwh.value,
      offsetCapFraction: a.offset_cap_fraction.value, horizonYears: a.horizon_years.value, opportunityRate: a.opportunity_rate.value,
      escalation: a.electricity_escalation.value, degradation: a.panel_degradation.value,
    }),
  },
  battery: {
    label: "Home Battery Storage",
    blurb: "Bought for resilience, not ROI. With no federal credit and ~$0 Maine bill savings, the pure-economics NPV is strongly negative — by design.",
    describe: (a) => `a ${a.usable_kwh.value} kWh home battery — bought for resilience; the ledger prices that honestly`,
    followup: "what backup power through an outage is genuinely worth to you per year — it's the number that decides this one",
    defaults: () => {
      const c = capitalDefaults();
      return {
        usable_kwh: A("usable_kwh", "Usable battery capacity", 13.5, "kWh", TAGS.DEFAULT_SOURCED,
          S("Tesla Powerwall 3 usable capacity (EnergySage)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/", null,
            "EnergySage's product review of the Tesla Powerwall 3, the most commonly installed home battery. EnergySage is a national solar/storage marketplace; its reviews combine manufacturer specifications with real installer-quote data from its own platform."),
          "How much energy the battery can actually store and give back, in kilowatt-hours. It sets both the price (batteries are sold by capacity) and what an outage looks like — 13.5 kWh runs a typical home's essentials for roughly a day. More capacity costs proportionally more; it doesn't improve the bill economics."),
        installed_cost_per_kwh: A("installed_cost_per_kwh", "Installed battery cost per kWh", 998, "$/kWh", TAGS.DEFAULT_SOURCED,
          S("EnergySage Marketplace average — $998/kWh (2026)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/", "~$13,473 all-in for a 13.5 kWh Powerwall 3.", WHAT_ENERGYSAGE),
          "The installed price per kilowatt-hour of storage — hardware plus electrician, permits, and commissioning. Multiply by capacity for the sticker price. This number is what makes battery economics hard: at ~$1,000/kWh, a whole-home battery costs as much as a used car, while its yearly bill savings in Maine are close to zero."),
        federal_itc_pct: A("federal_itc_pct", "Federal tax credit on battery cost", 0.0, "fraction", TAGS.DEFAULT_SOURCED,
          S("Battery 25D credit EXPIRED Dec 31, 2025 (was 30%)", "https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit", null, WHAT_REWIRING),
          "The share of the battery's cost the federal government returns as a tax credit. The 30% residential credit (25D) covered home batteries of 3 kWh or more until it expired December 31, 2025 — so a 2026 buyer gets zero. That removed the single biggest subsidy from home-battery economics."),
        annual_bill_savings: A("annual_bill_savings", "Annual electricity-bill savings from the battery", 0.0, "$", TAGS.DEFAULT_SOURCED,
          S("Modeling choice: ~$0 for a typical Maine customer", null, "No strong residential TOU arbitrage; NEB already credits export at retail.",
            "A modeling choice this calculator states openly: with flat residential rates and retail-value NEB credits, there is no price spread for a battery to earn. The reasoning is in the note; there is no external study behind the $0 — it follows from how Maine rates are structured."),
          "Money the battery saves on the bill itself each year — by storing cheap power and using it when power is expensive. Maine residential rates are mostly flat (no big day/night price spread), and rooftop export is already credited at retail value, so there's essentially nothing to arbitrage: the honest default is $0."),
        resilience_value_per_year: A("resilience_value_per_year", "What backup power during outages is worth to you per year", 200, "$", TAGS.UNSOURCED, null,
          "What not losing power in an outage is worth to YOU each year — the real reason Mainers buy batteries. It's inherently personal: spoiled food, a sump pump that must run, medical equipment, working from home through an ice storm. It's kept separate from bill savings so the pure-economics verdict stays honest. No researched number exists; $200 is a placeholder meant to make you think about your own answer."),
        opportunity_rate: c.opportunity_rate,
        horizon_years: A("horizon_years", "Analysis horizon (battery warranty life)", 10, "years", TAGS.DEFAULT_SOURCED,
          S("Tesla Powerwall warranty — 10 years (70% retention)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/", null,
            "The manufacturer's own warranty terms (Tesla guarantees 70% capacity retention at 10 years), as reported in EnergySage's marketplace review — the industry's definition of the battery's dependable life."),
          "How many years of battery value the comparison counts — set to the 10-year warranty, after which capacity is no longer guaranteed. That's much shorter than the 25-year panel horizon, which is a big part of why battery economics look worse than PV: the same upfront cost has fewer years to earn its keep."),
      };
    },
    run: (a) => computeBattery({
      usableKwh: a.usable_kwh.value, installedCostPerKwh: a.installed_cost_per_kwh.value, federalItcPct: a.federal_itc_pct.value,
      annualBillSavings: a.annual_bill_savings.value, resilienceValuePerYear: a.resilience_value_per_year.value,
      horizonYears: a.horizon_years.value, opportunityRate: a.opportunity_rate.value,
    }),
  },
};

// combos: one mechanism, two thin registry entries (mirror of src/battery_rooftop.py etc.)
const INTERACTION_EXPLAIN = "Extra value that might exist because the battery and the panels work together — for example storing midday solar you'd otherwise export and using it at night. In Maine this is usually near zero, because net energy billing already credits exported power at retail value. The default is 0, which keeps the combo exactly additive. If research lands a real number, it applies during the battery's years only.";

function comboDefaults(pvKey, pvLabel) {
  const merged = { ...OPTIONS[pvKey].defaults() };           // PV keys bare (incl. shared capital)
  const bt = OPTIONS.battery.defaults();
  for (const [k, asm] of Object.entries(bt)) {
    if (k === "opportunity_rate") continue;                  // shared, stays bare
    merged["battery_" + k] = { ...asm, key: "battery_" + k };
  }
  merged.battery_pv_interaction_value_per_year = A(
    "battery_pv_interaction_value_per_year",
    `Extra annual value from pairing the battery with ${pvLabel} (interaction)`,
    0.0, "$", TAGS.UNSOURCED,
    S("Open research: battery+PV pairing economics", null,
      "No sourced number yet — see docs/options-integration-notes.md. Default 0 keeps the combo exactly additive."),
    INTERACTION_EXPLAIN);
  return merged;
}

function comboRun(pvKey) {
  return (a) => {
    const pvR = OPTIONS[pvKey].run(a, {});
    const btR = computeBattery({
      usableKwh: a.battery_usable_kwh.value, installedCostPerKwh: a.battery_installed_cost_per_kwh.value,
      federalItcPct: a.battery_federal_itc_pct.value, annualBillSavings: a.battery_annual_bill_savings.value,
      resilienceValuePerYear: a.battery_resilience_value_per_year.value,
      horizonYears: a.battery_horizon_years.value, opportunityRate: a.opportunity_rate.value,
    });
    return computeCombo(pvKey, pvR, btR, a.battery_pv_interaction_value_per_year.value);
  };
}

OPTIONS["battery+rooftop"] = {
  label: "Battery + Rooftop Solar",
  blurb: "The realistic pairing: rooftop PV (25-yr stream) plus a battery (10-yr stream), combined additively — each keeps its own horizon.",
  describe: (a) => `${a.capacity_kw.value} kW of rooftop solar plus a ${a.battery_usable_kwh.value} kWh battery — two streams, each on its own horizon`,
  followup: "your annual kWh usage plus a real installer quote ($ per watt) — they drive the PV side, which carries this combo",
  defaults: () => comboDefaults("rooftop", "rooftop solar"),
  run: comboRun("rooftop"),
};
OPTIONS["battery+balcony"] = {
  label: "Battery + Balcony Kit",
  blurb: "A renter-scale pairing: a plug-in kit plus a battery, combined additively — each stream keeps its own horizon and economics.",
  describe: (a) => `a ${a.capacity_kw.value} kW plug-in kit plus a ${a.battery_usable_kwh.value} kWh battery — two streams, each on its own horizon`,
  followup: "your daytime self-consumption share plus a real electrician quote — the kit's side is what earns here",
  defaults: () => comboDefaults("balcony", "plug-in solar"),
  run: comboRun("balcony"),
};

// --- on-load self-checks (mirror the Python worked examples) ---------------
function verifyAll() {
  const close = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;
  const c = computeCommunity({ monthlyBill: 150, pricePerKwh: 0.25, billOffsetFraction: 0.6, subscriptionDiscountPct: 0.12, allocationPct: 1.0 });
  if (!(close(c.annualSavings, 129.6) && close(c.pctOff, 0.072) && c.capital === 0)) return "community";
  const b = computeBalcony({ capacityKw: 1.2, specificYield: 1200, selfConsumption: 1.0, volumetricRate: 0.27, kitCost: 1200, electricianCost: 300, horizonYears: 25, opportunityRate: 0.07, escalation: 0, degradation: 0 });
  if (!(close(b.annualSavings, 388.8) && close(b.capital.simplePaybackYears, 1500 / 388.8, 1e-6))) return "balcony";
  const r = computeRooftop({ capacityKw: 5.5, specificYield: 1200, installedCostPerW: 2.95, federalItcPct: 0, creditValuePerKwh: 0.27, annualUsageKwh: 6600, offsetCapFraction: 1.0, horizonYears: 25, opportunityRate: 0.07, escalation: 0, degradation: 0 });
  if (!(close(r.annualSavings, 1782) && close(r.upfrontCost, 16225) && close(r.capital.simplePaybackYears, 16225 / 1782, 1e-6))) return "rooftop";
  const bt = computeBattery({ usableKwh: 13.5, installedCostPerKwh: 998, federalItcPct: 0, annualBillSavings: 0, resilienceValuePerYear: 200, horizonYears: 10, opportunityRate: 0.07 });
  if (!(close(bt.upfrontCost, 13473) && close(bt.annualSavings, 200) && bt.capital.npv < 0)) return "battery";

  // battery+rooftop worked example (tests/test_combo.py): flat streams -> exact additivity.
  const br = computeCombo("rooftop", r, bt, 0);
  if (!(close(br.upfrontCost, 29698) && close(br.annualSavings, 1982)
        && close(br.capital.simplePaybackYears, 29698 / 1982, 1e-6)
        && close(br.capital.npv, r.capital.npv + bt.capital.npv, 1e-6))) return "battery+rooftop";
  // horizon honesty with LIVE escalation/degradation: year 11 = PV-only cashflow.
  const rLive = computeRooftop({ capacityKw: 5.5, specificYield: 1200, installedCostPerW: 2.95, federalItcPct: 0, creditValuePerKwh: 0.27, annualUsageKwh: 6600, offsetCapFraction: 1.0, horizonYears: 25, opportunityRate: 0.07, escalation: 0.03, degradation: 0.005 });
  const brLive = computeCombo("rooftop", rLive, bt, 0);
  if (!close(brLive.capital.yearly[10].savings, rLive.capital.yearly[10].savings, 1e-6)) return "battery+rooftop";

  // battery+balcony worked example: 1500 + 13473 upfront; 388.8 + 200 year-1.
  const bb = computeCombo("balcony", b, bt, 0);
  if (!(close(bb.upfrontCost, 14973) && close(bb.annualSavings, 588.8)
        && close(bb.capital.simplePaybackYears, 14973 / 588.8, 1e-6))) return "battery+balcony";
  return null;
}

// --- rendering -------------------------------------------------------------
const money = (x) => "$" + x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (x) => x.toLocaleString("en-US", { maximumFractionDigits: 0 });
function tagClass(tag) { return tag === TAGS.UNSOURCED ? "tag tag-unsourced" : tag === TAGS.USER_PROVIDED ? "tag tag-user" : "tag tag-sourced"; }

// R4 toggle state machine. Valid states: community | battery | rooftop | balcony |
// battery+rooftop | battery+balcony. Community is exclusive; rooftop+balcony is not offered;
// deselecting down to zero re-selects community.
let activeParts = new Set(["community"]);
let currentOption = "community";
let assumptions = OPTIONS.community.defaults();
let billEdited = false;

function stateKey() {
  if (activeParts.has("community")) return "community";
  const hasBattery = activeParts.has("battery");
  if (hasBattery && activeParts.has("rooftop")) return "battery+rooftop";
  if (hasBattery && activeParts.has("balcony")) return "battery+balcony";
  return activeParts.values().next().value;
}

function toggleOption(part) {
  if (part === "community") {
    activeParts = new Set(["community"]);
  } else if (activeParts.has(part)) {
    activeParts.delete(part);
    if (activeParts.size === 0) activeParts = new Set(["community"]); // deselect-to-zero -> default
  } else {
    activeParts.delete("community");                 // capital options clear community
    if (part === "rooftop") activeParts.delete("balcony");   // rooftop+balcony not offered
    if (part === "balcony") activeParts.delete("rooftop");
    activeParts.add(part);
  }
  applyState();
}

function selectOption(key) {  // GLOBAL — the deterministic verifier's driver contract
  activeParts = new Set(key === "community" ? ["community"] : key.split("+"));
  applyState();
}

function applyState() {
  currentOption = stateKey();
  assumptions = OPTIONS[currentOption].defaults();
  syncToggles();
  const billCard = document.getElementById("bill-row");
  if (billCard) billCard.style.display = OPTIONS[currentOption].needsBill ? "block" : "none";
  updateStatement();
  recompute();
}

function syncToggles() {
  document.querySelectorAll("button.toggle").forEach((btn) => {
    const part = btn.getAttribute("data-part");
    const on = activeParts.has(part);
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

function readCtx() {
  const billRaw = document.getElementById("bill").value;
  const bill = billRaw === "" ? DEFAULT_MONTHLY_BILL : parseFloat(billRaw);
  const usageRaw = document.getElementById("annual-usage").value;
  return { bill, annualUsage: usageRaw ? parseFloat(usageRaw) : null };
}

// R3: the headline statement is a plain sentence describing the current scenario.
function updateStatement() {
  const el = document.getElementById("statement");
  const ctx = readCtx();
  const opt = OPTIONS[currentOption];
  let sentence = "Here’s the ledger for " + opt.describe(assumptions, ctx) + ".";
  if (currentOption === "community" && !billEdited) {
    sentence = "No details from you yet, so here’s the ledger for " + opt.describe(assumptions, ctx) +
      " — that bill is the sourced Maine average, not yours.";
  }
  el.textContent = sentence;
}

function showNotice(msg) {
  const n = document.getElementById("notice");
  n.textContent = msg;
  n.classList.add("show");
}
function hideNotice() { document.getElementById("notice").classList.remove("show"); }

// The question box: ask the local agent service; degrade to the form flow on ANY failure —
// the page is fully functional with zero backend (R7).
async function askQuestion(q) {
  hideNotice();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ASK_TIMEOUT_MS);
  let payload;
  try {
    const res = await fetch(SERVICE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error("service returned " + res.status);
    payload = await res.json();
  } catch (e) {
    return fallbackToForm("The calculator agent isn’t reachable — answering with the classic form below. " +
      "Open “Refine this estimate” to set the scenario by hand.");
  } finally {
    clearTimeout(timer);
  }
  if (payload.error === "cap_exceeded") {
    return fallbackToForm("The agent’s budget is used up for now — answering with the classic form below.");
  }
  if (payload.error === "unanswerable") {
    return fallbackToForm("The agent couldn’t map that question to a Maine solar option — your question is " +
      "kept above; use the classic form below.");
  }
  if (payload.error) {
    return fallbackToForm("The calculator agent hit an error — answering with the classic form below.");
  }
  renderAgentPayload(payload);
}

// Adapt the service's CLI-shaped payload to the mirror renderer: same renderer, different data.
function renderAgentPayload(payload) {
  selectOptionSilently(payload.option);
  assumptions = payload.assumptions; // same record shape: label/value/unit/tag/source/explain
  const res = payload.result;
  let r;
  if (payload.option === "community") {
    const bill = payload.inputs.monthly_bill;
    const billInput = document.getElementById("bill");
    billInput.value = bill;
    billEdited = true;
    const pill = document.getElementById("bill-tag");
    pill.textContent = TAGS.USER_PROVIDED; pill.className = "tag tag-user";
    r = { annualSavings: res.annual_savings, monthlySavings: res.monthly_savings, pctOff: res.pct_off, steps: payload.steps };
  } else {
    r = {
      annualSavings: res.annual_savings_year1, upfrontCost: res.upfront_cost, steps: payload.steps,
      capital: { npv: res.npv, simplePaybackYears: res.simple_payback_years, opportunityRate: res.opportunity_rate, horizonYears: res.horizon_years },
    };
  }
  const note = payload.agent && payload.agent.note ? " " + payload.agent.note : "";
  document.getElementById("statement").textContent =
    "Answered by the calculator agent — " + OPTIONS[currentOption].describe(assumptions, readCtx()) + "." + note;
  render(r, payload.followup);
}

// Set the six-state machine to `key` without recomputing (the agent payload carries the data).
function selectOptionSilently(key) {
  activeParts = new Set(key === "community" ? ["community"] : key.split("+"));
  currentOption = stateKey();
  syncToggles();
  const billCard = document.getElementById("bill-row");
  if (billCard) billCard.style.display = OPTIONS[currentOption].needsBill ? "block" : "none";
}

function fallbackToForm(message) {
  showNotice(message);
  document.getElementById("refine").open = true;
  updateStatement();
  recompute();
}

function recompute() {
  const opt = OPTIONS[currentOption];
  const ctx = readCtx();
  if (opt.needsBill && (isNaN(ctx.bill) || ctx.bill < 0)) {
    document.getElementById("result").innerHTML = "<p class='hint'>Enter a valid monthly bill (or clear the box to use the Maine average).</p>";
    return;
  }
  let r;
  try { r = opt.run(assumptions, ctx); }
  catch (e) { document.getElementById("result").innerHTML = `<p class='src warn'>${e.message}</p>`; return; }
  render(r);
}

function render(r, followupText) {
  const el = document.getElementById("result");
  let html = `<div class="headline">`;
  if (currentOption === "community") {
    html += `<div class="big">${money(r.annualSavings)}<span>/yr saved</span></div>`;
    html += `<div class="sub">${money(r.monthlySavings)}/mo · ${(r.pctOff * 100).toFixed(1)}% off · <strong>$0 upfront capital</strong></div>`;
  } else {
    const cap = r.capital;
    const verdict = cap.npv > 0 ? "solar wins" : "the market wins";
    const pb = cap.simplePaybackYears == null ? "never" : cap.simplePaybackYears.toFixed(1) + " yr";
    html += `<div class="big">${money(r.annualSavings)}<span>/yr (year 1)</span></div>`;
    html += `<div class="sub">${money(r.upfrontCost)} upfront · payback ${pb} · <strong>NPV ${money(cap.npv)}</strong> (${verdict} at ${(cap.opportunityRate * 100).toFixed(0)}%)</div>`;
  }
  html += `</div>`;

  html += `<h3>How we got there</h3><ol class="steps">`;
  for (const s of r.steps) {
    const shown = s.unit.startsWith("$") ? `${money(s.value)} <span class="unit">${s.unit}</span>` : `${num(s.value)} <span class="unit">${s.unit}</span>`;
    html += `<li><div class="step-label">${s.label}</div><code>${s.formula}</code><div class="step-val">= ${shown}</div></li>`;
  }
  if (currentOption !== "community") {
    const cap = r.capital;
    html += `<li><div class="step-label">Capital verdict (vs. ${(cap.opportunityRate * 100).toFixed(0)}% opportunity cost)</div><code>NPV = −upfront + Σ savings_t ÷ (1+r)^t</code><div class="step-val">= ${money(cap.npv)} <span class="unit">${cap.npv > 0 ? "solar wins" : "market wins"}, ${cap.horizonYears}-yr horizon</span></div></li>`;
  }
  html += `</ol>`;

  html += `<h3>Assumptions <span class="hint">(edit any to refine — expand a row for what it means)</span></h3><div class="assumptions">`;
  for (const key of Object.keys(assumptions)) {
    const a = assumptions[key];
    html += `<div class="assumption"><label>${a.label}</label>`;
    html += `<div class="arow"><input type="number" step="any" min="0" data-key="${key}" value="${a.value}"> <span class="unit">${a.unit}</span> <span class="${tagClass(a.tag)}">${a.tag}</span></div>`;
    if (!a.source && a.tag === TAGS.UNSOURCED) {
      html += `<div class="src warn">no source yet — don't treat this number as established fact</div>`;
    }
    if (a.explain || a.source) {
      html += `<details class="why"><summary>What this means</summary><div class="deep">`;
      if (a.explain) html += `<p>${a.explain}</p>`;
      if (a.source) {
        const cite = a.source.url ? `<a href="${a.source.url}" target="_blank" rel="noopener">${a.source.title}</a>` : a.source.title;
        html += `<p class="src">source: ${cite}${a.source.note ? ` — ${a.source.note}` : ""}</p>`;
        if (a.source.what_is_it) html += `<p class="src">what the source is: ${a.source.what_is_it}</p>`;
      } else if (a.tag === TAGS.UNSOURCED) {
        html += `<p class="src warn">This number is a placeholder awaiting research — treat it as a question, not an answer.</p>`;
      }
      html += `</div></details>`;
    }
    html += `</div>`;
  }
  html += `</div>`;

  // R5: after any result, invite the input that would most tighten the estimate.
  const followup = followupText || `The most valuable thing you could tell us: ${OPTIONS[currentOption].followup}.`;
  html += `<div class="followup"><strong>Want a tighter estimate?</strong> ${followup}</div>`;
  el.innerHTML = html;

  el.querySelectorAll("input[data-key]").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const key = e.target.getAttribute("data-key");
      const v = parseFloat(e.target.value);
      if (!isNaN(v)) { assumptions[key] = { ...assumptions[key], value: v, tag: TAGS.USER_PROVIDED, source: null }; updateStatement(); recompute(); }
    });
  });
}

window.addEventListener("DOMContentLoaded", () => {
  try {
    const failed = verifyAll();
    if (failed) throw new Error(`self-check failed for the ${failed} option`);
  } catch (e) {
    const b = document.getElementById("parity-banner");
    b.style.display = "block";
    b.textContent = `⚠ Formula self-check FAILED (${e.message}) — the web formula diverged from the verified Python worked example. Do not trust these numbers; use the Python CLI/tests.`;
  }

  // question flow
  const qbox = document.getElementById("question");
  document.getElementById("ask").addEventListener("click", () => askQuestion(qbox.value));
  qbox.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askQuestion(qbox.value); } });
  document.querySelectorAll("button.sample").forEach((btn) => {
    btn.addEventListener("click", () => { qbox.value = btn.textContent.trim(); askQuestion(qbox.value); });
  });

  // refine flow
  document.querySelectorAll("button.toggle").forEach((btn) => {
    btn.addEventListener("click", () => toggleOption(btn.getAttribute("data-part")));
  });
  const billInput = document.getElementById("bill");
  billInput.addEventListener("input", () => {
    billEdited = billInput.value !== "" && parseFloat(billInput.value) !== DEFAULT_MONTHLY_BILL;
    const pill = document.getElementById("bill-tag");
    pill.textContent = billEdited ? TAGS.USER_PROVIDED : TAGS.DEFAULT_SOURCED;
    pill.className = billEdited ? "tag tag-user" : "tag tag-sourced";
    updateStatement(); recompute();
  });
  document.getElementById("annual-usage").addEventListener("input", () => { updateStatement(); recompute(); });
  document.getElementById("reset").addEventListener("click", () => {
    assumptions = OPTIONS[currentOption].defaults();
    billInput.value = DEFAULT_MONTHLY_BILL; billEdited = false;
    document.getElementById("annual-usage").value = "";
    const pill = document.getElementById("bill-tag");
    pill.textContent = TAGS.DEFAULT_SOURCED; pill.className = "tag tag-sourced";
    updateStatement(); recompute();
  });

  // R2: with no user input, the default render is community at the sourced average Maine bill.
  selectOption("community");
});
