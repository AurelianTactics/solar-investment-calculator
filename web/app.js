// Community-solar POC — web UI.
//
// This JS formula is a FAITHFUL MIRROR of the Python source of truth (../src/solar_calc.py).
// It runs a self-check against the canonical worked example on load (see verifyWorkedExample);
// if the two ever diverge, a banner appears. Keep this in sync with the Python core.

const TAGS = {
  DEFAULT_SOURCED: "default (sourced)",
  USER_PROVIDED: "user-provided",
  UNSOURCED: "unsourced - pending research",
};

// Defaults mirror src/assumptions.py. As of Phase 4 the load-bearing three are sourced (CMP).
function defaultAssumptions() {
  return {
    price_per_kwh: {
      key: "price_per_kwh",
      label: "All-in residential price per kWh (CMP)",
      value: 0.306, unit: "$/kWh", tag: TAGS.DEFAULT_SOURCED,
      source: {
        title: "Maine DOE — Electricity Prices (CMP, eff. Jan 1 2026)",
        url: "https://www.maine.gov/energy/electricity-prices",
        note: "All-in avg = $168.41 / 550 kWh. Display-only in the bill-first flow; resets each Jan 1.",
      },
    },
    bill_offset_fraction: {
      key: "bill_offset_fraction",
      label: "Portion of the bill a community-solar credit offsets (CMP)",
      value: 0.82, unit: "fraction", tag: TAGS.DEFAULT_SOURCED,
      source: {
        title: "Maine OPA + Maine DOE — credit offsets per-kWh charges, not the fixed charge",
        url: "https://www.maine.gov/meopa/electricity/renewable-energy/community_solar",
        note: "(bill − fixed)/bill ≈ ($168.41 − $30.21)/$168.41 ≈ 0.82 for a 550 kWh CMP bill; rises with usage.",
      },
    },
    subscription_discount_pct: {
      key: "subscription_discount_pct",
      label: "Subscription discount on the credit value you keep as savings",
      value: 0.15, unit: "fraction", tag: TAGS.DEFAULT_SOURCED,
      source: {
        title: "Maine OPA (10–15%) + Solar Gardens (guaranteed 15% on CMP credits)",
        url: "https://www.maine.gov/meopa/electricity/renewable-energy/community_solar",
        note: "Discount on the credits, which offset ~82% of the bill → ~12% off the total bill (0.15 × 0.82).",
      },
    },
    allocation_pct: {
      key: "allocation_pct",
      label: "Share of your usage the subscription is sized to cover",
      value: 1.0, unit: "fraction", tag: TAGS.DEFAULT_SOURCED,
      source: {
        title: "Modeling choice: size the subscription to your usage",
        url: null,
        note: "Stated default (100%), not an external citation. Over-subscribing wastes credits because unused credits expire after 12 months.",
      },
    },
  };
}

// Mirror of solar_calc.compute().
function compute({ monthlyBill, pricePerKwh, billOffsetFraction, subscriptionDiscountPct, allocationPct = 1.0, annualUsageKwh = null }) {
  if (monthlyBill < 0) throw new Error("monthly_bill must be >= 0");
  if (pricePerKwh <= 0) throw new Error("price_per_kwh must be > 0");
  const annualSpend = monthlyBill * 12;
  const monthlyUsageKwh = monthlyBill / pricePerKwh;
  const annualUsage = annualUsageKwh != null ? annualUsageKwh : monthlyUsageKwh * 12;
  const creditValuePerKwh = pricePerKwh * billOffsetFraction;
  const creditsGenerated = annualUsage * allocationPct * creditValuePerKwh;
  const annualSavings = creditsGenerated * subscriptionDiscountPct;
  const monthlySavings = annualSavings / 12;
  const pctOff = annualSpend ? annualSavings / annualSpend : 0;
  const steps = [
    { n: 1, label: "Bill → annual spend (do-nothing baseline)", formula: "annual_spend = monthly_bill × 12", uses: [], value: annualSpend, unit: "$/yr" },
    { n: 2, label: "Bill → estimated usage", formula: "annual_usage = (monthly_bill ÷ price_per_kwh) × 12", uses: ["price_per_kwh"], value: annualUsage, unit: "kWh/yr" },
    { n: 3, label: "Usage → credits the subscription generates", formula: "credits = annual_usage × allocation_pct × (price_per_kwh × bill_offset_fraction)", uses: ["price_per_kwh", "bill_offset_fraction", "allocation_pct"], value: creditsGenerated, unit: "$/yr" },
    { n: 4, label: "Credits → savings (the discount you keep)", formula: "annual_savings = credits × subscription_discount_pct", uses: ["subscription_discount_pct"], value: annualSavings, unit: "$/yr" },
  ];
  return { annualSpend, monthlyUsageKwh, annualUsageKwh: annualUsage, creditValuePerKwh, creditsGenerated, annualSavings, monthlySavings, pctOff, capital: 0, steps };
}

// On-load parity guard against the Python worked example.
function verifyWorkedExample() {
  const r = compute({ monthlyBill: 150, pricePerKwh: 0.25, billOffsetFraction: 0.6, subscriptionDiscountPct: 0.12, allocationPct: 1.0 });
  const close = (a, b) => Math.abs(a - b) < 1e-6;
  return close(r.annualSavings, 129.6) && close(r.monthlySavings, 10.8) && close(r.pctOff, 0.072) && close(r.annualUsageKwh, 7200) && r.capital === 0;
}

const money = (x) => "$" + x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

let assumptions = defaultAssumptions();

function recompute() {
  const bill = parseFloat(document.getElementById("bill").value);
  if (isNaN(bill) || bill < 0) { document.getElementById("result").innerHTML = "<p class='hint'>Enter your approximate monthly bill above.</p>"; return; }
  const usageRaw = document.getElementById("annual-usage").value;
  const annualUsageKwh = usageRaw ? parseFloat(usageRaw) : null;
  const r = compute({
    monthlyBill: bill,
    pricePerKwh: assumptions.price_per_kwh.value,
    billOffsetFraction: assumptions.bill_offset_fraction.value,
    subscriptionDiscountPct: assumptions.subscription_discount_pct.value,
    allocationPct: assumptions.allocation_pct.value,
    annualUsageKwh,
  });
  render(bill, r);
}

function tagClass(tag) {
  if (tag === TAGS.UNSOURCED) return "tag tag-unsourced";
  if (tag === TAGS.USER_PROVIDED) return "tag tag-user";
  return "tag tag-sourced";
}

function render(bill, r) {
  const el = document.getElementById("result");
  let html = "";
  html += `<div class="headline">`;
  html += `<div class="big">${money(r.annualSavings)}<span>/yr saved</span></div>`;
  html += `<div class="sub">${money(r.monthlySavings)}/mo · ${(r.pctOff * 100).toFixed(1)}% off · <strong>$0 upfront capital</strong></div>`;
  html += `</div>`;

  html += `<h3>How we got there</h3><ol class="steps">`;
  for (const s of r.steps) {
    const val = s.unit.startsWith("$") ? money(s.value) : s.value.toLocaleString("en-US", { maximumFractionDigits: 0 }) + " kWh";
    html += `<li><div class="step-label">${s.label}</div><code>${s.formula}</code><div class="step-val">= ${val} <span class="unit">${s.unit}</span></div></li>`;
  }
  html += `</ol>`;

  html += `<h3>Assumptions <span class="hint">(edit any to refine — it recomputes instantly)</span></h3>`;
  html += `<div class="assumptions">`;
  for (const key of ["price_per_kwh", "bill_offset_fraction", "subscription_discount_pct", "allocation_pct"]) {
    const a = assumptions[key];
    html += `<div class="assumption">`;
    html += `<label>${a.label}</label>`;
    html += `<div class="arow"><input type="number" step="0.01" min="0" data-key="${key}" value="${a.value}"> <span class="unit">${a.unit}</span> <span class="${tagClass(a.tag)}">${a.tag}</span></div>`;
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
      if (!isNaN(v)) {
        assumptions[key] = { ...assumptions[key], value: v, tag: TAGS.USER_PROVIDED, source: null };
        recompute();
      }
    });
  });
}

window.addEventListener("DOMContentLoaded", () => {
  if (!verifyWorkedExample()) {
    const b = document.getElementById("parity-banner");
    b.style.display = "block";
    b.textContent = "⚠ Formula self-check FAILED — the web formula diverged from the verified worked example. Do not trust these numbers.";
  }
  document.getElementById("bill").addEventListener("input", recompute);
  document.getElementById("annual-usage").addEventListener("input", recompute);
  document.getElementById("reset").addEventListener("click", () => { assumptions = defaultAssumptions(); recompute(); });
  recompute();
});
