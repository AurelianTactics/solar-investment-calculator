---
title: "feat: make the financial argument the thing this tool is best at"
type: feat
status: ready
date: 2026-07-29
---

> **Provenance: agent-generated, lightly human-reviewed.** Written by Claude on 2026-07-29 from
> `docs/ideas/ideas.md`, where the human note reads: *"need to think through how I present the
> financial argument… maybe 'if I had invested this money, what percent return would I need for
> equivalent savings'… NPV, IRR etc."* That intent is human. The IRR-as-headline framing, the
> requirements, the panel contents, and the sequencing are an agent's elaboration of it, read for
> direction rather than line by line.
>
> **The least contingent of the four plans.** It serves the author's own mental model — the stated
> audience in `STRATEGY.md` — so it survives every verdict in
> `docs/plans/2026-07-30-001-decide-is-this-worth-pursuing.md`, including STOP. If only one plan
> gets built, the argument for this one is that it's the only plan that doesn't need an audience.

# feat: make the financial argument the thing this tool is best at

## Summary

Three slices that turn "NPV $9,811 (solar wins at 7%)" into an argument a homeowner can actually
weigh: the **required-return framing** (S1) — *what return would your investments need to beat
this?* — a **progressive-disclosure financial panel** carrying IRR, discounted and undiscounted
payback, and the cashflow (S2), and **inflation stated explicitly** rather than folded into
escalation (S3).

S1 is the headline and is worth shipping alone.

## Problem Frame

The capital engine is described in `CLAUDE.md` as the centerpiece, and it is the one thing here
that a solar salesperson will never show you: NPV > 0 means buying beats investing the same cash at
your opportunity rate. That is a genuinely good argument.

**It is currently delivered as a number most people cannot use.** The compare table's NPV column
is a dollar figure with a parenthetical discount rate. To act on it you must already know what NPV
is, accept 7% as your alternative, and trust that the horizon and escalation behind it are
reasonable. The notes have flagged this repeatedly — wanting undiscounted payback, IRR, and
specifically *"if I had invested this money, what percent return would I need for equivalent
savings."*

That last phrasing is the insight, and it inverts the current framing usefully. Instead of:

> NPV $9,811 at a 7% discount rate

it says:

> Your money would need to earn **12.4% a year**, every year for 25 years, to beat putting it on
> the roof.

Same arithmetic — that is the IRR — but it asks a question the reader can answer, because everyone
has a rough sense of what their savings actually earn. It also degrades honestly: when the required
return is 3%, most readers correctly conclude solar wins easily; when it's 15%, they correctly
conclude it doesn't.

**The risk to respect:** this is one more number on a page the notes already call "way too busy."
S1 must *replace* the NPV headline's job, not sit beside it, and S2 must be genuinely hidden until
asked for. If this ships as three more visible rows, it has failed regardless of correctness.

## Requirements

- **R1 — The headline verdict is a required rate of return**, stated as a sentence, for every
  capital option. Community solar stakes no capital and is exempt (it has no IRR — say so, don't
  print a zero).
- **R2 — IRR is computed in `src/capital.py`**, alongside NPV and payback, and mirrored in
  `web/app.js` like every other formula. It is a property of the cashflow stream the engine
  already builds — not a new model.
- **R3 — It degrades honestly when there is no solution.** A stream that never turns positive has
  no IRR. Say "this never pays back at any rate" rather than printing a misleading number or
  `NaN`. Streams with sign changes can have multiple roots; bisection over a bounded range with an
  explicit "no unique answer" outcome is correct and sufficient here.
- **R4 — Both paybacks are available**: simple (undiscounted) and discounted. The gap between them
  *is* the time-value argument, and showing them adjacent teaches it for free.
- **R5 — The detail is progressive disclosure**, in the existing ledger idiom (an expandable row),
  not a new page, panel, or tab.
- **R6 — Every new number is an assumption or a step**, carrying a label, tag and explanation like
  everything else. No new number arrives unlabeled.
- **R7 — Comparisons stay at one shared `opportunity_rate`.** Already true and load-bearing; IRR
  makes it more tempting to break, because a per-option rate would look reasonable and make the
  rows incomparable.

## S1 — The required-return headline

Compute IRR from the existing per-year cashflow stream. Bisection between −0.99 and, say, 5.0 to a
tolerance of 1e-6; the stream is one negative outflow followed by positive inflows in the ordinary
case, so a unique root exists and bisection is robust, obvious, and needs no dependency.

Render as a sentence under the verdict:

> Your money would need to earn **12.4%/yr for 25 years** to beat this. *(You told us you'd
> otherwise earn 7%.)*

The parenthetical is what ties it back to the editable `opportunity_rate` and keeps the existing
NPV verdict coherent rather than orphaned.

**Where the horizon comes from matters.** "12.4% a year" is meaningless without "for how long," and
the horizon is itself an editable assumption. Both belong in the sentence.

## S2 — The financial detail panel

One expandable row in the ledger — *"Show the full financial picture"* — containing:

| Row | Why it's here |
|---|---|
| Required return (IRR) | The S1 headline, in its numeric home |
| NPV at your opportunity rate | What exists today |
| Simple payback | The number every solar quote leads with |
| Discounted payback | The honest version, and the contrast is the lesson |
| Total undiscounted savings over the horizon | The big encouraging number, labeled as what it is |
| Year-by-year cashflow | Already computed; currently only in `--json` |

The cashflow is the one worth showing visually, and it is already in the payload — the web mirror
just doesn't render it. A small inline bar or sparkline per year, or a compact table. **Judge any
layout against `battery+rooftop`** (25 assumptions, 9 steps), never the community default, per the
design-system note in `web/index.html`.

## S3 — Inflation, stated

Escalation currently folds general inflation and real electricity-price growth into one number.
They are different claims with different sources, and a reader who wants to argue with one has to
argue with both. Split them, or state explicitly in the `explain` that escalation is nominal and
inflation is already inside it. **Splitting adds a knob**; stating it clearly may be the better
trade at this page density. Decide when building, and record which and why.

## Sequencing

```
S1 IRR + headline  ──►  S2 detail panel  ──►  S3 inflation
   (~a day)              (~a day)              (~half a day)
```

## Definition of done

- `pytest tests service/tests` passes, including hand-verified IRR cases for every capital option
  and the no-solution case.
- `python tools/verify_web.py check` exits 0; the parity self-check passes for all seven states,
  meaning `web/app.js` computes the same IRR as `src/capital.py`.
- `python src/cli.py --option rooftop --json` carries IRR and both paybacks; MCP `calculate`
  returns them too (automatic via `tools_core`, but assert it — `test_tools_core.py` is the place).
- A screenshot comparison of `battery+rooftop` before and after lands in `docs/design/`, per
  "a design judgement is evidence too."
- Community solar reports no IRR and says why, rather than reporting zero.

## Out of scope

Financing (loans, leases, PPAs) — that is a modeling change, in the backlog, and much larger.
Tax-situation modeling beyond the existing flat federal credit. Any per-option opportunity rate.
