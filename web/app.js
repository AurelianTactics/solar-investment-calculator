// Solar investment calculator — web UI (all options).
//
// This JS is a FAITHFUL MIRROR of the Python source of truth (../src/*.py). On load it re-runs the
// hand-verified worked example for EVERY option (see verifyAll); if any diverges — or if this file
// throws at all — a red banner appears and tells you not to trust the numbers. No JS runtime ships
// in the build env, so the Python suite (python3 -m unittest discover -s tests) remains the metric.

const TAGS = {
  DEFAULT_SOURCED: "default (sourced)",
  USER_PROVIDED: "user-provided",
  UNSOURCED: "unsourced - pending research",
};

const S = (title, url, note) => ({ title, url: url || null, note: note || null });
const A = (key, label, value, unit, tag, source) => ({ key, label, value, unit, tag, source: source || null });

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

// --- shared capital financial assumptions (mirror of capital_assumptions()) -
function capitalDefaults() {
  return {
    opportunity_rate: A("opportunity_rate", "Opportunity cost — return if you invested the cash instead", 0.07, "fraction", TAGS.DEFAULT_SOURCED, S("Modeling choice: long-run diversified-market return (7%/yr)", null, "The hurdle solar must beat: NPV > 0 means buying beats investing the cash at this rate.")),
    electricity_escalation: A("electricity_escalation", "Annual electricity-price escalation", 0.03, "fraction", TAGS.DEFAULT_SOURCED, S("Modeling choice: conservative 3%/yr", null, "Maine's recent rises were far steeper; 3% is deliberately conservative.")),
    panel_degradation: A("panel_degradation", "Annual panel output degradation", 0.005, "fraction", TAGS.DEFAULT_SOURCED, S("Modeling choice: industry-standard ~0.5%/yr", null, "Applies to PV generation, not battery throughput.")),
    horizon_years: A("horizon_years", "Analysis horizon (system life)", 25, "years", TAGS.DEFAULT_SOURCED, S("Modeling choice: 25-year PV horizon", null, "Batteries warrant ~10 yr — that option overrides this.")),
  };
}

// --- option registry -------------------------------------------------------
const OPTIONS = {
  community: {
    label: "Community Solar",
    blurb: "Zero upfront capital. You subscribe to an off-site solar farm and buy its bill credits at a discount.",
    needsBill: true,
    defaults: () => ({
      price_per_kwh: A("price_per_kwh", "All-in residential price per kWh (CMP)", 0.306, "$/kWh", TAGS.DEFAULT_SOURCED, S("Maine DOE — Electricity Prices (CMP, eff. Jan 1 2026)", "https://www.maine.gov/energy/electricity-prices", "Display-only in the bill-first flow; resets each Jan 1.")),
      bill_offset_fraction: A("bill_offset_fraction", "Portion of the bill a community-solar credit offsets (CMP)", 0.82, "fraction", TAGS.DEFAULT_SOURCED, S("Maine OPA + Maine DOE — credit offsets per-kWh charges, not the fixed charge", "https://www.maine.gov/meopa/electricity/renewable-energy/community_solar", "(bill − fixed)/bill ≈ 0.82 for a 550 kWh CMP bill; rises with usage.")),
      subscription_discount_pct: A("subscription_discount_pct", "Subscription discount on the credit value you keep", 0.15, "fraction", TAGS.DEFAULT_SOURCED, S("Maine OPA (10–15%) + Solar Gardens (guaranteed 15% on CMP credits)", "https://www.maine.gov/meopa/electricity/renewable-energy/community_solar", "Discount on credits, which offset ~82% of the bill → ~12% off the total bill.")),
      allocation_pct: A("allocation_pct", "Share of your usage the subscription is sized to cover", 1.0, "fraction", TAGS.DEFAULT_SOURCED, S("Modeling choice: size the subscription to your usage", null, "Over-subscribing wastes credits (they expire after 12 months).")),
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
    defaults: () => ({
      capacity_kw: A("capacity_kw", "System size (plug-in)", 1.2, "kW", TAGS.DEFAULT_SOURCED, S("Maine LD 1730 — 1,200 W maximum", "https://mainemorningstar.com/2026/04/03/maine-renters-may-soon-be-able-to-access-solar-power-after-passage-of-plug-in-bill/")),
      specific_yield_kwh_per_kw: A("specific_yield_kwh_per_kw", "Annual production per kW (Maine)", 1200, "kWh/kW/yr", TAGS.DEFAULT_SOURCED, S("Maine PV yield; consistent with the OPA $388/yr anchor", "https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/")),
      self_consumption_fraction: A("self_consumption_fraction", "Share of generation used on-site (rest exported, uncompensated)", 1.0, "fraction", TAGS.DEFAULT_SOURCED, S("Modeling choice: OPA $388/yr anchor implies near-full self-consumption", null, "Plug-in earns NOTHING for exported surplus — lower this if it out-produces your daytime load.")),
      volumetric_rate_per_kwh: A("volumetric_rate_per_kwh", "Volumetric retail rate a self-consumed kWh avoids (CMP)", 0.27, "$/kWh", TAGS.DEFAULT_SOURCED, S("Maine DOE — CMP per-kWh (volumetric) charges", "https://www.maine.gov/energy/electricity-prices", "Self-consumption avoids per-kWh charges, not the fixed charge.")),
      kit_cost: A("kit_cost", "Plug-in kit cost", 1200, "$", TAGS.DEFAULT_SOURCED, S("NRCM — U.S. kits ~$1,000–1,500 (falling)", "https://www.nrcm.org/blog/what-to-know-maines-new-plug-in-solar-law/")),
      electrician_cost: A("electrician_cost", "Electrician install cost (required over 420 W)", 300, "$", TAGS.UNSOURCED, null),
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
    defaults: () => ({
      capacity_kw: A("capacity_kw", "System size (rooftop)", 5.5, "kW", TAGS.DEFAULT_SOURCED, S("Sized to a typical CMP home (~6,600 kWh/yr at ~1,200 kWh/kW)", null, "Oversizing wastes credits (they expire at 12 months).")),
      specific_yield_kwh_per_kw: A("specific_yield_kwh_per_kw", "Annual production per kW (Maine)", 1200, "kWh/kW/yr", TAGS.DEFAULT_SOURCED, S("Maine PV yield (~1,200 kWh/kW/yr)", "https://www.energysage.com/local-data/solar-panel-cost/me/")),
      installed_cost_per_w: A("installed_cost_per_w", "Installed cost per watt (Maine)", 2.95, "$/W", TAGS.DEFAULT_SOURCED, S("EnergySage — Maine average $2.95/W (May 2026), before incentives", "https://www.energysage.com/local-data/solar-panel-cost/me/")),
      federal_itc_pct: A("federal_itc_pct", "Federal tax credit on system cost", 0.0, "fraction", TAGS.DEFAULT_SOURCED, S("Federal 25D residential solar credit EXPIRED Dec 31, 2025 (was 30%)", "https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit", "A 2026 cash/loan buyer gets $0. Set to 0.30 only if installed by the 2025 deadline.")),
      credit_value_per_kwh: A("credit_value_per_kwh", "NEB credit value per kWh (volumetric, CMP)", 0.27, "$/kWh", TAGS.DEFAULT_SOURCED, S("Maine DOE — CMP per-kWh charge a NEB credit offsets", "https://www.maine.gov/energy/electricity-prices")),
      annual_usage_kwh: A("annual_usage_kwh", "Your annual electricity usage", 6600, "kWh", TAGS.DEFAULT_SOURCED, S("Typical CMP residential usage (~550 kWh/month)", null, "Caps the value of generation (NEB credits beyond usage expire).")),
      offset_cap_fraction: A("offset_cap_fraction", "Share of usage that generation is credited against", 1.0, "fraction", TAGS.DEFAULT_SOURCED, S("Modeling choice: value generation up to usage only", null, "Surplus credits expire at 12 months.")),
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
    defaults: () => {
      const c = capitalDefaults();
      return {
        usable_kwh: A("usable_kwh", "Usable battery capacity", 13.5, "kWh", TAGS.DEFAULT_SOURCED, S("Tesla Powerwall 3 usable capacity (EnergySage)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/")),
        installed_cost_per_kwh: A("installed_cost_per_kwh", "Installed battery cost per kWh", 998, "$/kWh", TAGS.DEFAULT_SOURCED, S("EnergySage Marketplace average — $998/kWh (2026)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/", "~$13,473 all-in for a 13.5 kWh Powerwall 3.")),
        federal_itc_pct: A("federal_itc_pct", "Federal tax credit on battery cost", 0.0, "fraction", TAGS.DEFAULT_SOURCED, S("Battery 25D credit EXPIRED Dec 31, 2025 (was 30%)", "https://homes.rewiringamerica.org/federal-incentives/25d-rooftop-solar-tax-credit")),
        annual_bill_savings: A("annual_bill_savings", "Annual electricity-bill savings from the battery", 0.0, "$", TAGS.DEFAULT_SOURCED, S("Modeling choice: ~$0 for a typical Maine customer", null, "No strong residential TOU arbitrage; NEB already credits export at retail.")),
        resilience_value_per_year: A("resilience_value_per_year", "What backup power during outages is worth to you per year", 200, "$", TAGS.UNSOURCED, null),
        opportunity_rate: c.opportunity_rate,
        horizon_years: A("horizon_years", "Analysis horizon (battery warranty life)", 10, "years", TAGS.DEFAULT_SOURCED, S("Tesla Powerwall warranty — 10 years (70% retention)", "https://www.energysage.com/energy-storage/best-home-batteries/tesla-powerwall-battery-complete-review/")),
      };
    },
    run: (a) => computeBattery({
      usableKwh: a.usable_kwh.value, installedCostPerKwh: a.installed_cost_per_kwh.value, federalItcPct: a.federal_itc_pct.value,
      annualBillSavings: a.annual_bill_savings.value, resilienceValuePerYear: a.resilience_value_per_year.value,
      horizonYears: a.horizon_years.value, opportunityRate: a.opportunity_rate.value,
    }),
  },
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
  return null;
}

// --- rendering -------------------------------------------------------------
const money = (x) => "$" + x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (x) => x.toLocaleString("en-US", { maximumFractionDigits: 0 });
function tagClass(tag) { return tag === TAGS.UNSOURCED ? "tag tag-unsourced" : tag === TAGS.USER_PROVIDED ? "tag tag-user" : "tag tag-sourced"; }

let currentOption = "community";
let assumptions = OPTIONS.community.defaults();

function readCtx() {
  const bill = parseFloat(document.getElementById("bill").value);
  const usageRaw = document.getElementById("annual-usage").value;
  return { bill, annualUsage: usageRaw ? parseFloat(usageRaw) : null };
}

function recompute() {
  const opt = OPTIONS[currentOption];
  const ctx = readCtx();
  if (opt.needsBill && (isNaN(ctx.bill) || ctx.bill < 0)) {
    document.getElementById("result").innerHTML = "<p class='hint'>Enter your approximate monthly bill above.</p>";
    return;
  }
  let r;
  try { r = opt.run(assumptions, ctx); }
  catch (e) { document.getElementById("result").innerHTML = `<p class='src warn'>${e.message}</p>`; return; }
  render(r);
}

function render(r) {
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

  html += `<h3>Assumptions <span class="hint">(edit any to refine — it recomputes instantly)</span></h3><div class="assumptions">`;
  for (const key of Object.keys(assumptions)) {
    const a = assumptions[key];
    html += `<div class="assumption"><label>${a.label}</label>`;
    html += `<div class="arow"><input type="number" step="any" min="0" data-key="${key}" value="${a.value}"> <span class="unit">${a.unit}</span> <span class="${tagClass(a.tag)}">${a.tag}</span></div>`;
    if (a.source) {
      const cite = a.source.url ? `<a href="${a.source.url}" target="_blank" rel="noopener">${a.source.title}</a>` : a.source.title;
      html += `<div class="src">source: ${cite}${a.source.note ? ` — ${a.source.note}` : ""}</div>`;
    } else if (a.tag === TAGS.UNSOURCED) {
      html += `<div class="src warn">no source yet — don't treat this number as established fact</div>`;
    }
    html += `</div>`;
  }
  html += `</div>`;
  el.innerHTML = html;

  el.querySelectorAll("input[data-key]").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const key = e.target.getAttribute("data-key");
      const v = parseFloat(e.target.value);
      if (!isNaN(v)) { assumptions[key] = { ...assumptions[key], value: v, tag: TAGS.USER_PROVIDED, source: null }; recompute(); }
    });
  });
}

function selectOption(key) {
  currentOption = key;
  assumptions = OPTIONS[key].defaults();
  document.getElementById("blurb").textContent = OPTIONS[key].blurb;
  document.getElementById("bill-card").style.display = OPTIONS[key].needsBill ? "block" : "none";
  recompute();
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
  const sel = document.getElementById("option");
  sel.addEventListener("change", (e) => selectOption(e.target.value));
  document.getElementById("bill").addEventListener("input", recompute);
  document.getElementById("annual-usage").addEventListener("input", recompute);
  document.getElementById("reset").addEventListener("click", () => { assumptions = OPTIONS[currentOption].defaults(); recompute(); });
  selectOption("community");
});
