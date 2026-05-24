---
name: Solar Investment Calculator
last_updated: 2026-05-24
---

# Solar Investment Calculator Strategy

## Target problem

A Maine homeowner facing a rising CMP or Versant bill suspects solar could pay off but can't tell *whether* it's worth it or *which* option to pick. The information mostly exists — but it's scattered across many dimensions (option type, utility billing structure, usage, $/kWh, upfront cost) and has to be gathered and synthesized into a comparable ROI for what is a big, largely one-shot financial decision.

## Our approach

**Transparency.** Every assumption and calculation step is exposed and independently fact-checkable, so the user can trust the ROI rather than accept a black-box number or a biased installer quote on faith. Underneath, the model is a plain capital-allocation comparison: the savings from putting capital into solar versus the return from investing that same capital elsewhere.

## Who it's for

**Primary:** A Maine homeowner working through their own solar decision — starting with the author. The leading job is to *build and pressure-test their own mental model of the economics*; reaching a confident go / no-go and which-option decision follows from it. Helping others is a welcome bonus, not the goal.

## Key metrics

- **Formula correctness** *(active now)* — calculation outputs match hand-verified worked examples (a test suite of known cases). A change that breaks a known case is a regression.

## Tracks

### Transparent economic model

The core engine: the capital-allocation comparison (upfront cost vs. bill savings vs. opportunity cost), the Maine option models (community / balcony / rooftop / battery / combinations), and CMP/Versant billing logic — with every assumption and step exposed and fact-checkable.

_Why it serves the approach:_ it **is** the transparency — the audit trail is the product.

### Guided walkthrough interface

The "roughly how much is your monthly bill?" entry point that walks through high-level numbers, then lets the user drill into line items, tune assumptions, or leave them as footnotes.

_Why it serves the approach:_ progressive disclosure makes transparency *legible* — stay high-level or inspect every number without drowning in it.

### Agent-native foundation

Parity built in from the start: anything a human can do in the UI or model, an agent can do too — drive the UI (Playwright + Claude tools), re-run and extend the model, run the formula-correctness checks.

_Why it serves the approach:_ an agent that can independently re-run and test every exposed step is the **verification arm** of transparency — the same audit trail, automated.
