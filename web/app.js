// Solar investment calculator — web UI (question-first, all seven option states).
//
// This JS is a FAITHFUL MIRROR of the Python source of truth (../src/*.py). On load it re-runs the
// hand-verified worked example for EVERY option — including the two combos — via verifyAll(); if
// any diverges, or this file throws at all, a red banner appears and tells you not to trust the
// numbers. The Python suite (pytest tests) remains the metric.
//
// Layout contract with tools/verify_web.py: selectOption(key) stays a GLOBAL function accepting
// all seven option keys ("community", "balcony", "rooftop", "battery", "plugin-battery",
// "battery+rooftop", "battery+balcony"); selectCompare(keys) stays a GLOBAL entering the side-by-side comparison
// view (renders `.cmp-table`, plus one `details.opt-sec` ledger section per compared option in
// #detail, each rendering `.step-label`); results render `.big` and `.step-label`; the question
// box is `#question`; the fallback notice is `#notice.show` and its text always contains "without
// the agent". The headline renders into the sticky `#result` card; steps + assumptions render
// into `#detail` inside the "Refine this estimate" drawer; the tighter-estimate tip renders into
// `#tip-body` under the Ask box. `#copy-link` (optional — wired only if present) copies the
// scenario URL.
//
// STATE <-> TEXT is a closed loop, and both directions are load-bearing:
//   state -> text   `syncQuestionBox()` rewrites #question from the current scenario on every
//                   render, so the box can never contradict the headline; `syncUrl()` mirrors the
//                   same state into the query string, which is the scenario's save file.
//   text -> state   `askQuestion()` elides any question the page itself authored (it still holds
//                   the state that produced the text, so there is nothing to interpret), then
//                   falls to the local parser, then to the service.
// A page-authored #question is therefore NOT a neutral starting value: anything that asks the
// box's resting text gets an instant local recompute rather than a service round-trip. The
// deterministic verifier types its own question for exactly this reason.
//
// Refining vs. comparing is ONE drawer, split by what an edit is allowed to touch:
//   * shared inputs (#bill, #annual-usage, #shared-assumptions) describe YOUR situation and drive
//     every option on screen — in compare mode an edit there moves every row at once;
//   * per-option ledgers (#detail) describe ONE option and move only that option's row.
// A key is shared or per-option, never both: SHARED_KEYS are lifted out of the ledgers while
// comparing, so there is never a second control editing the same number.

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

// --- TOU three-case engine (mirror of src/tou.py) --------------------------
// The master equation, delivery-only: savings_vs_flat = U × discount − residual × penalty.
// Case 2 (under the 15.8% line, "gravy"): baseline is TOU-alone, the battery earns only the
// incremental shifted kWh × penalty. Case 3 (over the line, "rescue"): baseline is FLAT ($0),
// the battery earns the whole net vs. flat, floored at 0 (below 0 you just stay on flat).
function touEvaluate({ annualUsageKwh, onPeakShare, residualCoverage, enrollmentDiscountPerKwh, residualPenaltyPerKwh }) {
  if (annualUsageKwh < 0) throw new Error("annual_usage_kwh must be >= 0");
  if (onPeakShare < 0 || onPeakShare > 1) throw new Error("on_peak_share must be in [0,1]");
  if (residualCoverage < 0 || residualCoverage > 1) throw new Error("residual_coverage must be in [0,1]");
  if (enrollmentDiscountPerKwh < 0) throw new Error("enrollment_discount_per_kwh must be >= 0");
  if (residualPenaltyPerKwh <= 0) throw new Error("residual_penalty_per_kwh must be > 0");
  const onPeakKwh = annualUsageKwh * onPeakShare;
  const thresholdShare = enrollmentDiscountPerKwh / residualPenaltyPerKwh;
  const underThreshold = onPeakShare < thresholdShare;
  const enrollmentOnlySavings = annualUsageKwh * enrollmentDiscountPerKwh - onPeakKwh * residualPenaltyPerKwh;
  const shiftedKwh = residualCoverage * onPeakKwh;
  const residualKwh = onPeakKwh - shiftedKwh;
  const savingsVsFlat = annualUsageKwh * enrollmentDiscountPerKwh - residualKwh * residualPenaltyPerKwh;
  const kase = underThreshold ? 2 : 3;
  const arbitrage = underThreshold ? shiftedKwh * residualPenaltyPerKwh : Math.max(0, savingsVsFlat);
  return { onPeakKwh, thresholdShare, underThreshold, case: kase, enrollmentOnlySavings, shiftedKwh, residualKwh, savingsVsFlat, arbitrage };
}

// --- battery (mirror of src/battery.py) ------------------------------------
function computeBattery(p) {
  if (p.federalItcPct < 0 || p.federalItcPct > 1) throw new Error("federal_itc_pct must be in [0,1]");
  const gross = p.usableKwh * p.installedCostPerKwh;
  const net = gross * (1 - p.federalItcPct);
  const tou = p.touEnrolled
    ? touEvaluate({ annualUsageKwh: p.annualUsageKwh, onPeakShare: p.onPeakShare, residualCoverage: p.residualCoverage, enrollmentDiscountPerKwh: p.enrollmentDiscountPerKwh, residualPenaltyPerKwh: p.residualPenaltyPerKwh })
    : null;
  const touArbitrage = tou ? tou.arbitrage : 0;
  const annualSavings = p.annualBillSavings + touArbitrage + p.resilienceValuePerYear;
  const touLabel = tou
    ? `TOU mode ON → Case ${tou.case} arbitrage (threshold: on-peak share < ${tou.thresholdShare.toFixed(4)})`
    : "TOU mode off (default) → no arbitrage on a flat rate";
  const touFormula = tou
    ? (tou.case === 2 ? "case 2 (gravy): arb = shifted_kwh × residual_penalty_per_kwh"
                      : "case 3 (rescue): arb = max(0, usage × discount − residual_kwh × penalty)")
    : "tou_arbitrage = 0 (tou_enrolled = 0: staying on the flat rate)";
  return {
    annualSavings, upfrontCost: net, tou, touArbitrage,
    capital: capitalCompare({ upfrontCost: net, annualSavingsYear1: annualSavings, horizonYears: p.horizonYears, opportunityRate: p.opportunityRate, escalation: 0, degradation: p.annualDegradation || 0 }),
    steps: [
      { n: 1, label: "Capacity & price → gross system cost", formula: "gross_cost = usable_kwh × installed_cost_per_kwh", value: gross, unit: "$" },
      { n: 2, label: "Federal credit → net upfront capital", formula: "net_cost = gross_cost × (1 − federal_itc_pct)", value: net, unit: "$" },
      { n: 3, label: touLabel, formula: touFormula, value: touArbitrage, unit: "$/yr" },
      { n: 4, label: "Bill savings + TOU arbitrage + resilience → annual value", formula: "annual_value = annual_bill_savings + tou_arbitrage + resilience_value_per_year", value: annualSavings, unit: "$/yr" },
    ],
  };
}

// --- plug-in / DIY DER battery (mirror of src/plugin_battery.py) ------------
function computePluginBattery(p) {
  if (p.installedCostPerKwh < 0) throw new Error("installed_cost_per_kwh must be >= 0");
  if (p.cyclesPerYear <= 0) throw new Error("cycles_per_year must be > 0");
  if (p.federalItcPct < 0 || p.federalItcPct > 1) throw new Error("federal_itc_pct must be in [0,1]");
  const t = touEvaluate({ annualUsageKwh: p.annualUsageKwh, onPeakShare: p.onPeakShare, residualCoverage: p.residualCoverage, enrollmentDiscountPerKwh: p.enrollmentDiscountPerKwh, residualPenaltyPerKwh: p.residualPenaltyPerKwh });
  // Scope: this option models only the home already under the TOU line. Over it the baseline is
  // flat instead of TOU and the battery must rescue the enrollment — a different calculation,
  // backlogged rather than half-modeled. Python raises OutOfScope here; recompute() renders it.
  if (!t.underThreshold) {
    throw new Error(`This option models only homes already under the TOU on-peak line (under ${(t.thresholdShare * 100).toFixed(1)}% of usage on weekday 5–9 p.m.); yours is set to ${(p.onPeakShare * 100).toFixed(1)}%. Over the line, enrolling in TOU loses money before the battery even starts, so the battery has to rescue the enrollment rather than add to it — a calculation that isn't built yet. Set your real on-peak share from your utility's hourly download, or compare the installed battery instead.`);
  }
  const usableKwhNeeded = t.shiftedKwh / p.cyclesPerYear;
  const gross = usableKwhNeeded * p.installedCostPerKwh;
  const net = gross * (1 - p.federalItcPct);
  const annualSavings = t.arbitrage + p.resilienceValuePerYear;
  const breakEven = p.valuePerUsableKwhYr * p.horizonYears;
  return {
    annualSavings, upfrontCost: net, tou: t, usableKwhNeeded, breakEvenCostPerKwh: breakEven,
    enrollmentOnlySavings: t.enrollmentOnlySavings,
    capital: capitalCompare({ upfrontCost: net, annualSavingsYear1: annualSavings, horizonYears: p.horizonYears, opportunityRate: p.opportunityRate, escalation: 0, degradation: 0 }),
    steps: [
      { n: 1, label: "Usage × on-peak share → on-peak kWh (weekday 5–9 p.m.)", formula: "on_peak_kwh = annual_usage_kwh × on_peak_share", value: t.onPeakKwh, unit: "kWh/yr" },
      { n: 2, label: `Threshold check → the most on-peak kWh a home can use and still win on TOU alone (${(t.thresholdShare * 100).toFixed(1)}% of usage); you're at ${(p.onPeakShare * 100).toFixed(1)}%, under it, so this option applies`, formula: "on_peak_ceiling = annual_usage_kwh × enrollment_discount_per_kwh ÷ residual_penalty_per_kwh", value: t.thresholdShare * p.annualUsageKwh, unit: "kWh/yr" },
      { n: 3, label: "Switching to TOU with NO battery → what the rate change alone saves (the battery's baseline)", formula: "enrollment_only = usage × enrollment_discount − on_peak_kwh × residual_penalty", value: t.enrollmentOnlySavings, unit: "$/yr" },
      { n: 4, label: "Battery coverage → shifted on-peak kWh (the rest stays on-peak)", formula: "shifted_kwh = residual_coverage × on_peak_kwh", value: t.shiftedKwh, unit: "kWh/yr" },
      { n: 5, label: "Shifted load ÷ cycles → battery size needed", formula: "usable_kwh_needed = shifted_kwh ÷ cycles_per_year", value: usableKwhNeeded, unit: "kWh" },
      { n: 6, label: "Size × price → gross cost", formula: "gross_cost = usable_kwh_needed × installed_cost_per_kwh", value: gross, unit: "$" },
      { n: 7, label: "Federal credit → net upfront capital (25D expired; no TPO for a self-install)", formula: "net_cost = gross_cost × (1 − federal_itc_pct)", value: net, unit: "$" },
      { n: 8, label: "TOU arbitrage the battery adds on top of enrolling (each shifted kWh dodges the on-peak penalty)", formula: "tou_arbitrage = shifted_kwh × residual_penalty_per_kwh", value: t.arbitrage, unit: "$/yr" },
      { n: 9, label: "Break-even installed cost (the shopping number: pay less than this per kWh and the battery pays for itself)", formula: "break_even = value_per_usable_kwh_yr × horizon_years", value: breakEven, unit: "$/kWh" },
      { n: 10, label: "Arbitrage + resilience → annual value", formula: "annual_value = tou_arbitrage + resilience_value_per_year", value: annualSavings, unit: "$/yr" },
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

// --- TOU arbitrage inputs (mirror of _tou_shared_assumptions()) -------------
const WHAT_CMP_TOU = "Central Maine Power's own published tariff page for its optional residential Time-of-Use delivery rate (effective July 1, 2026). Utility rates are approved in public filings with the Maine PUC, so this is the authoritative statement of the on-peak, off-peak, and flat delivery prices the arithmetic uses.";
const CMP_TOU_URL = "https://www.cmpco.com/time-of-use-delivery-rate";

function touSharedDefaults() {
  return {
    annual_usage_kwh: A("annual_usage_kwh", "Your annual electricity usage", 6600, "kWh", TAGS.DEFAULT_SOURCED,
      S("Typical CMP residential usage (~550 kWh/month)", null, "Scales the TOU enrollment discount (usage × $0.058120/kWh ceiling). Edit to your own annual kWh.",
        "A modeling choice: ~550 kWh/month is the typical CMP residential figure used across the state's own rate documents. Replace it with the actual total from twelve months of your own bills."),
      "How much electricity your home uses in a year. In the TOU model it scales the enrollment discount: every kWh you use earns the flat-vs-off-peak delivery discount just by being enrolled, so a bigger home has a bigger arbitrage ceiling. Your utility bill's usage history has the real number — use it."),
    on_peak_share: A("on_peak_share", "Share of your usage during on-peak hours (weekday 5–9 p.m.)", 0.25, "fraction", TAGS.UNSOURCED, null,
      "The fraction of your electricity used on weekdays between 5 and 9 p.m. — the single number that decides which TOU case you're in. Under 15.8%, the TOU rate beats the flat rate even with no battery (free money by enrolling); over it, the on-peak penalty (3.6× the flat rate) bites and a battery has to rescue you. Nobody can guess this for you: download your hourly usage from your utility's website and measure it. The 25% default is only a placeholder for a typical evening-heavy home."),
    residual_coverage: A("residual_coverage", "Share of on-peak usage the battery can actually shift off-peak", 0.7, "fraction", TAGS.UNSOURCED, null,
      "How much of your 5–9 p.m. load the battery can actually serve. A single-outlet plug-in unit covers whatever is plugged into it; a multi-circuit subpanel setup covers more. The hard part is winter electric heat — often the biggest on-peak load and exactly what a small battery can't carry — which is why this dial (0.5–0.9 is the plausible range) is the model's load-bearing unknown. No researched Maine figure has landed; 0.7 is a placeholder."),
    enrollment_discount_per_kwh: A("enrollment_discount_per_kwh", "TOU enrollment discount per kWh (flat minus off-peak delivery, CMP)", 0.058120, "$/kWh", TAGS.DEFAULT_SOURCED,
      S("CMP Rate TOU tariff (eff. Jul 1, 2026): $0.119590 flat − $0.061470 off-peak", CMP_TOU_URL,
        "Versant's 'Home Eco' TOU (BHD Rate A-4 / MPD A-4M) has a much thinner spread — set this and the penalty so their difference matches its ~$0.101 (BHD) / ~$0.099 (MPD) peak-vs-off-peak gap; its on-peak runs only ~6% above flat, so enrolling there is nearly risk-free and works weekends too.", WHAT_CMP_TOU),
      "What every kWh you use earns simply by being enrolled in the TOU rate, as long as it's bought off-peak: the flat delivery rate ($0.119590) minus the off-peak delivery rate ($0.061470). Multiply by your annual usage and you have the absolute ceiling on TOU savings — what a magic free battery covering everything would earn. Delivery-only: the supply price is the same on both rates and cancels out."),
    residual_penalty_per_kwh: A("residual_penalty_per_kwh", "On-peak penalty per residual kWh (on-peak minus off-peak delivery, CMP)", 0.367366, "$/kWh", TAGS.DEFAULT_SOURCED,
      S("CMP Rate TOU tariff (eff. Jul 1, 2026): $0.428836 on-peak − $0.061470 off-peak", CMP_TOU_URL,
        "The threshold on-peak share (below which TOU beats flat with no battery) is discount ÷ penalty = 0.1582 — matching CMP's own '≥86% off-peak' guidance. Versant Home Eco's penalty is only ~$0.10 with on-peak ~6% above flat: thin arbitrage, near-zero enrollment risk.", WHAT_CMP_TOU),
      "What every kWh you still buy during weekday 5–9 p.m. costs you versus buying it off-peak: the on-peak delivery rate ($0.428836, about 3.6× the flat rate) minus the off-peak rate ($0.061470). It's also what every kWh a battery SHIFTS off-peak avoids — but it is the penalty avoided, not the saving versus the flat rate, which is why the model never multiplies it by your whole usage."),
  };
}

// --- option registry -------------------------------------------------------
const OPTIONS = {
  community: {
    label: "Community Solar",
    blurb: "Zero upfront capital. You subscribe to an off-site solar farm and buy its bill credits at a discount.",
    needsBill: true,
    describe: (a, ctx) => `community solar on a ${money(ctx.bill)} monthly bill — zero upfront capital, you keep the discount on the credits`,
    followup: "your electricity usage in kWh — monthly or annual, it's in your bill's usage history — and who your utility is; it replaces the bill→usage estimate with the real number",
    example: "I use 550 kWh a month with CMP — what would community solar save me?",
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
    blurb: "Bought for resilience, not ROI. On the default flat rate with no owner-bought federal credit, the pure-economics NPV is strongly negative — by design. The one bill lever is the off-by-default TOU mode.",
    describe: (a) => `a ${a.usable_kwh.value} kWh home battery — bought for resilience; the ledger prices that honestly`,
    followup: "what backup power through an outage is genuinely worth to you per year — and, if you'd enroll in a TOU rate, your on-peak share (weekday 5–9 p.m.) from your utility's hourly data",
    defaults: () => {
      const c = capitalDefaults();
      const t = touSharedDefaults();
      return {
        usable_kwh: A("usable_kwh", "Usable battery capacity", 13.5, "kWh", TAGS.DEFAULT_SOURCED,
          S("Tesla Powerwall 3 usable capacity (EnergySage)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/", null,
            "EnergySage's product review of the Tesla Powerwall 3, the most commonly installed home battery. EnergySage is a national solar/storage marketplace; its reviews combine manufacturer specifications with real installer-quote data from its own platform."),
          "How much energy the battery can actually store and give back, in kilowatt-hours. It sets both the price (batteries are sold by capacity) and what an outage looks like — 13.5 kWh runs a typical home's essentials for roughly a day. More capacity costs proportionally more; it doesn't improve the bill economics."),
        installed_cost_per_kwh: A("installed_cost_per_kwh", "Installed battery cost per kWh", 998, "$/kWh", TAGS.DEFAULT_SOURCED,
          S("EnergySage Marketplace average — $998/kWh (2026)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/", "~$13,473 all-in for a 13.5 kWh Powerwall 3.", WHAT_ENERGYSAGE),
          "The installed price per kilowatt-hour of storage — hardware plus electrician, permits, and commissioning. Multiply by capacity for the sticker price. This number is what makes battery economics hard: at ~$1,000/kWh, a whole-home battery costs as much as a used car, while its yearly bill savings in Maine are close to zero."),
        federal_itc_pct: A("federal_itc_pct", "Federal credit reaching you (owner-bought 0; lease/PPA pass-through unknown)", 0.0, "fraction", TAGS.DEFAULT_SOURCED,
          S("25D EXPIRED Dec 31, 2025 (owner-bought: $0); 48E survives via lease/PPA", "https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
            "48E covers standalone storage begun before 2033 (FEOC content rules apply: ≥55% non-PFE in 2026); the installer claims it on Form 3468 — the homeowner never files Form 5695. Pass-through % to a Maine homeowner is unsourced.", WHAT_REWIRING),
          "The share of the battery's cost that federal incentives actually return to you. This is now a two-path financing switch, not a single rate. Owner-bought (cash or loan): the 30% residential credit (25D) expired December 31, 2025, so a 2026 buyer gets zero — the default. Lease/PPA (third-party-owned): the commercial 48E credit survives for standalone storage — the provider claims up to 30% and passes some of it through as lower payments — but how much reaches a Maine homeowner is an open research question, so don't pencil in a number you weren't quoted. Set this above 0 only to model a pass-through you can verify in an actual lease offer."),
        annual_bill_savings: A("annual_bill_savings", "Annual electricity-bill savings from the battery (outside the TOU mode)", 0.0, "$", TAGS.DEFAULT_SOURCED,
          S("Modeling choice: ~$0 on the default flat rate (arbitrage lives in the TOU mode)", null,
            "CMP's optional Rate TOU (eff. Jul 1, 2026) is a genuine but conditional, delivery-only arbitrage — modeled by the off-by-default tou_enrolled mode, not by this number. On the flat rate there is no spread; NEB already credits rooftop export at retail.",
            "A modeling choice this calculator states openly: with a flat rate and retail-value NEB credits, there is no price spread for a battery to earn outside the optional TOU rate. The reasoning is in the note; the TOU rates themselves are sourced on the arbitrage assumptions."),
          "Money the battery saves on the bill itself each year, outside the TOU arbitrage modeled separately. On the default flat rate (CMP Rate A: delivery AND supply both flat) there is no intraday price spread, and rooftop export is already credited at retail value under net energy billing — so the honest default is $0. Residential TOU arbitrage DOES exist, but it's conditional and delivery-only, so it lives in its own switch (tou_enrolled) rather than being buried here."),
        tou_enrolled: A("tou_enrolled", "Enrolled in the optional TOU delivery rate? (0 = no, 1 = yes)", 0.0, "0 or 1", TAGS.DEFAULT_SOURCED,
          S("Modeling choice: TOU arbitrage is an optional, off-by-default mode", null,
            "Enrollment is a choice, not the default — and CMP's spread is fat but conditional (needs ~86% off-peak), so the mode ships off. Versant's Home Eco is thin but nearly risk-free.", WHAT_MODELING_CHOICE),
          "Whether you've switched from the default flat delivery rate to the optional time-of-use rate (CMP 'Rate TOU', Versant 'Home Eco'). Off by default because most homes are on the flat rate, where a battery has nothing to arbitrage. Turn it on (set to 1) and the battery faces the three-case TOU math: under a 15.8% on-peak share the rate alone wins and the battery adds gravy; over it, the battery has to rescue the enrollment from the 3.6× on-peak penalty."),
        annual_usage_kwh: t.annual_usage_kwh,
        on_peak_share: t.on_peak_share,
        residual_coverage: t.residual_coverage,
        enrollment_discount_per_kwh: t.enrollment_discount_per_kwh,
        residual_penalty_per_kwh: t.residual_penalty_per_kwh,
        resilience_value_per_year: A("resilience_value_per_year", "What backup power during outages is worth to you per year", 200, "$", TAGS.UNSOURCED, null,
          "What not losing power in an outage is worth to YOU each year — the real reason Mainers buy batteries. It's inherently personal: spoiled food, a sump pump that must run, medical equipment, working from home through an ice storm. It's kept separate from bill savings so the pure-economics verdict stays honest. No researched number exists; $200 is a placeholder meant to make you think about your own answer."),
        annual_degradation: A("annual_degradation", "Annual battery capacity fade", 0.03, "fraction", TAGS.DEFAULT_SOURCED,
          S("Modeling choice: ~3%/yr LFP capacity fade (1–4%/yr range)", null,
            "Bracketed by the LFP literature and the 70%@10yr warranty point; a measured Powerwall 3 curve (plus a Maine cold-climate adjustment) would replace it.", WHAT_MODELING_CHOICE),
          "How much usable capacity the battery loses each year as its cells age. LFP chemistry (Powerwall 3) fades roughly 1–4% a year, and the fade continues past the warranty's 70%-at-10-years floor. The model trims each future year's value by this rate, the battery equivalent of panel degradation. Deep-cycling daily to chase TOU savings pushes you toward the fast end."),
        warranty_years: A("warranty_years", "Warranty term (the guarantee floor — not the expected life)", 10, "years", TAGS.DEFAULT_SOURCED,
          S("Tesla Powerwall warranty — 10 years, 70% capacity retention", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
            "Unlimited cycles for solar use — a signal Tesla doesn't expect death at year 10. The warranty is the risk floor; the horizon models the expected life.",
            "The manufacturer's own warranty terms, as reported in EnergySage's marketplace review — the industry's definition of the battery's guaranteed (not expected) life."),
          "How long the manufacturer guarantees the battery (Tesla: 70% capacity retention at 10 years, unlimited cycles for a solar home). Like a car warranty, it's a floor, not a life expectancy — which is why the analysis horizon below is longer. This number doesn't enter the math; it's here so the risk window (years beyond warranty are on you) stays visible next to the service-life horizon the dollars are computed over."),
        opportunity_rate: c.opportunity_rate,
        horizon_years: A("horizon_years", "Analysis horizon (expected battery service life)", 13, "years", TAGS.DEFAULT_SOURCED,
          S("Expected Powerwall 3 service life ~12–15 yr (default 13); warranty is 10", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/",
            "Warranty (10 yr, 70% retention) ≠ life. Model the ~13-yr expected life with continued ~3%/yr fade; keep warranty_years as the separate risk window.",
            "A modeling choice anchored to the manufacturer's warranty terms and LFP-lifespan reporting (EnergySage review plus battery-life explainers): the warranty floor is 10 years, the reported expected service life ~12–15."),
          "How many years of battery value the comparison counts — set to the expected service life of an LFP battery like the Powerwall 3 (~12–15 years, default 13), not the 10-year warranty, which is a guarantee floor the way a car warranty is. Still much shorter than the 25-year panel horizon. Honest caveat: with ~$0 bill savings the extra years add ~$0 each, so the longer horizon nudges NPV without flipping the resilience-not-ROI verdict — its real effect is that you shouldn't budget a year-10 replacement."),
      };
    },
    run: (a) => computeBattery({
      usableKwh: a.usable_kwh.value, installedCostPerKwh: a.installed_cost_per_kwh.value, federalItcPct: a.federal_itc_pct.value,
      annualBillSavings: a.annual_bill_savings.value, resilienceValuePerYear: a.resilience_value_per_year.value,
      horizonYears: a.horizon_years.value, opportunityRate: a.opportunity_rate.value,
      annualDegradation: a.annual_degradation.value, touEnrolled: !!a.tou_enrolled.value,
      annualUsageKwh: a.annual_usage_kwh.value, onPeakShare: a.on_peak_share.value,
      residualCoverage: a.residual_coverage.value,
      enrollmentDiscountPerKwh: a.enrollment_discount_per_kwh.value,
      residualPenaltyPerKwh: a.residual_penalty_per_kwh.value,
    }),
  },
  "plugin-battery": {
    label: "Plug-In / DIY Battery",
    blurb: "A buy-and-plug battery for a home that already uses little power on weekday evenings. Under a 15.8% on-peak share, switching to CMP's optional TOU rate lowers your bill on its own — and the battery adds arbitrage on top, earning the 3.6× on-peak penalty back on every kWh it shifts off-peak. Homes above that line need a different calculation, which isn't built yet.",
    describe: (a) => {
      const threshold = a.enrollment_discount_per_kwh.value / a.residual_penalty_per_kwh.value;
      return a.on_peak_share.value < threshold
        ? `a plug-in TOU battery: you're under the ${(threshold * 100).toFixed(1)}% on-peak line, so switching to the TOU rate already lowers your bill — and every kWh the battery shifts off-peak is arbitrage on top`
        : `a plug-in TOU battery — but at ${(a.on_peak_share.value * 100).toFixed(1)}% on-peak you're over the ${(threshold * 100).toFixed(1)}% line this option models, so it can't answer for you yet`;
    },
    followup: "your on-peak share — the fraction of your usage on weekdays 5–9 p.m., from your utility's hourly download — it decides whether this option applies to you at all",
    example: "I use 6,600 kWh a year and only 12% of it is on weekday evenings — is a plug-in battery worth it?",
    defaults: () => {
      const c = capitalDefaults();
      return {
        ...touSharedDefaults(),
        // Overrides the shared 0.25 so the shipped defaults describe a home this option models.
        on_peak_share: A("on_peak_share", "Share of your usage during on-peak hours (weekday 5–9 p.m.)", 0.12, "fraction", TAGS.UNSOURCED, null,
          "The fraction of your electricity used on weekdays between 5 and 9 p.m. — the number that decides whether this option applies to you at all. Under 15.8%, the TOU rate already beats the flat rate with no battery, and a plug-in battery adds arbitrage on top of that: this is the situation the calculator models. Over 15.8%, the on-peak penalty (3.6× the flat rate) means enrolling loses money until a battery rescues it — a different calculation that isn't built yet, so the calculator says so instead of guessing. Nobody can estimate this for you: download your hourly usage from your utility's website and measure it. The 12% default is only a placeholder for an off-peak-leaning home."),
        cycles_per_year: A("cycles_per_year", "Charge/discharge cycles per year (one per on-peak weekday)", 250, "cycles/yr", TAGS.DEFAULT_SOURCED,
          S("Modeling choice: 250 weekday cycles/yr (CMP on-peak is weekdays 5–9 p.m.)", null,
            "~52 weeks × 5 weekdays minus holidays. Derived from the CMP tariff's on-peak definition; the count itself is a stated modeling choice.", WHAT_MODELING_CHOICE),
          "How many times a year the battery runs its daily routine: charge off-peak, discharge through the 5–9 p.m. window. On-peak hours exist only on non-holiday weekdays, so ~250 cycles a year is the ceiling. It also sizes the battery: the kWh you want shifted per year, divided by the cycles available to shift them, is the usable capacity you need to buy."),
        value_per_usable_kwh_yr: A("value_per_usable_kwh_yr", "Arbitrage value per usable kWh of battery per year", 90.13, "$/kWh/yr", TAGS.DEFAULT_SOURCED,
          S("CMP Rate TOU arithmetic: 250 × ($0.428836 − $0.061470/0.90) ≈ $90.13", CMP_TOU_URL,
            "Exact algebra on the sourced tariff rates with a 0.90 round-trip efficiency. Break-even ≈ $901/kWh simple over 10 yr (~$633 at 7% NPV).", WHAT_CMP_TOU),
          "What one kWh of battery capacity earns per year once you're on the TOU rate: 250 weekday cycles times the on-peak price avoided, net of the ~10% round-trip charging loss. Multiply by the analysis horizon and you get the break-even installed cost — about $901/kWh over 10 years — which is why a cheap plug-in unit clears it and a $998/kWh Powerwall doesn't."),
        installed_cost_per_kwh: A("installed_cost_per_kwh", "Plug-in battery cost per usable kWh", 600, "$/kWh", TAGS.UNSOURCED, null,
          "What a buy-and-plug battery costs per usable kWh. Ballparks: consumer power stations (EcoFlow, Bluetti, Anker) run roughly $500–700/kWh; a DIY LFP battery plus inverter more like $300–500/kWh. Compare whatever you find against the break-even $/kWh the calculator reports — that single comparison is the verdict. No verbatim price page has been ingested yet, so $600 is a placeholder: price a real unit before deciding."),
        federal_itc_pct: A("federal_itc_pct", "Federal tax credit on battery cost", 0.0, "fraction", TAGS.DEFAULT_SOURCED,
          S("25D expired Dec 31, 2025; no third-party-ownership path for a self-install", "https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit",
            "A 2026 buy-and-plug buyer gets $0 federal credit.", WHAT_REWIRING),
          "The share of the cost the federal government returns as a tax credit: zero. The residential credit (25D) expired December 31, 2025, and the surviving commercial path (48E) reaches homeowners only through a lease/PPA provider — which a self-installed plug-in battery doesn't have. Unlike the installed battery, there's no financing structure that changes this answer."),
        resilience_value_per_year: A("resilience_value_per_year", "What backup power during outages is worth to you per year", 200, "$", TAGS.UNSOURCED, null,
          "What not losing power in an outage is worth to YOU each year. A plug-in battery doubles as portable backup — fridge, phones, a sump pump through an ice storm — which for many buyers is the real reason to own one, with the TOU arbitrage as the kicker. Kept separate from the arbitrage so the pure-economics verdict stays honest. No researched number exists; $200 is a placeholder meant to make you think about your own answer."),
        opportunity_rate: c.opportunity_rate,
        horizon_years: A("horizon_years", "Analysis horizon (plug-in battery service life)", 10, "years", TAGS.DEFAULT_SOURCED,
          S("Modeling choice: 10-yr consumer power-station horizon", null,
            "A stated planning life, not a warranty citation — plug-in units typically warrant 2–5 yr; LFP cell cycle life supports ~10 at one cycle/day.", WHAT_MODELING_CHOICE),
          "How many years of value the comparison counts — a stated ~10-year service life for a consumer power station cycled daily. Shorter than the installed battery's 13-year horizon because the hardware is cheaper and the daily TOU cycling works it harder. The break-even scales directly with this: ~$901/kWh at 10 years, ~$1,172 at 13."),
      };
    },
    run: (a) => computePluginBattery({
      annualUsageKwh: a.annual_usage_kwh.value, onPeakShare: a.on_peak_share.value,
      residualCoverage: a.residual_coverage.value, installedCostPerKwh: a.installed_cost_per_kwh.value,
      cyclesPerYear: a.cycles_per_year.value,
      enrollmentDiscountPerKwh: a.enrollment_discount_per_kwh.value,
      residualPenaltyPerKwh: a.residual_penalty_per_kwh.value,
      valuePerUsableKwhYr: a.value_per_usable_kwh_yr.value, federalItcPct: a.federal_itc_pct.value,
      resilienceValuePerYear: a.resilience_value_per_year.value,
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
      annualDegradation: a.battery_annual_degradation.value, touEnrolled: !!a.battery_tou_enrolled.value,
      annualUsageKwh: a.battery_annual_usage_kwh.value, onPeakShare: a.battery_on_peak_share.value,
      residualCoverage: a.battery_residual_coverage.value,
      enrollmentDiscountPerKwh: a.battery_enrollment_discount_per_kwh.value,
      residualPenaltyPerKwh: a.battery_residual_penalty_per_kwh.value,
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
  label: "Battery + Balcony Solar",
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
  // battery worked example (tests/test_battery.py): 13-yr service life, 3%/yr fade, TOU off.
  const bt = computeBattery({ usableKwh: 13.5, installedCostPerKwh: 998, federalItcPct: 0, annualBillSavings: 0, resilienceValuePerYear: 200, horizonYears: 13, opportunityRate: 0.07, annualDegradation: 0.03, touEnrolled: false });
  if (!(close(bt.upfrontCost, 13473) && close(bt.annualSavings, 200) && bt.capital.npv < 0
        && close(bt.capital.yearly[12].savings, 200 * Math.pow(0.97, 12)))) return "battery";
  // TOU mode Case 3 (6,600 kWh, 25% on-peak, 70% coverage): arb = 383.592 - 181.84617 = 201.74583.
  const btTou = computeBattery({ usableKwh: 13.5, installedCostPerKwh: 998, federalItcPct: 0, annualBillSavings: 0, resilienceValuePerYear: 200, horizonYears: 13, opportunityRate: 0.07, annualDegradation: 0.03, touEnrolled: true, annualUsageKwh: 6600, onPeakShare: 0.25, residualCoverage: 0.7, enrollmentDiscountPerKwh: 0.058120, residualPenaltyPerKwh: 0.367366 });
  if (!(btTou.tou.case === 3 && close(btTou.touArbitrage, 201.74583, 1e-5)
        && close(btTou.annualSavings, 401.74583, 1e-5))) return "battery";

  // plugin-battery worked example (tests/test_plugin_battery.py): 6,600 kWh, 12% on-peak (under
  // the 15.8% line), 70% coverage -> arb 554.4 x 0.367366; break-even = 90.13 x 10 = $901.3/kWh.
  const pbArgs = { annualUsageKwh: 6600, onPeakShare: 0.12, residualCoverage: 0.7, installedCostPerKwh: 600, cyclesPerYear: 250, enrollmentDiscountPerKwh: 0.058120, residualPenaltyPerKwh: 0.367366, valuePerUsableKwhYr: 90.13, federalItcPct: 0, resilienceValuePerYear: 200, horizonYears: 10, opportunityRate: 0.07 };
  const pb = computePluginBattery(pbArgs);
  if (!(close(pb.usableKwhNeeded, 2.2176) && close(pb.upfrontCost, 1330.56, 1e-4)
        && close(pb.enrollmentOnlySavings, 92.638128, 1e-5)
        && close(pb.annualSavings, 403.6677104, 1e-5)
        && close(pb.breakEvenCostPerKwh, 901.3, 1e-6))) return "plugin-battery";
  // Scope guard: over the line the option refuses rather than answering from an unbuilt model.
  let pbRefused = false;
  try { computePluginBattery({ ...pbArgs, onPeakShare: 0.25 }); } catch (e) { pbRefused = true; }
  if (!pbRefused) return "plugin-battery";

  // battery+rooftop worked example (tests/test_combo.py): flat battery stream -> exact additivity.
  const btFlat = computeBattery({ usableKwh: 13.5, installedCostPerKwh: 998, federalItcPct: 0, annualBillSavings: 0, resilienceValuePerYear: 200, horizonYears: 13, opportunityRate: 0.07, annualDegradation: 0, touEnrolled: false });
  const br = computeCombo("rooftop", r, btFlat, 0);
  if (!(close(br.upfrontCost, 29698) && close(br.annualSavings, 1982)
        && close(br.capital.simplePaybackYears, 29698 / 1982, 1e-6)
        && close(br.capital.npv, r.capital.npv + btFlat.capital.npv, 1e-6))) return "battery+rooftop";
  // horizon honesty with LIVE escalation/degradation: year 14 = PV-only cashflow (battery ends at 13).
  const rLive = computeRooftop({ capacityKw: 5.5, specificYield: 1200, installedCostPerW: 2.95, federalItcPct: 0, creditValuePerKwh: 0.27, annualUsageKwh: 6600, offsetCapFraction: 1.0, horizonYears: 25, opportunityRate: 0.07, escalation: 0.03, degradation: 0.005 });
  const brLive = computeCombo("rooftop", rLive, bt, 0);
  if (!close(brLive.capital.yearly[13].savings, rLive.capital.yearly[13].savings, 1e-6)) return "battery+rooftop";

  // battery+balcony worked example: 1500 + 13473 upfront; 388.8 + 200 year-1.
  const bb = computeCombo("balcony", b, btFlat, 0);
  if (!(close(bb.upfrontCost, 14973) && close(bb.annualSavings, 588.8)
        && close(bb.capital.simplePaybackYears, 14973 / 588.8, 1e-6))) return "battery+balcony";
  return null;
}

// --- rendering -------------------------------------------------------------
const money = (x) => "$" + x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money0 = (x) => "$" + x.toLocaleString("en-US", { maximumFractionDigits: 0 });
const num = (x) => x.toLocaleString("en-US", { maximumFractionDigits: 0 });
// ONE rule for turning a fraction into a percent, used by every surface that prints one. Rounding
// rules that differ per surface are how a page ends up saying "4.5%" and "5% discount rate" about
// the same number on the same screen. Rounds to a tenth and drops a trailing ".0"; the ×1000-then-
// ÷10 order matters, because 0.07 × 100 is 7.000000000000001.
const pct = (frac) => String(Math.round(frac * 1000) / 10);
function tagClass(tag) { return tag === TAGS.UNSOURCED ? "tag tag-unsourced" : tag === TAGS.USER_PROVIDED ? "tag tag-user" : "tag tag-sourced"; }

// R4 toggle state machine. Valid states: community | battery | rooftop | balcony |
// plugin-battery | battery+rooftop | battery+balcony. Community and plugin-battery stand alone;
// rooftop+balcony is not offered; deselecting down to zero re-selects community.
let activeParts = new Set(["community"]);
let currentOption = "community";
let assumptions = OPTIONS.community.defaults();
let billEdited = false;
// Did the USER put the usage number in the box, or is the box just mirroring an option's sourced
// default? Only a user's number may override; a mirrored default must never follow you onto an
// option that would have derived usage differently (community derives it from the bill).
let usageEdited = false;

// Comparison mode: null = single-option view; otherwise the ordered option keys being compared.
// Each compared option keeps its OWN assumptions dict; the shared inputs (#bill, #annual-usage)
// drive every row live at render time — rows are recomputed views, never saved snapshots, so
// they can't go stale against each other.
let compareKeys = null;
let compareAssumptions = null;
// Which per-option ledger sections are expanded (compare mode). Kept across re-renders so an
// edit doesn't collapse the section you're editing, or a sibling you opened to read against it.
let openSections = new Set();

const inCompare = () => compareKeys !== null;

// Assumptions that describe YOUR situation rather than one option's design, so a comparison is
// only honest if every row uses the same number. While comparing, these are lifted out of the
// per-option ledgers into the shared block and fan out to every compared option on edit.
// `opportunity_rate` is the load-bearing one: NPVs computed at different discount rates aren't
// comparable at all. (`annual_usage_kwh` is shared too, but via the #annual-usage box below.)
const SHARED_KEYS = ["opportunity_rate"];

function exitCompare() { compareKeys = null; compareAssumptions = null; openSections = new Set(); }

// The dicts a shared input must write to: every compared option, or just the current one.
function activeDicts() {
  return inCompare() ? compareKeys.map((k) => compareAssumptions[k]) : [assumptions];
}

function stateKey() {
  if (activeParts.has("community")) return "community";
  if (activeParts.has("plugin-battery")) return "plugin-battery";
  const hasBattery = activeParts.has("battery");
  if (hasBattery && activeParts.has("rooftop")) return "battery+rooftop";
  if (hasBattery && activeParts.has("balcony")) return "battery+balcony";
  return activeParts.values().next().value;
}

function toggleOption(part) {
  if (part === "community" || part === "plugin-battery") {
    activeParts = new Set([part]);                   // both stand alone (no pairings offered)
  } else if (activeParts.has(part)) {
    activeParts.delete(part);
    if (activeParts.size === 0) activeParts = new Set(["community"]); // deselect-to-zero -> default
  } else {
    activeParts.delete("community");                 // capital options clear community
    activeParts.delete("plugin-battery");            // ...and the standalone plug-in battery
    if (part === "rooftop") activeParts.delete("balcony");   // rooftop+balcony not offered
    if (part === "balcony") activeParts.delete("rooftop");
    activeParts.add(part);
  }
  applyState();
}

function selectOption(key) {  // GLOBAL — the deterministic verifier's driver contract
  exitCompare();
  activeParts = new Set(key === "community" ? ["community"] : key.split("+"));
  applyState();
}

// GLOBAL (verifier contract) — enter the side-by-side comparison view over 2+ option keys.
// Every row recomputes live from the shared inputs; each compared option ALSO gets its own
// ledger section in the drawer, so any row can be refined without leaving the comparison.
function selectCompare(keys, focusKey) {
  compareKeys = keys.slice();
  compareAssumptions = {};
  for (const k of compareKeys) compareAssumptions[k] = OPTIONS[k].defaults();
  currentOption = focusKey && compareKeys.includes(focusKey) ? focusKey : compareKeys[0];
  assumptions = compareAssumptions[currentOption];
  openSections = new Set([currentOption]);
  afterStateChange();
}

// Swap which options are being compared WITHOUT discarding the edits made to the survivors —
// dropping rooftop from a three-way compare must not silently reset the battery row you tuned.
function toggleCompareKey(key) {
  const next = compareKeys.includes(key)
    ? compareKeys.filter((k) => k !== key)
    : [...compareKeys, key];
  if (next.length < 2) return selectOption(next[0] || key);  // one option isn't a comparison
  const kept = compareAssumptions;
  compareKeys = next;
  compareAssumptions = {};
  for (const k of next) compareAssumptions[k] = kept[k] || OPTIONS[k].defaults();
  if (!next.includes(currentOption)) currentOption = next[0];
  assumptions = compareAssumptions[currentOption];
  openSections = new Set([...openSections].filter((k) => next.includes(k)));
  if (!openSections.size) openSections.add(currentOption);
  afterStateChange();
}

// Enter/leave comparison from the mode switch. Entering seeds a second option so the user lands
// on an actual comparison rather than an empty picker; community is the natural comparator
// (it's the zero-capital baseline every capital option has to beat).
function setMode(mode) {
  if (mode === "compare") {
    if (inCompare()) return;
    selectCompare(currentOption === "community" ? ["community", "rooftop"] : [currentOption, "community"],
                  currentOption);
  } else {
    if (inCompare()) selectOption(currentOption);
  }
}

function applyState() {
  currentOption = stateKey();
  assumptions = OPTIONS[currentOption].defaults();
  afterStateChange();
}

// One path out of every state change: the pickers, the shared block, and the shared inputs'
// reach all follow from (compareKeys, currentOption) — never set piecemeal at each call site.
// The shared inputs are re-applied FIRST, because a state change rebuilds assumption dicts from
// defaults and your bill/usage must survive switching options.
function afterStateChange() {
  syncPickers();
  applyUsageInput();
  syncSharedInputs();
  recompute();
}

function syncPickers() {
  const cmp = inCompare();
  document.getElementById("single-picker").hidden = cmp;
  document.getElementById("compare-picker").hidden = !cmp;
  document.querySelectorAll("button.mode").forEach((btn) => {
    const on = (btn.getAttribute("data-mode") === "compare") === cmp;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
  document.querySelectorAll("button.toggle[data-part]").forEach((btn) => {
    const on = !cmp && activeParts.has(btn.getAttribute("data-part"));
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
  document.querySelectorAll("button.toggle[data-cmp-key]").forEach((btn) => {
    const on = cmp && compareKeys.includes(btn.getAttribute("data-cmp-key"));
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

// --- shared inputs ----------------------------------------------------------
// `annual_usage_kwh` is carried as an assumption by rooftop (and its combo) but as a ctx override
// by community, which derives usage from the bill. The #annual-usage box is the ONE editor for
// both readings, so it's lifted out of every ledger — see ledgerSkipKeys().
const USAGE_KEY = "annual_usage_kwh";

function usageDicts() { return activeDicts().filter((d) => d[USAGE_KEY]); }
function optionKeysOnScreen() { return inCompare() ? compareKeys : [currentOption]; }
function anyNeedsBill() { return optionKeysOnScreen().some((k) => OPTIONS[k].needsBill); }

function syncSharedInputs() {
  const cmp = inCompare();
  document.getElementById("shared-head").hidden = !cmp;
  document.getElementById("shared-note").hidden = !cmp;
  document.getElementById("bill-row").style.display = anyNeedsBill() ? "block" : "none";
  // Usage only matters where something reads it: community (bill -> usage) or a PV option
  // carrying annual_usage_kwh. Balcony and a lone battery ignore it — don't ask for it.
  document.getElementById("usage-row").style.display =
    anyNeedsBill() || usageDicts().length ? "block" : "none";
  syncUsageBox();
  renderSharedAssumptions();
}

// Show what's actually in force: where an option carries annual_usage_kwh, the box mirrors that
// assumption — tag, source and all — instead of sitting empty while a sourced 6,600 kWh default
// quietly drives the answer.
function syncUsageBox() {
  syncUsageValueAndTag();
  renderUsageMeta();
}

function syncUsageValueAndTag() {
  const box = document.getElementById("annual-usage");
  const tag = document.getElementById("usage-tag");
  const a = usageDicts().map((d) => d[USAGE_KEY])[0];
  if (!a) {
    if (!usageEdited) box.value = "";     // drop a mirrored default rather than let it follow you
    box.placeholder = "estimate from bill";
    tag.hidden = true;
    return;
  }
  if (document.activeElement !== box) box.value = a.value;   // mirror; don't fight live typing
  tag.hidden = false;
  tag.textContent = a.tag;
  tag.className = tagClass(a.tag);
}

// The box's explanation only changes when the STATE does, so it's rendered on state change alone —
// rebuilding it on every keystroke would collapse the disclosure the user opened to read.
function renderUsageMeta() {
  const a = usageDicts().map((d) => d[USAGE_KEY])[0];
  document.getElementById("usage-meta").innerHTML = a
    ? `<p class="hint">${inCompare()
        ? "Drives every option in the comparison that uses your usage."
        : "The single most valuable number you can give us."}</p>` + whyHtml(a)
    : `<p class="hint">If you know it, enter it — it replaces the bill→usage estimate with your
       real number.</p>`;
}

// Cleared box (or a box that's only mirroring): every option goes back to its sourced default,
// and community goes back to deriving usage from the bill.
function resetUsageToDefaults() {
  for (const k of optionKeysOnScreen()) {
    const d = inCompare() ? compareAssumptions[k] : assumptions;
    if (d[USAGE_KEY]) d[USAGE_KEY] = OPTIONS[k].defaults()[USAGE_KEY];
  }
}

// Push the usage box into every option that carries usage as an assumption. Runs on every state
// change too, so switching or adding an option never loses the number you typed.
function applyUsageInput() {
  const raw = document.getElementById("annual-usage").value;
  if (!usageEdited || raw === "") {
    usageEdited = false;
    resetUsageToDefaults();
    return;
  }
  const v = parseFloat(raw);
  if (isNaN(v) || v < 0) return;
  for (const d of usageDicts()) applyUsageAssumption(d, v);
}

// SHARED_KEYS rendered once, above the per-option ledgers, editing every compared option at once.
function renderSharedAssumptions() {
  const host = document.getElementById("shared-assumptions");
  if (!inCompare()) { host.innerHTML = ""; return; }
  let rows = "";
  for (const key of SHARED_KEYS) {
    const a = compareKeys.map((k) => compareAssumptions[k][key]).find(Boolean);
    if (a) rows += assumptionRowHtml(key, a, { shared: true });
  }
  host.innerHTML = rows ? `<div class="assumptions">${rows}</div>` : "";
  wireAssumptionInputs(host);
}

function readCtx() {
  const billRaw = document.getElementById("bill").value;
  const bill = billRaw === "" ? DEFAULT_MONTHLY_BILL : parseFloat(billRaw);
  const usageRaw = document.getElementById("annual-usage").value;
  return { bill, annualUsage: usageRaw ? parseFloat(usageRaw) : null };
}

// --- state <-> text sync (R4/R5) and the scenario URL (R8b) -----------------
// The page could always DESCRIBE its state — `describe()` has driven the context line all along —
// but never wrote that description BACK into the question box, so the box went stale the moment
// you refined: it still said "$150" while the headline computed something else. These functions
// close the loop in the missing direction, reusing `describe()` rather than inventing a second
// phrasing system that could drift from it.
//
// `lastGeneratedQuestion` is the EXACT string the page last authored. The box is page-owned only
// while it still equals that string; the moment the user types, the two diverge and the page
// stops overwriting (R8) — an unasked draft is never destroyed. Storing the string rather than a
// boolean "the page wrote the box" flag is load-bearing for the elision in askQuestion(): a
// boolean would also be true right after a sample-button click, and the elision would then answer
// the current view instead of the sample's question.
let lastGeneratedQuestion = null;
let questionSynced = false;    // false only before the first paint, where R4 rewrites regardless
let takeoverQuestion = false;  // an answer just landed: its sentence takes the box back over

// Assumption labels carry a full explanatory tail ("Opportunity cost — return if you invested
// the cash instead"); prose wants the head of it.
const shortLabel = (a) => (a.label || "").split(" — ")[0].split(" (")[0].trim();

function fmtAssumptionValue(a) {
  const u = a.unit || "";
  if (u === "$") return money0(a.value);
  if (u.startsWith("$/")) return "$" + a.value + u.slice(1);
  if (u === "fraction") return pct(a.value) + "%";
  return `${a.value} ${u}`.trim();
}

// The keys the tag machinery already knows the user moved off a sourced default — the same signal
// renderCompare marks rows with (✎), surfaced in prose instead. In compare mode, edits from every
// compared option, deduped by key.
function editedOnScreen() {
  const dicts = inCompare() ? compareKeys.map((k) => compareAssumptions[k]) : [assumptions];
  const seen = new Map();
  for (const d of dicts) {
    for (const [k, a] of Object.entries(d || {})) {
      if (a && a.tag === TAGS.USER_PROVIDED && !seen.has(k)) seen.set(k, a);
    }
  }
  return [...seen.values()];
}

// R5, and the reason it can coexist with "the page says too much": SILENT AT REST. With nothing
// edited this renders nothing at all — it costs pixels only when it has news, which is exactly
// when a customized estimate might otherwise be mistaken for a default one.
function editedNote() {
  const edits = editedOnScreen();
  if (!edits.length) return "";
  return ` ${edits.length} assumption${edits.length > 1 ? "s" : ""} edited from sourced defaults: `
    + edits.map((a) => shortLabel(a).toLowerCase()).join(", ") + ".";
}

// R4: the sentence the box should hold for the state on screen right now.
function questionFromState() {
  const ctx = readCtx();
  let s;
  if (inCompare()) {
    s = "Compare " + compareKeys.map((k) => OPTIONS[k].label).join(" vs ");
    if (anyNeedsBill()) s += ` on a ${money(ctx.bill)} monthly bill`;
  } else {
    s = "Estimate " + OPTIONS[currentOption].describe(assumptions, ctx);
  }
  // Community derives usage from the bill instead of carrying annual_usage_kwh as an assumption,
  // so a usage the user typed would go unsaid there; where an option DOES carry it, the edited
  // clause below already names it and repeating it would say the same number twice.
  const carriesUsage = inCompare()
    ? compareKeys.some((k) => compareAssumptions[k][USAGE_KEY])
    : !!assumptions[USAGE_KEY];
  if (usageEdited && ctx.annualUsage && !carriesUsage) {
    s += `, using ${num(ctx.annualUsage)} kWh a year`;
  }
  const edits = editedOnScreen();
  if (edits.length) {
    s += ", with " + edits.map((a) => `${shortLabel(a).toLowerCase()} at ${fmtAssumptionValue(a)}`).join("; ");
  }
  return s + ".";
}

// The generated sentence grows with every assumption you edit, and a fixed two-row box clips it —
// hiding the tail of the very state the box exists to show. Grow to fit, then scroll at a height
// where the box would start crowding out the answer.
function autosizeQuestion(qbox) {
  qbox.style.height = "auto";
  qbox.style.height = Math.min(qbox.scrollHeight, 150) + "px";
}

function syncQuestionBox() {
  const qbox = document.getElementById("question");
  if (!qbox) return;
  const cur = qbox.value.trim();
  const pageOwns = !questionSynced || takeoverQuestion || cur === "" || cur === lastGeneratedQuestion;
  const next = questionFromState();
  lastGeneratedQuestion = next;   // tracked even when the user owns the box, so the R6 elision
  takeoverQuestion = false;       // test below always compares against the CURRENT state's sentence
  if (!pageOwns) return;
  questionSynced = true;
  if (qbox.value !== next) qbox.value = next;
  autosizeQuestion(qbox);
}

// R8b: the URL is the save file — no database, no accounts. Only what the user actually changed
// is encoded (the same TAGS.USER_PROVIDED set R5 reads), so links stay short and adding an
// assumption later can't invalidate an old one.
function stateToQuery() {
  const p = new URLSearchParams();
  if (inCompare()) p.set("c", compareKeys.join(","));
  else p.set("o", currentOption);
  if (billEdited) {
    const raw = document.getElementById("bill").value;
    if (raw !== "") p.set("bill", raw);
  }
  const usageRaw = document.getElementById("annual-usage").value;
  if (usageEdited && usageRaw !== "") p.set("usage", usageRaw);
  // annual_usage_kwh is carried by `usage` above — its one editor is the shared box, so writing
  // it twice would let a link disagree with itself.
  const push = (prefix, d) => {
    for (const [k, a] of Object.entries(d || {})) {
      if (a && a.tag === TAGS.USER_PROVIDED && k !== USAGE_KEY) p.set(prefix + k, String(a.value));
    }
  };
  if (inCompare()) for (const k of compareKeys) push(`a.${k}.`, compareAssumptions[k]);
  else push("a.", assumptions);
  return p.toString();
}

function scenarioUrl() {
  const base = location.href.split("#")[0].split("?")[0];
  const q = stateToQuery();
  return q ? base + "?" + q : base;
}

function syncUrl() {
  // replaceState, not pushState — a scenario that grows the back stack on every keystroke is a
  // trap. Chrome forbids replaceState on file://, which is exactly how the verifier drives this
  // page, so a failure here must be silent: the URL is a convenience, never a dependency.
  try { history.replaceState(null, "", scenarioUrl()); } catch (e) { /* file:// — ignore */ }
}

// Read the scenario back. Unknown or malformed keys are ignored rather than fatal (the same
// fail-soft discipline as the caches): a link from a future version still opens.
function hydrateFromUrl() {
  let p;
  try { p = new URLSearchParams(location.search); } catch (e) { return false; }
  if (![...p.keys()].length) return false;

  const numParam = (name) => {
    const raw = p.get(name);
    if (raw === null || raw === "") return null;
    const v = parseFloat(raw);
    return isNaN(v) || v < 0 ? null : v;
  };

  const bill = numParam("bill");
  if (bill !== null) {
    document.getElementById("bill").value = bill;
    billEdited = true;
    const pill = document.getElementById("bill-tag");
    pill.textContent = TAGS.USER_PROVIDED; pill.className = "tag tag-user";
  }
  const usage = numParam("usage");
  if (usage !== null) {
    document.getElementById("annual-usage").value = usage;
    usageEdited = true;
  }

  // The option/compare selection rebuilds assumption dicts from defaults, so it must happen
  // BEFORE the per-assumption overrides are laid on top.
  const cmp = (p.get("c") || "").split(",").filter((k) => OPTIONS[k]);
  const one = p.get("o");
  if (cmp.length >= 2) selectCompare(cmp);
  else if (cmp.length === 1) selectOption(cmp[0]);
  else if (one && OPTIONS[one]) selectOption(one);
  else if (bill === null && usage === null) return false;   // nothing recognizable in the URL
  else selectOption(currentOption);

  for (const [name, raw] of p.entries()) {
    if (!name.startsWith("a.")) continue;
    const parts = name.slice(2).split(".");
    const key = parts.pop();
    const optKey = parts.join(".");
    const v = parseFloat(raw);
    if (isNaN(v)) continue;
    const dicts = optKey
      ? (compareAssumptions && compareAssumptions[optKey] ? [compareAssumptions[optKey]] : [])
      : [assumptions];
    for (const d of dicts) {
      if (d[key]) d[key] = { ...d[key], value: v, tag: TAGS.USER_PROVIDED, source: null };
    }
  }
  afterStateChange();   // re-render with the overrides in force (and rewrite the box from them)
  return true;
}

function showNotice(msg) {
  const n = document.getElementById("notice");
  n.textContent = msg;
  n.classList.add("show");
}
function hideNotice() { document.getElementById("notice").classList.remove("show"); }

// --- local question parsing (no LLM) ----------------------------------------
// A deliberately simple keyword/number reader used (a) whenever the agent service fails —
// unreachable, over budget, errored — so asking still ANSWERS instead of just apologizing,
// and (b) always for comparison questions, which the one-option service can't express.
// Extracted inputs are applied and surfaced in the notice, never silently dropped
// (docs/solutions: extracted inputs must be applied or surfaced).
const ALL_OPTION_KEYS = ["community", "balcony", "rooftop", "battery", "plugin-battery", "battery+rooftop", "battery+balcony"];

function parseQuestionLocally(q) {
  const s = (q || "").toLowerCase();

  // Which options are named, in the order the question names them. "Plug-in battery" (or DIY
  // battery / power station / TOU battery) is its OWN option — it must be claimed first and
  // blanked out, or the balcony probe ("plug-in") and battery probe ("batter") would both
  // misread it. Blanking with spaces keeps every later match index meaningful.
  const found = [];
  const pluginBatteryRe = /plug[\s-]?in\s+(?:der\s+|diy\s+)?batter\w*|diy\s+batter\w*|power\s*station\w*|tou\s+batter\w*/;
  const probe = (key, re, str) => { const i = str.search(re); if (i !== -1) found.push({ key, i }); };
  probe("plugin-battery", pluginBatteryRe, s);
  const s2 = s.replace(new RegExp(pluginBatteryRe.source, "g"), (m) => " ".repeat(m.length));
  probe("community", /\bcommunity\b/, s2);
  probe("balcony", /balcony|plug[\s-]?in/, s2);
  probe("rooftop", /\broof/, s2);
  probe("battery", /batter|powerwall|\bstorage\b/, s2);
  found.sort((a, b) => a.i - b.i);
  const parts = found.map((f) => f.key);

  const compareWord = /compar|\bversus\b|\bvs\b|side[\s-]by[\s-]side/.test(s);
  const compareAll = compareWord && /\ball\b|\bevery\b|\bseven\b/.test(s);

  // Usage: "550 kWh a month" -> annualized; unit-less small numbers read as monthly.
  let annualUsage = null;
  const um = s.match(/([\d,]+(?:\.\d+)?)\s*kwh(?:\s*(?:a|per|\/|each)?\s*(month|mo\b|year|yr|annually|annum))?/);
  if (um) {
    const v = parseFloat(um[1].replace(/,/g, ""));
    const unit = um[2] || "";
    annualUsage = /month|mo/.test(unit) ? v * 12 : unit ? v : v < 2000 ? v * 12 : v;
  }

  // Bill: "$150", "bill is 150"; "a year" after the number -> monthlyized.
  let bill = null;
  const bm = s.match(/\$\s*([\d,]+(?:\.\d+)?)/) || s.match(/bill\s*(?:is|of|around|about|:)?\s*([\d,]+(?:\.\d+)?)/);
  if (bm) {
    bill = parseFloat(bm[1].replace(/,/g, ""));
    const after = s.slice(bm.index + bm[0].length, bm.index + bm[0].length + 16);
    if (/(a|per)\s*(year|yr)|annually/.test(after)) bill = bill / 12;
  }

  let mode = null, keys = null;
  if (compareAll) {
    mode = "compare"; keys = ALL_OPTION_KEYS.slice();
  } else if (parts.length >= 2) {
    const pv = parts.includes("rooftop") ? "rooftop" : parts.includes("balcony") ? "balcony" : null;
    if (!compareWord && parts.length === 2 && parts.includes("battery") && pv) {
      mode = "single"; keys = ["battery+" + pv];        // "battery with rooftop" = the combo
    } else {
      mode = "compare"; keys = parts;                    // 2+ standalone mentions = compare them
    }
  } else if (parts.length === 1) {
    mode = "single"; keys = parts;
  } else if (bill != null || annualUsage != null) {
    mode = "refine"; keys = null;                        // numbers only: refine the current view
  }
  return mode ? { mode, keys, bill, annualUsage } : null;
}

// Rooftop (and its combo) carries usage as a per-option assumption rather than a shared input.
function applyUsageAssumption(dict, usage) {
  if (!dict.annual_usage_kwh) return false;
  dict.annual_usage_kwh = { ...dict.annual_usage_kwh, value: usage, tag: TAGS.USER_PROVIDED, source: null };
  return true;
}

// Apply a locally parsed question: set the shared inputs, switch the view, say what was understood.
function answerLocally(parsed, reason) {
  // The question was answered, so the answer's own generated sentence takes the box back over —
  // the box must describe what is on screen, not the phrasing that got us here.
  takeoverQuestion = true;
  const understood = [];
  if (parsed.bill != null && !isNaN(parsed.bill)) {
    document.getElementById("bill").value = parsed.bill;
    billEdited = true;
    const pill = document.getElementById("bill-tag");
    pill.textContent = TAGS.USER_PROVIDED; pill.className = "tag tag-user";
    understood.push("monthly bill " + money(parsed.bill));
  }
  if (parsed.annualUsage != null && !isNaN(parsed.annualUsage)) {
    document.getElementById("annual-usage").value = parsed.annualUsage;
    usageEdited = true;
    understood.push(num(parsed.annualUsage) + " kWh/yr usage");
  }
  // The shared inputs are set above; selecting the view re-applies them to whatever it builds.
  if (parsed.mode === "compare") {
    understood.unshift("comparing " + parsed.keys.map((k) => OPTIONS[k].label).join(" vs "));
    selectCompare(parsed.keys);
  } else if (parsed.mode === "single") {
    understood.unshift(OPTIONS[parsed.keys[0]].label);
    selectOption(parsed.keys[0]);
  } else {
    understood.unshift("keeping the current option");    // "refine": numbers only
    applyUsageInput();
    syncSharedInputs();
    recompute();
  }
  showNotice(reason + " Understood: " + understood.join("; ") + ".");
}

// Service failed: answer with the built-in mirror if the question parsed, else the classic form.
function smartFallback(parsed, reasonPrefix) {
  if (parsed) {
    return answerLocally(parsed, reasonPrefix + " answered without the agent by the page’s built-in calculator.");
  }
  fallbackToForm(reasonPrefix + " answering without the agent with the classic form below. " +
    "Open “Refine this estimate” to set the scenario by hand.");
}

// The question box: ask the local agent service; degrade to the local parser (then the form
// flow) on ANY failure — the page is fully functional with zero backend (R7).
async function askQuestion(q) {
  hideNotice();
  // R6 — Layer 1: the page WROTE this question, so it still holds the state that produced it.
  // There is nothing to interpret and nothing to route: recompute directly. No LLM, no network,
  // no latency, no spend. The match is against the exact generated string rather than a "the page
  // wrote the box" flag, so a sample-button question (which the page also writes) never lands
  // here and silently re-answers the current view instead of what it asked.
  if (lastGeneratedQuestion !== null && (q || "").trim() === lastGeneratedQuestion) {
    takeoverQuestion = true;
    recompute();
    return showNotice("Answered instantly without the agent: this page wrote that question from " +
      "your current scenario, so it already holds the state and recomputed directly — no model call.");
  }
  const parsed = parseQuestionLocally(q);
  // Comparison is a client-side live view: the agent service maps a question to ONE option,
  // so compare-intent questions skip the service and are answered by the verified mirror.
  if (parsed && parsed.mode === "compare") {
    return answerLocally(parsed, "Side-by-side comparisons are computed right here by the page’s " +
      "built-in calculator (the agent answers single-option questions).");
  }
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
    return smartFallback(parsed, "The calculator agent isn’t reachable —");
  } finally {
    clearTimeout(timer);
  }
  if (payload.error === "cap_exceeded") {
    return smartFallback(parsed, "The agent’s budget is used up for now —");
  }
  if (payload.error === "unanswerable") {
    // The agent affirmatively said it can't map this — don't second-guess it with keyword matching.
    return fallbackToForm("The agent couldn’t map that question to a Maine solar option — your question is " +
      "kept above; answering without the agent with the classic form below.");
  }
  if (payload.error) {
    return smartFallback(parsed, "The calculator agent hit an error —");
  }
  renderAgentPayload(payload);
}

// Adapt the service's CLI-shaped payload to the mirror renderer: same renderer, different data.
function renderAgentPayload(payload) {
  takeoverQuestion = true;   // answered: the box now describes the answer's scenario
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
  // Mirror the agent's own assumptions into the shared inputs (never applyUsageInput() here —
  // that would overwrite the agent's answer with this page's defaults).
  syncSharedInputs();
  const note = payload.agent && payload.agent.note ? " " + payload.agent.note : "";
  render(r, payload.followup,
    "Answered by the calculator agent — " + OPTIONS[currentOption].describe(assumptions, readCtx()) + "." + note);
}

// Set the seven-state machine to `key` without recomputing (the agent payload carries the data).
function selectOptionSilently(key) {
  exitCompare();
  activeParts = new Set(key === "community" ? ["community"] : key.split("+"));
  currentOption = stateKey();
  syncPickers();
}

function fallbackToForm(message) {
  showNotice(message);
  document.getElementById("refine").open = true;
  recompute();
}

function recompute() {
  if (compareKeys) return recomputeCompare();
  const opt = OPTIONS[currentOption];
  const ctx = readCtx();
  if (opt.needsBill && (isNaN(ctx.bill) || ctx.bill < 0)) {
    document.getElementById("result").innerHTML = "<p class='hint'>Enter a valid monthly bill (or clear the box to use the Maine average).</p>";
    document.getElementById("detail").innerHTML = "";
    return;
  }
  let r;
  try { r = opt.run(assumptions, ctx); }
  catch (e) {
    document.getElementById("result").innerHTML = `<p class='src warn'>${e.message}</p>`;
    document.getElementById("detail").innerHTML = "";
    return;
  }
  render(r);
}

// --- side-by-side comparison view -------------------------------------------
function recomputeCompare() {
  const ctx = readCtx();
  if (compareKeys.some((k) => OPTIONS[k].needsBill) && (isNaN(ctx.bill) || ctx.bill < 0)) {
    document.getElementById("result").innerHTML = "<p class='hint'>Enter a valid monthly bill (or clear the box to use the Maine average).</p>";
    document.getElementById("detail").innerHTML = "";
    return;
  }
  const rows = compareKeys.map((k) => {
    try { return { key: k, r: OPTIONS[k].run(compareAssumptions[k], ctx) }; }
    catch (e) { return { key: k, err: e.message }; }
  });
  renderCompare(rows, ctx);
}

// Clicking a table row jumps to that option's ledger — it EXPANDS the section rather than
// swapping the drawer's contents, so any section you already opened stays open beside it.
function focusCompareOption(key) {
  currentOption = key;
  assumptions = compareAssumptions[key];
  openSections.add(key);
  document.getElementById("refine").open = true;   // the ledgers live in the drawer
  recomputeCompare();
  const sec = document.querySelector(`details.opt-sec[data-sec="${key}"]`);
  if (sec) sec.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderCompare(rows, ctx) {
  let html = `<div class="headline"><p class="card-label">Side-by-side comparison — shared inputs, each option’s own ledger</p></div>`;
  html += `<div class="cmp-wrap"><table class="cmp-table"><thead><tr><th>Option</th><th>Upfront</th><th>Savings/yr</th><th>Payback</th><th>NPV</th></tr></thead><tbody>`;
  for (const row of rows) {
    const o = OPTIONS[row.key];
    const edited = Object.values(compareAssumptions[row.key]).some((a) => a.tag === TAGS.USER_PROVIDED);
    const mark = edited ? ` <span class="cmp-mark" title="some assumptions customized — click to inspect">✎</span>` : "";
    const cls = row.key === currentOption ? ` class="focus"` : "";
    html += `<tr${cls} data-cmp="${row.key}"><td class="opt-name">${o.label}${mark}</td>`;
    if (row.err) {
      html += `<td colspan="4" class="cmp-err">${row.err}</td></tr>`;
      continue;
    }
    const r = row.r;
    if (row.key === "community") {
      html += `<td>$0</td><td>${money0(r.annualSavings)}</td><td>—</td><td>—</td></tr>`;
    } else {
      const cap = r.capital;
      const pb = cap.simplePaybackYears == null ? "never" : cap.simplePaybackYears.toFixed(1) + " yr";
      const npvCls = cap.npv > 0 ? "cmp-pos" : "cmp-neg";
      html += `<td>${money0(r.upfrontCost)}</td><td>${money0(r.annualSavings)}</td><td>${pb}</td><td class="${npvCls}">${money0(cap.npv)}</td></tr>`;
    }
  }
  html += `</tbody></table></div>`;
  // Quote the rate actually in force, not the default: with R5 naming "opportunity cost" as an
  // edited assumption in this very sentence, a hardcoded "7%" would contradict itself.
  const sharedRate = compareKeys.map((k) => compareAssumptions[k].opportunity_rate).find(Boolean);
  const sharedRatePct = sharedRate ? pct(sharedRate.value) : "7";
  html += `<p class="context cmp-note">Savings are year 1. NPV converts each option’s future savings to today’s dollars at the shared opportunity rate (${sharedRatePct}%) and subtracts the upfront cost; community solar puts no capital at stake, so payback/NPV don’t apply. Every row recomputes live from the shared bill (${money(ctx.bill)}/mo) and usage — <strong>click a row</strong> to jump to its own steps and assumptions.${editedNote()}</p>`;
  html += `<button type="button" class="cmp-exit" id="cmp-exit">✕ Exit comparison — focus on ${OPTIONS[currentOption].label}</button>`;
  const el = document.getElementById("result");
  el.innerHTML = html;
  el.querySelectorAll("tr[data-cmp]").forEach((tr) => tr.addEventListener("click", () => focusCompareOption(tr.getAttribute("data-cmp"))));
  document.getElementById("cmp-exit").addEventListener("click", () => selectOption(currentOption));

  document.getElementById("tip-body").innerHTML =
    "your electricity usage in kWh — it tightens every option in this comparison at once.";

  renderCompareDetail(rows);
  syncQuestionBox();
  syncUrl();
}

// Every compared option gets its OWN ledger section — the whole point of a comparison is that you
// can refine both sides of it. Sections are collapsed by default (six full ledgers is a wall of
// numbers) but hold their open/closed state across re-renders, so editing an assumption doesn't
// slam shut the section you're working in.
function renderCompareDetail(rows) {
  const el = document.getElementById("detail");
  let html = `<p class="card-label">Refine each option — edits here move only that option’s row</p>`;
  for (const row of rows) {
    const open = openSections.has(row.key) ? " open" : "";
    const tail = row.err ? "error"
      : row.key === "community" ? `${money0(row.r.annualSavings)}/yr · $0 upfront`
      : `${money0(row.r.annualSavings)}/yr · ${money0(row.r.upfrontCost)} upfront`;
    html += `<details class="opt-sec"${open} data-sec="${row.key}">`
      + `<summary>${OPTIONS[row.key].label}<span class="sec-tail">${tail}</span></summary>`
      + `<div class="sec-body">`
      + (row.err ? `<p class="src warn">${row.err}</p>`
                 : ledgerHtml(row.r, compareAssumptions[row.key], row.key))
      + `</div></details>`;
  }
  el.innerHTML = html;
  el.querySelectorAll("details.opt-sec").forEach((d) => {
    d.addEventListener("toggle", () => {
      const key = d.getAttribute("data-sec");
      if (d.open) openSections.add(key); else openSections.delete(key);
    });
  });
  wireAssumptionInputs(el);
}

function render(r, followupText, contextText) {
  const opt = OPTIONS[currentOption];
  const ctx = readCtx();

  // Headline -> the sticky #result card, so the number stays in view while refining below.
  let head = `<div class="headline"><p class="card-label">${opt.label} — current estimate</p>`;
  if (currentOption === "community") {
    head += `<div class="big">${money(r.annualSavings)}<span>/yr saved</span></div>`;
    head += `<div class="sub">${money(r.monthlySavings)}/mo · ${(r.pctOff * 100).toFixed(1)}% off · <strong>$0 upfront capital</strong></div>`;
  } else {
    const cap = r.capital;
    const verdict = cap.npv > 0 ? "solar wins" : "the market wins";
    const pb = cap.simplePaybackYears == null ? "never" : cap.simplePaybackYears.toFixed(1) + " years";
    const ratePct = pct(cap.opportunityRate);
    head += `<div class="big">${money(r.annualSavings)}<span>/yr (year 1)</span></div>`;
    head += `<div class="sub">${money(r.upfrontCost)} upfront · <strong>payback ${pb}</strong> · NPV: ${money0(cap.npv)} (${ratePct}% discount rate) <button type="button" class="npv-what" aria-expanded="false">what’s NPV?</button></div>`;
    head += `<div class="npv-def" hidden>Net present value: all ${cap.horizonYears} years of projected savings converted into today’s dollars at the ${ratePct}% discount rate, minus the upfront cost. Above $0 means buying solar beats investing the same cash at ${ratePct}% — here, ${verdict}.</div>`;
  }
  // One small context line: the agent's answer note, or the default-bill caveat. The context
  // may quote user/agent text, so it is set via textContent, never innerHTML.
  // R5 appends which assumptions you moved off their sourced defaults — silent when none are.
  const context = (contextText
    || (currentOption === "community" && !billEdited
        ? `That ${money(ctx.bill)}/mo bill is the sourced Maine average, not yours — edit it under “Refine this estimate.”`
        : `For ${opt.describe(assumptions, ctx)}.`)) + editedNote();
  head += `<p class="context"></p></div>`;
  document.getElementById("result").innerHTML = head;
  document.querySelector("#result .context").textContent = context;
  const npvBtn = document.querySelector("#result .npv-what");
  if (npvBtn) npvBtn.addEventListener("click", () => {
    const def = document.querySelector("#result .npv-def");
    def.hidden = !def.hidden;
    npvBtn.setAttribute("aria-expanded", String(!def.hidden));
  });

  // R5: the tighter-estimate tip lives under the Ask box, phrased as something to *ask*.
  const tipBody = document.getElementById("tip-body");
  tipBody.innerHTML = followupText
    || `The most valuable thing you could tell us: ${opt.followup}.`
      + (opt.example ? ` For example: <span class="eg">“${opt.example}”</span>` : "");

  renderDetail(r);
  // Last, so the box and the URL describe what was just rendered rather than what preceded it.
  syncQuestionBox();
  syncUrl();
}

// Keys a ledger must NOT render, because a shared input above is already their one editor.
function ledgerSkipKeys() { return inCompare() ? [...SHARED_KEYS, USAGE_KEY] : [USAGE_KEY]; }

// Steps + assumptions -> #detail inside the refine drawer (single-option view).
function renderDetail(r) {
  const el = document.getElementById("detail");
  el.innerHTML = ledgerHtml(r, assumptions, currentOption);
  wireAssumptionInputs(el);
}

// One option's ledger: its calculation chain, then its own assumptions. Takes the option and its
// dict explicitly (never the globals) so the compare view can render one per row.
function ledgerHtml(r, a, optionKey) {
  let html = `<h3>How we got there</h3><ol class="steps">`;
  for (const s of r.steps) {
    const shown = s.unit.startsWith("$") ? `${money(s.value)} <span class="unit">${s.unit}</span>` : `${num(s.value)} <span class="unit">${s.unit}</span>`;
    html += `<li><div class="step-label">${s.label}</div><code>${s.formula}</code><div class="step-val">= ${shown}</div></li>`;
  }
  if (optionKey !== "community") {
    const cap = r.capital;
    html += `<li><div class="step-label">Capital verdict (vs. ${pct(cap.opportunityRate)}% opportunity cost)</div><code>NPV = −upfront + Σ savings_t ÷ (1+r)^t</code><div class="step-val">= ${money0(cap.npv)} <span class="unit">${cap.npv > 0 ? "solar wins" : "market wins"}, ${cap.horizonYears}-yr horizon</span></div></li>`;
  }
  html += `</ol>`;

  const skip = ledgerSkipKeys();
  const lifted = Object.keys(a).filter((k) => skip.includes(k));
  html += `<h3>Assumptions <span class="hint">(edit any to refine — expand a row for what it means)</span></h3>`;
  if (lifted.length) {
    // Lead with WHERE, then list: an assumption's label can itself contain an em dash, so a
    // "<label> and <label> — these describe…" sentence turns into a run-on.
    const where = inCompare()
      ? "Edited once under <strong>Shared inputs</strong> above, where a change moves every option at once"
      : "Edited in the box above";
    html += `<p class="hint" style="margin:-4px 0 10px">${where}, because
      ${lifted.length > 1 ? "they describe" : "it describes"} your situation rather than this
      option: ${lifted.map((k) => a[k].label).join("; ")}.</p>`;
  }
  html += `<div class="assumptions">`;
  for (const key of Object.keys(a)) {
    if (skip.includes(key)) continue;
    html += assumptionRowHtml(key, a[key], { opt: optionKey });
  }
  return html + `</div>`;
}

// Spinner increment for an assumption's number input. `step="any"` made the arrows move by 1,
// which is meaningless on a 0.005 degradation rate and a rounding error on a $1,200 kit. A click
// should be a nudge at the scale the number lives at: whole years, a percentage point on a
// fraction, ten dollars on a dollar figure, otherwise ~1% of the value snapped to 0.01/0.1/1/10.
// Unit alone can't decide it — "$/kWh" is both 0.27 (a retail rate) and 998 (installed battery
// cost) — so magnitude breaks the tie.
function stepFor(a) {
  const u = (a.unit || "").toLowerCase();
  const v = Math.abs(Number(a.value)) || 0;
  if (u === "years") return 1;
  if (u === "fraction") return v > 0 && v < 0.02 ? 0.001 : 0.01;   // 0.5%/yr degradation needs finer
  if (u === "$" || u === "$/yr") return 10;                        // incl. defaults of 0, where magnitude says nothing
  if (v >= 100) return 10;
  if (v >= 10) return 1;
  if (v >= 1) return 0.1;
  return 0.01;
}

// One editable assumption row. `where` decides which dict an edit lands in: {opt} = that option
// only; {shared:true} = every option on screen that carries the key.
function assumptionRowHtml(key, a, where) {
  const target = where.shared ? ` data-shared="1"` : ` data-opt="${where.opt}"`;
  let html = `<div class="assumption"><label>${a.label}</label>`;
  html += `<div class="arow"><input type="number" step="${stepFor(a)}" min="0" data-key="${key}"${target} value="${a.value}"> <span class="unit">${a.unit}</span> <span class="${tagClass(a.tag)}">${a.tag}</span></div>`;
  if (!a.source && a.tag === TAGS.UNSOURCED) {
    html += `<div class="src warn">no source yet — don't treat this number as established fact</div>`;
  }
  return html + whyHtml(a) + `</div>`;
}

// The "what this means / where it came from" disclosure. Every surface that shows an assumption
// shows this too — a number without its provenance is exactly what this tool exists not to be.
function whyHtml(a) {
  if (!a.explain && !a.source) return "";
  let html = `<details class="why"><summary>What this means</summary><div class="deep">`;
  if (a.explain) html += `<p>${a.explain}</p>`;
  if (a.source) {
    const cite = a.source.url ? `<a href="${a.source.url}" target="_blank" rel="noopener">${a.source.title}</a>` : a.source.title;
    html += `<p class="src">source: ${cite}${a.source.note ? ` — ${a.source.note}` : ""}</p>`;
    if (a.source.what_is_it) html += `<p class="src">what the source is: ${a.source.what_is_it}</p>`;
  } else if (a.tag === TAGS.UNSOURCED) {
    html += `<p class="src warn">This number is a placeholder awaiting research — treat it as a question, not an answer.</p>`;
  }
  return html + `</div></details>`;
}

function wireAssumptionInputs(root) {
  root.querySelectorAll("input[data-key]").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const key = e.target.getAttribute("data-key");
      const v = parseFloat(e.target.value);
      if (isNaN(v)) return;
      const opt = e.target.getAttribute("data-opt");
      const dicts = e.target.hasAttribute("data-shared")
        ? activeDicts().filter((d) => d[key])          // shared: move every row at once
        : [opt && compareAssumptions ? compareAssumptions[opt] : assumptions];
      for (const d of dicts) d[key] = { ...d[key], value: v, tag: TAGS.USER_PROVIDED, source: null };
      if (key === "default_monthly_bill") {
        // Agent payloads include this row; the computed bill lives in the #bill input — keep
        // them in lockstep so editing the row actually changes the result.
        document.getElementById("bill").value = v;
        billEdited = true;
        const pill = document.getElementById("bill-tag");
        pill.textContent = TAGS.USER_PROVIDED; pill.className = "tag tag-user";
      }
      recompute();
      // Retag in place rather than re-rendering the block: a rebuild would collapse the "what
      // this means" the user opened to decide what to type.
      const pill = e.target.closest(".arow").querySelector(".tag");
      pill.textContent = TAGS.USER_PROVIDED;
      pill.className = tagClass(TAGS.USER_PROVIDED);
    });
  });
}

window.addEventListener("DOMContentLoaded", () => {
  const bigRedBanner = (msg) => {
    let b = document.getElementById("parity-banner");
    if (!b) { b = document.createElement("div"); document.body.prepend(b); }
    b.style.cssText = "display:block;background:#f5e4d4;color:#a8481c;border:1.5px solid #e2bd99;border-left:4px solid #a8481c;border-radius:10px;padding:12px 16px;margin:12px;font-weight:500;";
    b.textContent = msg;
  };

  try {
    const failed = verifyAll();
    if (failed) throw new Error(`self-check failed for the ${failed} option`);
  } catch (e) {
    bigRedBanner(`⚠ Formula self-check FAILED (${e.message}) — the web formula diverged from the verified Python worked example. Do not trust these numbers; use the Python CLI/tests.`);
  }

  // Fail LOUDLY if the page skeleton and this script are out of sync (e.g. a cached app.js
  // served with a newer index.html) — a silent init error would leave the estimate blank.
  try {
    initPage();
  } catch (e) {
    bigRedBanner(`⚠ The page failed to load (${e.message}). Hard-refresh (Ctrl+Shift+R / Ctrl+F5) — a cached copy of the calculator script may be out of sync with the page. If this persists, use the Python CLI.`);
    throw e;
  }
});

function initPage() {
  // question flow
  const qbox = document.getElementById("question");
  document.getElementById("ask").addEventListener("click", () => askQuestion(qbox.value));
  qbox.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askQuestion(qbox.value); } });
  qbox.addEventListener("input", () => autosizeQuestion(qbox));   // a typed draft grows too
  autosizeQuestion(qbox);
  document.querySelectorAll("button.sample").forEach((btn) => {
    btn.addEventListener("click", () => { qbox.value = btn.textContent.trim(); askQuestion(qbox.value); });
  });

  // refine flow: one option, or several side by side
  document.querySelectorAll("button.mode").forEach((btn) => {
    btn.addEventListener("click", () => setMode(btn.getAttribute("data-mode")));
  });
  document.querySelectorAll("button.toggle[data-part]").forEach((btn) => {
    btn.addEventListener("click", () => toggleOption(btn.getAttribute("data-part")));
  });

  // The compare picker is built from the registry, so all seven states are reachable WITHOUT the
  // question box — including the two combos, which the single-option toggles can only reach as
  // a pairing. This is the click-only answer to "compare community solar to balcony solar".
  const cmpHost = document.getElementById("compare-toggles");
  cmpHost.innerHTML = ALL_OPTION_KEYS.map((k) =>
    `<button class="toggle" type="button" data-cmp-key="${k}" aria-pressed="false">${OPTIONS[k].label}</button>`).join("");
  cmpHost.querySelectorAll("button[data-cmp-key]").forEach((btn) => {
    btn.addEventListener("click", () => toggleCompareKey(btn.getAttribute("data-cmp-key")));
  });

  const billInput = document.getElementById("bill");
  billInput.addEventListener("input", () => {
    billEdited = billInput.value !== "" && parseFloat(billInput.value) !== DEFAULT_MONTHLY_BILL;
    const pill = document.getElementById("bill-tag");
    pill.textContent = billEdited ? TAGS.USER_PROVIDED : TAGS.DEFAULT_SOURCED;
    pill.className = billEdited ? "tag tag-user" : "tag tag-sourced";
    recompute();
  });
  const usageInput = document.getElementById("annual-usage");
  usageInput.addEventListener("input", () => {
    usageEdited = usageInput.value !== "";
    applyUsageInput();
    recompute();
    syncUsageValueAndTag();   // retag; the box itself is left alone while it has focus
  });
  // On blur, show what's actually in force — clearing the box falls back to a sourced default
  // rather than to nothing, so the box must say so instead of sitting misleadingly empty.
  usageInput.addEventListener("change", () => syncUsageValueAndTag());
  document.getElementById("reset").addEventListener("click", () => {
    if (inCompare()) {
      compareAssumptions = {};
      for (const k of compareKeys) compareAssumptions[k] = OPTIONS[k].defaults();
      assumptions = compareAssumptions[currentOption];
    } else {
      assumptions = OPTIONS[currentOption].defaults();
    }
    billInput.value = DEFAULT_MONTHLY_BILL; billEdited = false;
    usageInput.value = ""; usageEdited = false;
    const pill = document.getElementById("bill-tag");
    pill.textContent = TAGS.DEFAULT_SOURCED; pill.className = "tag tag-sourced";
    syncSharedInputs();
    recompute();
  });

  // R8b: hand the user the save file. Copying is built from state rather than location.href
  // because file:// refuses replaceState — the link must be right even where the address bar
  // can't be.
  const copyBtn = document.getElementById("copy-link");
  if (copyBtn) copyBtn.addEventListener("click", async () => {
    const url = scenarioUrl();
    try {
      await navigator.clipboard.writeText(url);
      showNotice("Link copied — it reopens this exact scenario (option, bill, usage, and every " +
        "assumption you edited).");
    } catch (e) {
      // Clipboard access is denied on file:// and without a user-gesture in some browsers; the
      // URL is still useful, so show it rather than failing.
      showNotice("Copy this link to reopen this exact scenario: " + url);
    }
  });

  // A shared scenario wins over the default landing state; otherwise R2 stands — with no user
  // input the default render is community at the sourced average Maine bill.
  if (!hydrateFromUrl()) selectOption("community");
}
