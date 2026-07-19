---
title: Options Expansion — Capital Engine + Balcony, Rooftop, Battery
type: plan
status: in-progress
date: 2026-05-25
inputs:
  - STRATEGY.md
  - docs/plans/2026-05-25-phase-4-research-integration.md
  - docs/BACKLOG.md
  - ../solar-investment-research/wiki/calculator-brief/open-questions.md
---

# Options Expansion — Capital Engine + Balcony, Rooftop, Battery

Extends the community-solar POC to the three capital-bearing options on the roadmap. This is the
iteration where the **deferred capital-allocation engine becomes load-bearing** (community solar is
$0 capital, so it never exercised it). Driven by a continuation request to keep working
autonomously; the user reviews at the end.

## Branch / PR strategy (decided autonomously)

The community-solar foundation lives in open PRs (`feat/community-solar-poc`,
`feat/maine-solar-research-kb`). To keep those reviewable as a snapshot, this work goes on **new
branches stacked on them** and opens **new PRs**:

- calculator: `feat/options-expansion` (base = `feat/community-solar-poc`)
- research: `feat/solar-options-research` (base = `feat/maine-solar-research-kb`)

Stacking keeps each new PR's diff focused on the options work, not a re-show of the foundation.

## The capital-allocation engine (the new core)

STRATEGY.md frames the model as *"the savings from putting capital into solar versus the return
from investing that same capital elsewhere."* That is the engine, dormant until now.

`src/capital.py` — a pure function comparing two uses of the same upfront capital over a horizon:

- **(A) invest the cash elsewhere:** terminal wealth = `upfront_cost × (1 + opportunity_rate)^N`.
- **(B) buy solar, invest the annual savings:** each year's savings (escalating with electricity
  prices, declining with panel degradation) is invested at `opportunity_rate` to the horizon.

Reported outputs (every one a labeled, traceable number — same transparency mechanic):

- `simple_payback_years` — `upfront_cost ÷ year-1 savings` (the intuitive number).
- `lifetime_savings_nominal` — undiscounted sum of savings over the horizon.
- `npv` — present value of the savings stream minus upfront, discounted at `opportunity_rate`.
  **NPV > 0 ⟺ solar beats investing the cash.** This is the headline capital-allocation verdict.
- `net_advantage_fv` — terminal-wealth difference (B − A); same sign as NPV, in future dollars.

New shared assumptions (sourced where possible, else tagged `unsourced — pending research` or a
stated modeling choice): `opportunity_rate`, `electricity_escalation`, `panel_degradation`,
`horizon_years`, `federal_itc_pct`.

## Per-option models (each a pure module + its own tests)

Each produces `upfront_cost` and `annual_savings_year1`, then (for capital options) feeds the engine.

| Option | Module | Capital | Savings model | Headline transparency point |
|---|---|---|---|---|
| Community (existing) | `solar_calc.py` | $0 | bill × offset × discount | "15% off credits ≠ 15% off bill" |
| Balcony / plug-in | `balcony.py` | small | self-consumed generation × retail volumetric $/kWh | **legality/permitting in Maine is the real question** |
| Rooftop | `rooftop.py` | large (net of 30% ITC) | generation × NEB credit value, capped near usage | payback ~10–13 yr; NPV vs. market |
| Battery | `battery.py` | large (net of ITC) | thin arbitrage/self-consumption + user-set resilience $ | **bought for resilience, not ROI — NPV usually < 0** |

Generation model (balcony/rooftop): `annual_kwh = size_kw × maine_specific_yield × derate`.

## Research handoff (mirrors the community-solar loop)

For each option, in `../solar-investment-research` on `feat/solar-options-research`:

1. Write a research brief + open questions (the "questions I want answered") under
   `wiki/calculator-brief/` or `docs/plans/`, with an exit checklist mapping to the calculator's
   new assumptions.
2. Ingest verbatim sources (`r.jina.ai` / `raw.github`; never `WebFetch`) per `agent_docs/ingest.md`.
3. Compile wiki articles (`wiki/options/`, `wiki/mechanics/`, `wiki/caveats/`) per
   `agent_docs/compile.md`; flip exit booleans only when genuinely sourced.
4. The calculator pulls the sourced numbers and re-tags its defaults `default (sourced)`.

Key open questions to answer per option:

- **Balcony:** Is plug-in/"balcony" PV legal & interconnectable in Maine (UL 3008 / NEC 705 / utility
  rules)? Realistic system cost and Maine specific yield? Self-consumption value vs. export.
- **Rooftop:** Installed $/W in Maine; federal ITC + any Maine incentives; net-metering vs. NEB for
  residential; degradation & system life; how excess generation is credited (and the 12-month
  expiry from the community-solar research).
- **Battery:** Installed $/kWh; ITC eligibility for standalone storage; whether Maine residential
  rates offer TOU arbitrage; how to honestly represent resilience value that isn't a dollar ROI.

## Sequence

0. This plan. ✅
1. Compound-engineering pass on the existing POC — find & fix bugs/inconsistencies (e.g. the
   research handoff note still says `assumptions.mjs` after the JS→Python pivot).
2. Progressive-disclosure pass on both `CLAUDE.md` files (humanlayer principles: lean, universally
   applicable, pointers over copies). Finalize file maps after the structure settles.
3. Document how to use & verify the existing work (`docs/how-to-use-and-verify.md`).
4. Capital engine (`capital.py` + tests) — the foundation the next three need.
5. Balcony: research loop → calculator model + tests + CLI + web + integration doc.
6. Rooftop: same loop.
7. Battery: same loop.
8. Final: clear cache, code-review pass, fix bugs, capture lessons (compound), commit, push, open
   new PRs on both repos.

## Invariants held throughout

- **Formula correctness is the metric.** Every option ships a hand-verified worked example as a
  test; `python3 -m unittest discover -s tests` must stay green.
- **Transparency mechanic.** Every number is a labeled, tagged (`default (sourced)` /
  `user-provided` / `unsourced — pending research`), optionally-sourced assumption.
- **Agent-native parity.** CLI + `--json` cover every option a human can run.
- **Web is a mirror with a self-check.** Each option gets an on-load parity guard against its
  Python worked example (no JS runtime here, so the Python suite remains the source of truth).
- **Research is verbatim or a stub, never a paraphrase.** The calculator pulls sourced numbers; it
  does not invent them.
