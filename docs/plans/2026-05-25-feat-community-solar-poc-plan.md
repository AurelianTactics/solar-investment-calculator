---
title: Community-Solar POC Build Plan
type: feat
status: planned
date: 2026-05-25
brainstorm: docs/brainstorms/community-solar-poc-requirements.md
---

# Community-Solar POC Build Plan

> **Stack note (post-build):** this plan specifies a JavaScript core (`*.mjs`, `node --test`). The
> build environment had no JS runtime, so the core pivoted to **Python** (`src/*.py`,
> `python3 -m unittest`) with `web/app.js` kept as a self-checking mirror. See
> `docs/solutions/best-practices/verify-runtime-before-choosing-stack.md`. The `.mjs` filenames
> below are historical; the shipped equivalents are `src/assumptions.py` / `src/solar_calc.py`.

## Overview

This plan turns the Phase 1 brainstorm (`docs/brainstorms/community-solar-poc-requirements.md`)
into a buildable Phase 3 spec. The brainstorm answered **what** the community-solar POC must do
(R1–R10, AE1–AE3); this plan answers **how**: the savings model and its arithmetic, the
assumption data model that makes every number labeled/editable/sourced, the guided-walkthrough
behavior, the worked example that anchors the formula-correctness metric, and the stack.

It also pins down which assumptions are **load-bearing for the dollar result** versus which are
display-only — this is the cleanest possible handoff to Phase 2 research, because it says exactly
which unknowns move the number the user is asked to trust.

This is still planning. No POC code lands from this doc; Phase 3 builds against it.

## Problem statement

A Maine homeowner enters one number — their monthly bill — and needs back an annual/monthly
savings figure and % off for a community-solar subscription that they can either trust enough to
act on, or trace to the single assumption they'd need to firm up. The hard part is not the
arithmetic; it is making the arithmetic *legible and sourced* so the number isn't taken on faith.

## The savings model

Community solar in Maine works through **Net Energy Billing (NEB)**: a subscriber's share of an
off-site array generates bill credits at the utility, and the subscriber buys those credits from
the provider at a discount to their face value. Net savings = the discount on the credits the
subscription generates. The POC models this transparently as a chain of steps.

### Inputs

- **Primary (R1):** `monthly_bill` ($). The only required input.
- **Optional refinements (R2):** `utility` (CMP | Versant), `price_per_kwh` ($/kWh),
  `subscription_discount_pct` (%), `annual_usage_kwh` (kWh). Any omitted input falls back to a
  labeled default.

### Assumptions (defaults, each tagged + sourced)

| Key | Meaning | Default tag at build time |
|---|---|---|
| `price_per_kwh` | All-in residential $/kWh, per utility | `unsourced — pending research` |
| `bill_offset_fraction` | Fraction of the bill an NEB credit offsets (the supply-vs-delivery question) | `unsourced — pending research` |
| `subscription_discount_pct` | Discount on credit face value the subscriber keeps | `unsourced — pending research` |
| `allocation_pct` | Share of the user's usage the subscription is sized to cover | `default (sourced)` = 100% (modeling choice, stated) |

### Computation chain (shown to the user — R9)

1. **Bill → annual spend:** `annual_spend = monthly_bill × 12`.
2. **Bill → usage:** `monthly_usage_kwh = monthly_bill ÷ price_per_kwh`;
   `annual_usage_kwh = monthly_usage_kwh × 12` (or use a user-provided `annual_usage_kwh`).
3. **Usage → credits the subscription generates:** value the NEB credit at the offsettable part
   of the rate, `credit_value_per_kwh = price_per_kwh × bill_offset_fraction`. Credits generated =
   `annual_usage_kwh × allocation_pct × credit_value_per_kwh`.
4. **Credits → savings:** the subscriber keeps the discount on those credits:
   `annual_savings = credits_generated × subscription_discount_pct`.
5. **Outputs:** `monthly_savings = annual_savings ÷ 12`; `pct_off = annual_savings ÷ annual_spend`;
   `capital = $0` (stated explicitly — R5).

### Load-bearing vs. display-only assumptions (the key handoff insight)

When the user starts from a **bill** (the primary flow), `price_per_kwh` *cancels out of the
dollar result*:

```
annual_savings = annual_usage_kwh × allocation × (price_per_kwh × offset) × discount
               = (monthly_bill ÷ price_per_kwh × 12) × allocation × price_per_kwh × offset × discount
               = monthly_bill × 12 × allocation × offset × discount
```

So for the bill-first flow:

- **Load-bearing for the dollar result:** `bill_offset_fraction`, `subscription_discount_pct`
  (and `allocation_pct`, fixed at 100% by default).
- **Display-only:** `price_per_kwh` — it only sets the *usage in kWh* shown in step 2; it does not
  move the savings number. (It becomes load-bearing only in the alternate flow where the user
  enters `annual_usage_kwh` directly instead of a bill.)

This tells Phase 2 exactly where to spend research effort: nailing the **offset fraction** and the
**typical discount** matters most for a trustworthy dollar figure; the per-utility `$/kWh` matters
for the usage display and the usage-first flow, and is the easiest for a user to override with
their own bill anyway.

### Worked example (anchors the formula-correctness metric — R10)

Fixed inputs (values are illustrative placeholders, independent of whether they're sourced — the
test asserts the *arithmetic*, not the realism of the inputs):

| Input | Value |
|---|---|
| `monthly_bill` | $150.00 |
| `price_per_kwh` | $0.25 /kWh |
| `bill_offset_fraction` | 0.60 |
| `subscription_discount_pct` | 0.12 |
| `allocation_pct` | 1.00 |

Hand-verified derivation:

- `annual_spend` = 150 × 12 = **$1,800.00**
- `monthly_usage_kwh` = 150 ÷ 0.25 = **600 kWh** → `annual_usage_kwh` = **7,200 kWh**
- `credit_value_per_kwh` = 0.25 × 0.60 = **$0.15 /kWh**
- `credits_generated` = 7,200 × 1.00 × 0.15 = **$1,080.00**
- `annual_savings` = 1,080 × 0.12 = **$129.60**
- `monthly_savings` = 129.60 ÷ 12 = **$10.80**
- `pct_off` = 129.60 ÷ 1,800 = **7.2%**
- `capital` = **$0**

This case touches every step (it exercises the usage derivation, the credit valuation, and the
discount). The test suite asserts these outputs to the cent / tenth-of-percent. A change that
breaks this case is a regression (the active metric).

A second assertion locks the cancellation property: holding bill/offset/discount fixed and
changing only `price_per_kwh` must leave `annual_savings`, `monthly_savings`, and `pct_off`
unchanged (only `annual_usage_kwh` changes).

## Assumption data model

Each assumption is a record:

```
{
  key: "bill_offset_fraction",
  label: "Portion of the bill a community-solar credit offsets",
  value: 0.60,
  unit: "fraction",        // "$/kWh" | "fraction" | "%" | "kWh" | "$"
  tag: "unsourced — pending research",   // "default (sourced)" | "user-provided" | "unsourced — pending research"
  source: null              // { title, url, note } once research lands it; null while pending
}
```

- Editing any assumption recomputes immediately and re-tags it `user-provided` (R7, AE2).
- A default with `source: null` renders as `unsourced — pending research`, never as fact (R8, AE3).
- A `default (sourced)` assumption cites a `wiki/` article in `../solar-investment-research`.

## Guided-walkthrough behavior

- Single prominent input: "roughly how much is your monthly power bill?" (R1).
- On submit, render the result (annual $ saved, monthly $ saved, % off, "$0 upfront capital") plus
  the four computation steps, each step showing the assumptions it used as labeled chips with
  their tags (R6, R9).
- Each assumption chip is expandable/editable; editing recomputes and re-tags (R7).
- Optional refinement inputs (utility, $/kWh, discount, usage) are available but never required;
  unset ones show their labeled default (R2).

## Stack

> **Stack decision update (2026-05-25, build time):** the original plan called for a JS core +
> `node --test`. The build environment has **no JS runtime** (no node/deno/bun) — only Python 3.12.
> Since the *active metric is an executable formula-correctness test*, the tested core must run in
> the available runtime. So the source-of-truth core and tests are **Python**; the website is a
> static JS **mirror** of the same formula with an on-load self-check against the canonical worked
> example. Lesson captured in `docs/solutions/`. The rest of the design (assumption data model,
> step breakdown, worked example, agent-native parity) is unchanged.

Lean, dependency-free, headlessly testable, agent-native:

- **Calculation core (source of truth):** pure Python `src/solar_calc.py` — no I/O, no framework.
  The assumption defaults live in `src/assumptions.py`. This is what the test suite asserts against
  and what an agent imports directly (agent-native parity + formula correctness).
- **Agent-native / human CLI:** `src/cli.py` — enter a bill (and optional refinements), prints the
  labeled steps, the result, and each assumption's tag + source. Runnable now (`python3 src/cli.py
  --bill 150`); this is the testable parity surface in lieu of browser automation.
- **Website:** a static `web/index.html` + `web/app.js` (vanilla JS, no build step) — the guided
  walkthrough. The JS formula is a **faithful mirror** of the Python core and runs a self-check
  against the canonical worked example on load (a cheap parity guard), surfacing a banner if the
  two ever diverge.
- **Tests:** `tests/test_solar_calc.py` via `python3 -m unittest` (stdlib only, no deps). Encodes
  the worked example and the cancellation property, and asserts the `unsourced — pending research`
  tagging behavior (AE3).
- **Why this shape:** the dollar logic is tested in isolation and reusable by an agent; the CLI and
  website are thin views over the same formula; nothing to install. Browser-driven agent parity
  (Playwright) is a later add, not POC scope.

## Implementation phases (Phase 3)

1. **Core + assumptions.** Write `src/assumptions.mjs` (the default records, all `unsourced —
   pending research` except `allocation_pct`) and `src/calc.mjs` (pure computation chain returning
   the result *and* the per-step breakdown). 
2. **Tests.** Write `test/calc.test.mjs` encoding the worked example and the cancellation
   property; `npm test` → `node --test`. Get green before any UI.
3. **UI.** `index.html` + `src/app.mjs`: bill input → result + steps → editable assumption chips.
4. **Verify the golden path + edits** against AE1/AE2/AE3 by driving the calc core (and the UI if
   a browser is available); report what was and wasn't manually exercised.

## Acceptance criteria (trace to brainstorm)

- [ ] AE1 (R1,R4): bill-only input yields annual savings + % off using labeled defaults for
  everything unprovided.
- [ ] AE2 (R7): editing `price_per_kwh` recomputes immediately and re-tags it `user-provided`
  (and, per the cancellation property, leaves the dollar result unchanged while usage updates —
  a teachable transparency moment).
- [ ] AE3 (R6,R8): an unsourced default renders `unsourced — pending research`, not as fact.
- [ ] R5: output is $/yr, $/mo, % off, with "$0 upfront capital" stated; no payback/NPV.
- [ ] R9: all four steps (bill → usage → credits → savings) are visible, not just the final number.
- [ ] R10: the worked example passes as an automated test; breaking it fails the suite.

## Open assumptions handed to Phase 2 (research repo)

These are the defaults the POC ships as `unsourced — pending research`. Phase 2
(`../solar-investment-research`) must source each before Phase 4 can re-tag it `default (sourced)`.
Ordered by leverage on the dollar result (per the load-bearing analysis above):

1. **`bill_offset_fraction`** *(load-bearing)* — what portion of a Maine residential bill (supply
   vs. delivery) a community-solar NEB credit actually offsets. [Affects R4]
2. **`subscription_discount_pct`** *(load-bearing)* — typical Maine community-solar subscription
   discount %, plus any escalator terms and month-to-month credit rollover behavior. [Affects R4]
3. **`price_per_kwh`** *(display-only for the bill-first flow; load-bearing for the usage-first
   flow)* — all-in residential $/kWh for CMP and Versant. [Affects R3]

Each, when sourced, becomes a `default (sourced)` record citing a `wiki/` article in the research
repo. Until then it stays `unsourced — pending research` and the POC says so.
