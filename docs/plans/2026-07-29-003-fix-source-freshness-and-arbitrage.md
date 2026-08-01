---
title: "fix: the arbitrage overstatement, and knowing when a source goes stale"
type: fix
status: ready
date: 2026-07-29
---

> **Provenance: agent-generated, lightly human-reviewed.** Written by Claude on 2026-07-29. The
> arbitrage error and the 2026-07-01 source update are **human-identified** — both are recorded in
> `docs/ideas/ideas.md` in the author's own words. Everything else (the `checked_on` /
> `recheck_after` schema, the suggested cadences, `tools/check_sources.py`, S3's rendering) is an
> agent's proposal read for direction, not line by line. The cadence numbers in particular are
> guesses, not research.
>
> **Split by `docs/plans/2026-07-30-001-decide-is-this-worth-pursuing.md`.** S1 is a known-wrong
> number shipping today and survives every verdict — do it regardless. S2/S3 are about strangers
> relying on stale numbers, so their urgency depends on whether there are any; under a NARROW
> verdict a calendar reminder replaces the whole of S2.

# fix: the arbitrage overstatement, and knowing when a source goes stale

## Summary

One known-wrong number and the process gap that let it sit: fix the time-of-use arbitrage
overstatement (S1, ~1.9% too generous), then give every sourced assumption a **checked-on date and
a re-check cadence** so staleness is visible instead of discovered (S2), and surface it to the
reader (S3).

## Problem Frame

`docs/plans/2026-07-20-001-feat-minimal-user-feedback.md` states the uncomfortable truth plainly:

> An LLM wrote these formulas. Tariffs change, CMP refiles rates, the federal credit is a political
> object, and a third of the assumptions ship tagged `unsourced — pending research`. The tests
> prove internal consistency, not that the examples still describe Maine. **Correctness here is a
> hypothesis with an expiry date.**

Two concrete instances are already known and neither was caught by anything automatic:

1. **The arbitrage math is wrong in a known direction.** The master equation values each shifted
   kWh at on-peak minus off-peak — `U×0.058120 − R×0.367366` — **as if charging were lossless**.
   Real round-trip efficiency is ~85–90%, so every arbitrage figure is about **1.9% too generous**.
   Small, but it is an error in the *favorable* direction on the option whose whole case is
   arbitrage, and this project's entire pitch is that its numbers are checkable.
2. **`maine.gov/energy/electricity-prices` updated 2026-07-01** and nothing noticed. It is the
   source behind `price_per_kwh`, which propagates into every option.

The second is the real subject. Fixing (1) without (2) means doing this again in three months and
finding out the same way — by chance.

## Requirements

- **R1 — The fix lands in the research repo first.** `solar-investment-research/wiki/` is the
  source of truth; the calculator *pulls* sourced numbers and never invents them. A correction
  applied here first would invert that and is the one thing this project must not do.
- **R2 — Round-trip efficiency is an explicit, editable assumption**, not a constant folded into
  the equation. It varies by chemistry and by how the battery is driven, and burying it is what
  produced the current error.
- **R3 — Every sourced assumption carries a `checked_on` date** and a **`recheck_after`** interval
  appropriate to what it is. A statutory credit percentage and a monthly-average rate do not go
  stale on the same clock.
- **R4 — Staleness is reportable without a network call.** `python tools/check_sources.py` reads
  the assumption metadata and lists what is overdue. Fetching the actual pages to diff them is a
  much larger job and explicitly out of scope — knowing *what to go look at* is most of the value.
- **R5 — A stale sourced default is visible to the reader**, in the same register as the existing
  tags. Not alarming, just honest: a number last verified 14 months ago should say so.
- **R6 — No auto-updating.** Nothing fetches a page and rewrites `assumptions.py`. Same
  founding-rule collision as auto-editing from feedback: it converts a page change nobody read
  into a sourced default nobody checked.

## S1 — The arbitrage fix

**In the research repo:** correct the master equation to charge the round-trip loss against the
shifted kWh, and record the efficiency figure with its source. Expect roughly:

```
value_per_shifted_kwh = on_peak_rate − (off_peak_rate ÷ round_trip_efficiency)
```

rather than `on_peak_rate − off_peak_rate` — you must buy more than one kWh off-peak to deliver one
on-peak, which is exactly the loss the current form ignores.

**Then in the calculator:** add `round_trip_efficiency` to `src/tou.py`'s assumptions, tagged
`default (sourced)` once the research lands (and `unsourced — pending research` if it ships ahead
of that — do not let a plausible number wear a sourced tag). Update `src/battery.py` and
`src/plugin_battery.py`, which share the engine, and mirror it in `web/app.js`.

**The worked examples in `tests/` change.** That is the point — they encode the old, wrong answer.
Update them from the corrected research, not by pasting whatever the new code prints, or the test
stops being an independent check and becomes a screenshot of a bug.

Expect the plug-in battery's break-even installed cost to move down slightly and its payback out.
If a case crosses the 15.8% scope line as a result, that is a real finding, not a test to nudge.

## S2 — Freshness metadata

Extend the `source` record in `src/assumptions.py`:

| Field | Meaning |
|---|---|
| `checked_on` | ISO date a human last confirmed this value against the document |
| `recheck_after` | e.g. `"P1Y"` / a day count — how long before it should be looked at again |

Suggested cadences, to be set per assumption rather than globally:

- **Utility rates** (`price_per_kwh`, on/off-peak, delivery) — CMP refiles regularly; ~6 months.
- **State-published figures** (Maine DOE prices) — the 2026-07-01 update is the precedent; ~6 months.
- **Statutory values** (`federal_itc_pct`, NEB rules) — stable until suddenly not; ~1 year, and
  worth a note that legislation is the trigger, not the calendar.
- **Market/equipment prices** (`installed_cost_per_w`, battery $/kWh) — ~1 year.

`tools/check_sources.py` prints what is overdue, sorted by how overdue, and exits non-zero if
anything is — so it can become a chore or a CI step later without rework. Stdlib-only, like the
rest of `tools/`.

## S3 — Surfacing it to the reader

In the ledger, a sourced assumption past its `recheck_after` shows its date alongside the existing
`default (sourced)` tag: *"last checked Jan 2026."* Reuse the provenance tag styling — the design
system allows hue on exactly the three provenance tags, and this is provenance.

**Do not add a fourth tag colour or a warning icon.** A date is the honest signal; an alarm implies
the number is wrong, which is not what "overdue for a look" means.

## Sequencing

```
S1 arbitrage fix (research → calculator)  ──►  S2 freshness metadata  ──►  S3 surface it
   (~a day, most of it research)               (~a day)                    (~half a day)
```

S1 first because it is a known wrong number shipping today. S2 and S3 are what stop the next one
lasting as long.

## Definition of done

- The research repo carries the corrected equation and a sourced round-trip efficiency, and the
  calculator's `explain` text cites it.
- `pytest tests service/tests` passes with worked examples updated **from the research**, and the
  arbitrage figures move down by roughly the expected ~1.9%.
- `python tools/verify_web.py check` exits 0 — the mirror computes the corrected value too.
- `python tools/check_sources.py` runs, lists overdue sources, and exits non-zero when any is.
- Every `default (sourced)` assumption has a `checked_on`; any that can't get one is retagged
  `unsourced — pending research`, which is the honest outcome rather than a failure.

## Out of scope

Fetching or diffing source documents automatically. Alerting. Any agent that reads a page and
proposes an update — that is Tier 5 in the backlog and wants a month of real events first.
