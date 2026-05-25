---
title: Phase 4 — Research Integration & Reaction
type: integration
status: done
date: 2026-05-25
inputs:
  - ../solar-investment-research/wiki/calculator-brief/answers.md
  - docs/plans/2026-05-25-feat-community-solar-poc-plan.md
---

# Phase 4 — Research Integration & Reaction

Phase 4 closes the loop: the research repo's three sourced answers are now the POC's defaults, and
this doc reacts to what the research + the build taught us — what firmed up, what surprised us,
what's still open, and what the next iteration needs.

## What landed in the code

The research brief (`../solar-investment-research/wiki/calculator-brief/answers.md`, all three exit
booleans `true`) was folded into the POC defaults — re-tagged from `unsourced — pending research`
to `default (sourced)` with citations, in both `src/assumptions.py` and the `web/app.js` mirror:

| Assumption | Was (Phase 3 placeholder) | Now (sourced, CMP) | Source |
|---|---|---|---|
| `price_per_kwh` | 0.25 (unsourced) | **$0.306/kWh** | Maine DOE electricity prices (eff. Jan 1 2026) |
| `bill_offset_fraction` | 0.60 (unsourced) | **0.82** | Maine OPA + Maine DOE (credit offsets per-kWh charges, not fixed) |
| `subscription_discount_pct` | 0.12 (unsourced) | **0.15** | Maine OPA (10–15%) + Solar Gardens (guaranteed 15%) |

Default bill-only estimate (a $150 CMP bill) moved from $129.60/yr (7.2%) to **$221.40/yr (12.3%
off, $0 capital)**. The test suite stayed green (12 tests); the worked-example case is unchanged
(it uses fixed illustrative inputs, decoupled from the shipped defaults by design).

## What firmed up

- **The savings model is correct as specified.** Solar Gardens states the savings calculation in
  the same shape the POC uses ("what you paid for credits + remaining utility balance, vs. what
  you'd have paid without credits") — i.e. `savings = bill × offset × discount`. Independent
  confirmation of the formula, not just the inputs.
- **A model cross-check validates the numbers.** `pct_off = offset × discount = 0.82 × 0.15 ≈
  12.3%` lands squarely inside the Maine OPA's independently-stated "10–15% savings" range. The
  formula and the sourced inputs agree — exactly the formula-correctness signal the metric wants.

## What surprised us (worth surfacing to users)

1. **"15% discount" ≠ 15% off your bill.** The provider's discount is on the *credits*, which only
   offset the ~82% of the bill that is per-kWh charges — never the fixed monthly charge. So a 15%
   credit discount nets ~12% off the total bill. The POC surfaces both numbers; marketing usually
   shows only the bigger one.
2. **`price_per_kwh` is display-only for the dollar result.** The Phase 1 cancellation analysis held
   up against real numbers: starting from a bill, the $/kWh cancels out of savings (it only sets the
   usage shown). So the load-bearing research was the offset fraction and the discount — which is
   where Phase 2 effort actually went.
3. **The offset fraction is usage-dependent, not a constant.** Because the fixed charge is fixed,
   the offsettable share is ~0.82 for a typical 550 kWh CMP bill but rises toward 1.0 for heavy
   users. The default is honest for a typical bill and editable; a future version could compute it
   from the user's own usage.
4. **Residential ≠ the commercial tariff rate.** Maine runs two NEB programs; residential community
   solar is the *kWh-credit* program (credits worth the customer's retail per-kWh charges), not the
   lower PUC *dollar tariff* program (non-residential). Estimating a homeowner's savings off the
   commercial tariff would understate them. Captured in the research caveats.

## What's still open (does not block the POC)

- **Escalators.** The common Maine model (Solar Gardens) is a flat guaranteed discount; whether
  other providers apply an annual escalator is unsourced (research open question). Not modeled — the
  POC is single-year ($/yr), so an escalator has no input to bind to yet. Revisit if/when the POC
  grows a multi-year view.
- **Versant defaults.** Shipped defaults are CMP. A Versant user must edit `price_per_kwh`,
  `bill_offset_fraction` (≈0.87–0.88), and pick Bangor Hydro vs. Maine Public. A utility selector is
  a clean next enhancement (the research already has the numbers — see `wiki/utilities/versant-rates.md`).
- **Annual rate refresh.** Standard-offer supply resets every Jan 1; the sourced `$/kWh` and the
  offset fraction will drift. The research repo's health-check has a stale-number audit; the
  calculator should re-pull after each January reset.

## What the next iteration (rooftop) needs

Rooftop is where the deferred **capital-allocation / NPV / payback / opportunity-cost engine**
becomes load-bearing (it's dormant for community solar, which is $0 capital). From this iteration:

- The bill→usage→credits pipeline and the assumption data model carry over directly.
- Rooftop kWh credits offset the same per-kWh charges, but rooftop adds upfront capital, system
  sizing, and generation modeling — and brings net-metering vs. NEB nuance. The research repo's
  `open-questions.md` already lists these as the rooftop research front.
- The capital engine will need: install cost, system size/generation, the same offset mechanics,
  and an opportunity-cost rate. None of that is in the community-solar POC, by design.

## Backlog / strategy touches

No `STRATEGY.md` change needed — the transparency approach and the formula-correctness metric both
held up. `docs/BACKLOG.md` already lists the utility selector (CMP/Versant depth), multi-year /
escalator handling, and the rooftop capital engine; this doc confirms those as the natural next
pulls, in that rough order.
