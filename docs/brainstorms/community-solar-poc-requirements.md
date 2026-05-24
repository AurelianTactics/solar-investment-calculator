---
date: 2026-05-24
topic: community-solar-poc
---

# Phase 1 — Community Solar POC Plan

## Summary

This is the Phase 1 planning artifact for the Solar Investment Calculator. It specifies a community-solar proof-of-concept that turns a monthly electricity bill into an estimated annual savings and % off, with every number shown as a labeled, editable, sourced assumption — and frames the phased roadmap so the Phase 2 research brief and Phase 3 build inherit a clean handoff. Planning only; no code.

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

- Maine community-solar credit mechanics — specifically what portion of the bill (supply vs. delivery) a Net Energy Billing credit offsets — are currently unknown and treated as an assumption pending Phase 2 research.
- Typical Maine community-solar subscription discount %, any escalators, and credit rollover behavior — assumptions pending research.
- $/kWh for CMP and Versant — assumptions pending research. The POC supports both utilities; the author's own utility is used for the first concrete numbers.
- A trustworthy Phase 3 number depends on Phase 2 landing first — consistent with the chosen phase order (2 before 3).

---

## Outstanding Questions

### Deferred to Planning

- [Affects R4][Needs research] What portion of a Maine bill (supply vs. delivery) a community-solar Net Energy Billing credit actually offsets.
- [Affects R3][Needs research] The $/kWh figures to use for CMP and Versant.
- [Affects R4][Needs research] Typical subscription discount %, escalator terms, and month-to-month credit rollover behavior.

*These three feed the Phase 2 research brief (owned by a separate repo plan).*
