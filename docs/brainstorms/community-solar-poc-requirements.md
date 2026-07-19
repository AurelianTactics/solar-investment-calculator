---
date: 2026-05-24
topic: community-solar-poc
---

# Phase 1 — Community Solar POC Plan

## Summary

This is the Phase 1 planning artifact for the Solar Investment Calculator. It specifies a community-solar proof-of-concept that turns a monthly electricity bill into an estimated annual savings and % off, with every number shown as a labeled, editable, sourced assumption — and frames the phased roadmap so the Phase 2 research brief and Phase 3 build inherit a clean handoff. Planning only; no code.

> **Status update (2026-06-14): Phases 2–4 have landed — this POC is built, sourced, and shipping.**
> All three Outstanding Questions below are now answered by Phase 2 research and folded into the POC
> defaults; see [`docs/plans/2026-05-25-phase-4-research-integration.md`](../plans/2026-05-25-phase-4-research-integration.md)
> for the integration record and `src/assumptions.py` / `web/app.js` for the shipped, cited values.
> The bill-only default ($150 CMP) now estimates **$221.40/yr (12.3% off, $0 capital)**. This doc is
> kept as the Phase 1 artifact of record; the Outstanding Questions and Dependencies sections are
> updated in place to mark what research resolved. Community solar became the foundation the three
> capital options (balcony / rooftop / battery) were then stacked on.

---

## Problem Frame

A Maine homeowner — starting with the author — facing a rising CMP or Versant bill can't easily tell whether a solar move pays off or which option to pick. The information mostly exists but is scattered across utility billing, usage, rates, and option types, and has to be synthesized into a comparable, trustworthy number (see `STRATEGY.md`).

Rather than build the whole tool at once, the author is sequencing the work in phases so that research and build never block on guesses about each other:

- **Phase 0 — Setup:** `git init`, `CLAUDE.md`, `BACKLOG.md`, scaffolding.
- **Phase 1 — This doc:** frame the problem, spec the community-solar POC.
- **Phase 2 — Research:** ideate the research and write the research-agent brief. *Owned by a separate repo plan; intentionally not detailed here.*
- **Phase 3 — Build:** implement the POC.
- **Phase 4+ — Integrate:** react to research findings and the POC, decide how they come together.

Community solar is the first option because it has the simplest capital model (near-zero upfront), so it gets to a trustworthy first number fastest and establishes the bill→usage→savings pipeline that later options reuse.

---

## Actors

- A1. **Homeowner (author first):** enters their bill, inspects and edits assumptions, reads the savings estimate and the steps behind it.
- A2. **Agent:** operates the same surface as the homeowner (enter inputs, edit assumptions, read results and steps) and runs the formula-correctness check — agent-native parity.
- A3. **Research agent (Phase 2, separate repo):** consumes the research brief seeded by this POC's open assumptions. Named here only for the handoff; out of this doc's build scope.

---

## Key Flows

- F1. **Community-solar walkthrough**
  - **Trigger:** homeowner enters their approximate monthly bill.
  - **Actors:** A1 (or A2).
  - **Steps:** enter bill → POC derives usage/spend from a stated $/kWh default → estimates the community-solar credits the subscription would generate and applies the subscription discount → shows annual and monthly $ saved and % off, with $0 capital noted → user expands any step and edits any default → result recomputes.
  - **Outcome:** the user has an estimated savings number they can trust, or knows exactly which assumption they'd need to firm up.
  - **Covered by:** R1, R3, R4, R6, R7, R9.

---

## Requirements

**Input**
- R1. The primary entry point is a single input: the approximate monthly electricity bill in dollars ("roughly how much is your monthly power bill?").
- R2. Optional refinement inputs are accepted — utility (CMP / Versant), $/kWh, the actual subscription discount % from a specific offer, and annual usage (kWh). Any input not provided falls back to a labeled default.

**Computation**
- R3. The POC converts the bill into estimated electricity usage and spend using a stated $/kWh assumption (per utility).
- R4. The POC estimates community-solar savings as a function of the credits the subscription generates and the subscription discount, measured against the do-nothing baseline (the full utility bill). Output is annual and monthly dollars saved and % off.
- R5. Community solar is framed as recurring savings, not a capital investment: the POC reports $/yr and % off and explicitly states $0 upfront capital. It does not compute payback period, NPV, or opportunity cost (those belong to the deferred capital-allocation engine).

**Transparency mechanic**
- R6. Every number used in the computation is displayed as a labeled assumption tagged `default (sourced)` or `user-provided`.
- R7. Every default is editable; editing a default recomputes the result immediately and re-tags that assumption as `user-provided`.
- R8. Each default assumption cites its source. A default with no source yet is shown tagged `unsourced — pending research`, never presented as established fact.
- R9. The walkthrough shows the calculation steps (bill → usage → credits → savings), not only the final number, so the user can follow and fact-check the rationale.

**Agent-native parity**
- R10. The POC exposes the same capabilities to an agent as to a human — entering inputs, editing assumptions, and reading the result and its steps — and the calculation is verifiable by an automated formula-correctness check (ties to `STRATEGY.md`'s active metric).

---

## Acceptance Examples

- AE1. **Covers R1, R4.** Given only a monthly bill amount, when the user submits, the POC produces an estimated annual savings and % off using labeled default assumptions for everything not provided.
- AE2. **Covers R7.** Given an estimate computed with the default $/kWh, when the user edits $/kWh to their actual rate, the savings estimate recomputes immediately and that assumption re-tags from `default (sourced)` to `user-provided`.
- AE3. **Covers R6, R8.** Given a default assumption that has no source yet, when the user inspects it, it is shown tagged `unsourced — pending research` rather than presented as fact.

---

## Success Criteria

- The author can enter their real bill (and optionally a real community-solar offer), see an estimated $/yr and % saved with $0 capital, follow every step, and either trust the number enough to act on it or identify exactly which assumption they'd need to firm up.
- The POC's output matches a hand-verified worked example for a known input set, and a change that breaks the known case is caught (formula-correctness metric).
- Phase 2 can start from this doc's list of open/unsourced assumptions without re-deriving what research is needed; Phase 3 can build without inventing the savings formula or the assumption-display behavior.

---

## Scope Boundaries

- This doc is Phase 1 planning only — it does not build the POC (that is Phase 3).
- The capital-allocation / NPV / payback engine is deferred to the rooftop iteration, where it is load-bearing.
- Other options — rooftop, balcony / plug-in, battery storage, and combinations — are later iterations.
- Bill ingestion (PDF/photo scan, line-item parsing) is backlog, not this POC.
- A separate research-bot repo, MCP server, native app, other states, and commercial use are backlog.
- The Phase 2 research brief's contents are owned by a separate repo plan; this doc only seeds the open assumptions that brief must answer.

---

## Key Decisions

- **Community solar as the first POC option:** simplest capital model, fastest path to a trustworthy first number, and it establishes the shared bill→usage→savings pipeline.
- **Defer the capital-allocation engine:** community solar has near-zero capital and does not exercise NPV/payback; that engine waits for the rooftop iteration where it matters.
- **Research as an in-repo sourced-doc brief, not a bot or second repo:** don't automate the research before the path has been walked; `STRATEGY.md` files the research repo under "not now."
- **Transparency via labeled, editable, sourced assumptions:** makes "fact-checkable" concrete, and an editable default subsumes the need for a separate "advanced input" mode in the POC.

---

## Dependencies / Assumptions

*Status: all research dependencies below resolved in Phase 2–4 (2026-06-14). Original text kept; resolution noted inline.*

- Maine community-solar credit mechanics — specifically what portion of the bill (supply vs. delivery) a Net Energy Billing credit offsets — are currently unknown and treated as an assumption pending Phase 2 research. → **Resolved:** the residential credit offsets the **per-kWh (volumetric) charges only**, never the fixed monthly charge ≈ **0.82** of a typical 550 kWh CMP bill (`bill_offset_fraction`); Maine OPA + Maine DOE.
- Typical Maine community-solar subscription discount %, any escalators, and credit rollover behavior — assumptions pending research. → **Resolved:** **15%** discount on credits (`subscription_discount_pct`; Maine OPA 10–15%, Solar Gardens guaranteed 15%); credits **expire after 12 months** (over-subscribing wastes them — `allocation_pct` sized to usage). Escalators: the common Maine model is a flat guaranteed discount; other providers' escalators are unsourced and not modeled (the POC is single-year, so no input binds yet).
- $/kWh for CMP and Versant — assumptions pending research. The POC supports both utilities; the author's own utility is used for the first concrete numbers. → **Resolved (CMP shipped):** CMP all-in **$0.306/kWh** (`price_per_kwh`; Maine DOE, eff. Jan 1 2026), volumetric ≈ $0.27. Versant numbers exist in research (`../solar-investment-research/wiki/utilities/versant-rates.md`, offset ≈ 0.87–0.88) but are not the shipped default — a utility selector is the clean next enhancement (see Open follow-ups).
- A trustworthy Phase 3 number depends on Phase 2 landing first — consistent with the chosen phase order (2 before 3). → **Held:** Phase 2 landed first, then Phases 3–4; the shipped default is fully sourced.

---

## Outstanding Questions

### Resolved by Phase 2 research (folded into the POC defaults, 2026-06-14)

- [x] [Affects R4] What portion of a Maine bill (supply vs. delivery) a community-solar Net Energy Billing credit actually offsets. → **Per-kWh (volumetric) charges only, not the fixed monthly charge** ≈ 0.82 for a typical 550 kWh CMP bill, rising toward 1.0 for heavy users (usage-dependent, not a true constant). Source: Maine OPA + Maine DOE. Surprise worth surfacing: a "15% discount" nets only ~12% off the *total* bill because the fixed charge is never offset.
- [x] [Affects R3] The $/kWh figures to use for CMP and Versant. → **CMP all-in $0.306/kWh** (volumetric ≈ $0.27), Maine DOE (eff. Jan 1 2026). Versant ≈ available in research but not shipped as default. Note: starting from a bill, $/kWh cancels out of the savings figure (it only sets the usage shown) — the load-bearing inputs were the offset fraction and the discount.
- [x] [Affects R4] Typical subscription discount %, escalator terms, and month-to-month credit rollover behavior. → **15% on credits** (OPA 10–15%; Solar Gardens guaranteed 15%); **credits expire after 12 months**; escalators not modeled (single-year POC, common model is flat).

*These three fed the Phase 2 research brief and are now `default (sourced)` in `src/assumptions.py` + `web/app.js`. Full integration record: `docs/plans/2026-05-25-phase-4-research-integration.md`.*

### Open follow-ups (carried to the backlog — none block the POC)

- **Versant utility selector** — research has CMP *and* Versant rates / offset fractions; the POC ships CMP defaults and lets a Versant user edit. A utility dropdown is the clean next enhancement.
- **Annual rate refresh** — standard-offer supply resets every Jan 1; `price_per_kwh` and the offset fraction drift. Re-pull from the research repo (which has a stale-number health-check) after each January reset.
- **Usage-derived offset fraction** — compute `bill_offset_fraction` from the user's own usage instead of the typical-bill default, since it is usage-dependent.
- **Multi-year / escalator view** — would give escalators an input to bind to; out of scope for the single-year POC.

*(The Versant/utility-mechanics line is in `docs/BACKLOG.md`; the rest are recorded here.)*
