---
title: "feat: minimal user feedback — passive stats + one active ask"
type: feat
status: draft
date: 2026-07-20
---

# feat: minimal user feedback — passive stats + one active ask

## Summary

Collect enough from real visitors to know **which assumption is wrong** and **what people actually
ask**, without building a feedback product. Three slices, in strict value order: (F1) an append-only
JSONL event log on the deploy's existing volume — no database, no accounts; (F2) client events for
the four moments that carry signal, of which *editing an assumption* is the one that matters; (F3)
one active ask — thumbs plus optional text, submitted **with the scenario URL attached**, because
the scenario is what makes a complaint actionable.

F1 alone is worth shipping. F2 is where the product learning is. F3 is cheap but lower-yield than
it looks, and deliberately last.

Explicitly **not** in scope: a dashboard, a database, accounts, session replay, analytics vendors,
anything that auto-edits `assumptions.py`, and any agentic "self-improvement loop." Those are the
version of this we can build later once we know what the data looks like.

---

## Problem Frame

The calculator is right and verified. What we don't know is whether it's *useful* — and the
project's whole thesis makes that question unusually specific.

This isn't a black-box tool where feedback can only be "good"/"bad". Every number on screen is a
labeled assumption with a tag, and a third of them ship tagged `unsourced — pending research`. So
the useful question isn't "did you like it" — it's **"which number did you not believe?"** And the
page already answers that every time someone edits an assumption off its default: that edit *is* the
feedback. We just don't record it.

The second thing we don't know is what people ask. `/ask` routes questions the page didn't write,
and every one of them is a statement about what a Maine homeowner thinks this tool is for. Some
fraction will be things we can't answer — those are the roadmap.

Three constraints shape the whole design:

- **Storage means statefulness, which the project has never had.** The deploy now has a volume at
  `/data` for the spend ledger and extraction cache (`docs/deploy-handoff.md`). An append-only file
  there is the entire storage story. A database is a real cost and buys nothing at this volume.
- **Feedback must not close its own loop.** "Sourced defaults trace to research; the calculator
  never invents numbers" is a founding rule. Anything auto-editing `assumptions.py` from user text
  breaks it. The honest loop is: feedback naming a bad default becomes a *research question* for
  `solar-investment-research`, whose whole job is landing sourced numbers. A human reads the file.
- **Traffic will be tiny.** Ten visitors is a realistic first month. That kills anything requiring
  statistical power and argues for capturing *raw, rich* events rather than counters — with ten
  users you read the log, you don't aggregate it.

---

## Requirements

- **F1.** Every event is appended as one JSON object per line to a file on the deploy's volume, with
  a timestamp. No database. Survives redeploys. Gitignored, and the path is configurable the same
  way the ledger's is.
- **F2.** The page reports four named events: a question asked, an option selected, **an assumption
  edited off its default** (key, old value, new value), and a comparison run. Nothing is reported
  that isn't one of these four.
- **F3.** The estimate carries one active ask: thumbs up/down plus an optional free-text box. It
  submits the current scenario URL alongside, so a complaint arrives with the state that produced it.
- **F4.** No personally identifying information is stored, ever — no IP, no cookie, no fingerprint,
  no account. A random per-page-load id is enough to group one visit's events; it dies with the tab.
- **F5.** The page must work identically with the endpoint unreachable, refusing, or absent. This is
  the same standard `/ask` already meets and the verifier already enforces: telemetry that can break
  the calculator is worse than no telemetry.
- **F6.** A visible, plain-English statement of what is collected, in the same register as the rest
  of the page's disclaimers. If we can't state it in two sentences, we're collecting too much.
- **F7.** The log is bounded — a size or line cap with oldest-first eviction, like the extraction
  cache's `MAX_ENTRIES`. An unbounded append is a disk bug waiting for traffic.
- **F8.** `/events` is rate-limited per IP and bounded in payload size, reusing the same limiter
  `/ask` already has. It's a public unauthenticated write endpoint; it needs the same treatment.

---

## F1 — The log (do this one first, it's an afternoon)

`service/feedback.py`, modeled directly on `cache.py` — same JSON-file pattern, same fail-soft
posture, same env-var configuration. Failing soft is not optional here: a telemetry write that
raises would take down an answer.

```
POST /events  {"session": "<random>", "events": [{"kind": "...", ...}]}  -> 204
```

Batched, because a single assumption-edit drag would otherwise fire twenty requests. The page holds
events in memory and flushes on a debounce and on `visibilitychange`.

Two things land free on the server side, without any client work at all:

- **`/ask` questions.** The extraction cache already stores every question the page didn't write,
  keyed by hash. Add the normalized question text and a hit counter to each entry and it becomes a
  frequency-ranked list of what people actually asked — the single most useful artifact in this
  whole plan, for roughly ten lines. *(Check first: this changes what a cached entry holds, so it
  interacts with `cache_version()`. Adding a field should invalidate cleanly, but verify.)*
- **Outcome counts per request:** which option was routed, whether the agent answered or the page
  fell back, and which error kind if any. That's "is the agent even working in the wild", which we
  currently have no way to know.

**Storage:** `/data/.feedback.jsonl`, `SOLAR_FEEDBACK_PATH` to override, gitignored.

---

## F2 — The four events (this is where the learning is)

| Event | Payload | What it answers |
|---|---|---|
| `asked` | question text, whether the agent or the local parser answered | What people want. The unanswerable ones are the roadmap. |
| `option_selected` | option key | Which of the seven anyone cares about. Cheap to record, and likely to be surprising. |
| **`assumption_edited`** | key, from, to, the option in view | **Which default nobody believes.** |
| `compared` | the option keys | Whether side-by-side is a real need or a feature we assumed. |

`assumption_edited` is the reason to do this work. Two distinct signals fall out of one event:

- An edit to a **sourced** default means our sourced number doesn't match this person's reality —
  either the source is stale, or the default is a bad central estimate for real Maine homes.
- An edit to an **unsourced** placeholder is a direct vote on which of the two honest unknowns
  (`installed_cost_per_kwh`, `residual_coverage`, the resilience value, `electrician_cost`) to
  research first. Right now that ordering is a guess.

Recording `from` and `to` matters more than recording the count: the *direction and magnitude* of
the correction is the research finding. Ten people all raising `installed_cost_per_w` from $2.95 to
about $3.60 is a sourced-number update with evidence, not a vague complaint.

---

## F3 — The one active ask (last, and smallest)

One row under the estimate: 👍 / 👎, and on a click, a single optional text box ("what didn't add
up?"). Submitting attaches the current scenario URL — which already encodes option, bill, usage, and
every edited assumption (R8b, shipped in W2). That attachment is the whole design: a thumbs-down
alone is noise, and a thumbs-down *with the scenario that produced it* is reproducible.

It's last because it's the lowest-yield slice. Almost nobody clicks these, the ones who do are
unrepresentative, and the passive `assumption_edited` signal tells us more about which number is
wrong than a free-text box will. It's in the plan because it's a few hours and it catches the one
thing passive data structurally cannot: a person who thinks the *whole framing* is wrong.

---

## What closes the loop (and what deliberately doesn't)

```
assumption_edited on an unsourced key   ──►  a research question in solar-investment-research
assumption_edited on a sourced key      ──►  re-check the source; is our default stale or wrong?
an unanswerable question, repeated      ──►  docs/BACKLOG.md
a thumbs-down with a scenario URL       ──►  open the URL, reproduce, decide
```

Every arrow ends at a human. That's the design, not a limitation we'll grow out of: the loop between
"a number looks wrong" and "a sourced number lands" already exists — it's the research repo — and
feedback is its intake, not a replacement for it. The compound-engineering version of this (an agent
that reads the log, drafts research questions, and opens them automatically) is a real thing to build
*later*, and it will be a much better thing to build once there's a month of real events to test it
against. Building it now means designing an automation against imagined data.

**Never:** auto-editing `assumptions.py`. It collides head-on with the founding rule and would
convert one confused visitor into a wrong sourced default.

---

## Sequencing and size

```
F1 log + free server-side signals  ──►  F2 client events  ──►  F3 active ask
        (~half a day)                      (~a day)              (~half a day)
```

F1 ships alone and is immediately useful. Do not start F2 before the deploy is live and F1 has
recorded anything at all — the first real events will change what's worth recording, and that is
cheaper to learn than to design around.

## Open questions for the human

1. **Is the question text itself OK to store?** It's typed by a person and could contain anything.
   Storing it verbatim is what makes it useful; a redaction pass is possible but adds cost. The
   answer determines F1's shape, so it's worth deciding before starting.
2. **How long is the retention?** "Forever, it's a POC" is a legitimate answer, but it should be a
   stated one, given F6 says the page will tell visitors what happens to their data.
3. **Does the MCP surface get counted too?** Tool calls are free signal about agent-native usage,
   and nobody is a "user" there in the privacy sense. Probably yes, and probably trivial.

## Definition of done

- `pytest tests service/tests` passes; `python tools/verify_web.py check` exits 0.
- The page renders and answers identically with `/events` returning 500, and with it absent.
- A real edit on the deployed page appears as one line in `/data/.feedback.jsonl`.
- The page states, in plain English, what it collects.
