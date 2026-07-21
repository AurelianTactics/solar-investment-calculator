---
title: "feat: minimal instrumentation — know what's happening, then know what's wrong"
type: feat
status: draft
date: 2026-07-20
updated: 2026-07-21
---

# feat: minimal instrumentation — know what's happening, then know what's wrong

## Summary

We currently have no idea whether anyone uses this. Four slices, in strict value order:
(S1) an append-only JSONL log on the deploy's volume, written first by a **server-side request
middleware** that needs no client cooperation and catches MCP too; (S2) `/ask` question capture
plus a new **`intent` field** on the router's existing structured-output call, classifying every
question as `calculate | feedback | out_of_scope` — logged, never acted on; (S3) client events, of
which *editing an assumption* is the one that carries a research finding; (S4) one active ask —
thumbs, then an optional text box, submitted with the scenario URL attached.

S1 is worth shipping on its own and is the cheapest thing here. S2 is nearly free because the LLM
call already exists. S3 is where the sharpest signal is. S4 is last and smallest.

Explicitly **not** in scope: a dashboard, a database, accounts, session replay, analytics vendors,
anything that auto-edits `assumptions.py`, and any agentic "self-improvement loop."

---

## Problem Frame

**We are flying blind.** We don't know if anyone visits, where they come from, what they do,
whether the agent works in the wild, whether anyone connects over MCP, or whether any number on the
page is still true.

The earlier framing of this plan opened "the calculator is right and verified." That claim doesn't
survive contact with what the project actually is. An LLM wrote these formulas. Tariffs change,
CMP refiles rates, the federal credit is a political object, and a third of the assumptions ship
tagged `unsourced — pending research`. The tests prove the code matches worked examples that were
themselves written down by a model — they prove internal consistency, not that the examples still
describe Maine. **Correctness here is a hypothesis with an expiry date, not a settled fact**, and
instrumentation is how we find out when it expires.

So the goal is not "build a feedback product." It is: the minimum instrumentation that lets us stop
guessing, cheap to build, cheap to throw away, structured so it can grow into something real.

That reframing changes the order of the work. The original plan led with client-side assumption
edits as the thesis. But an edit event only fires if someone visits, stays, and engages — and we
don't yet know that anyone does. Basic traffic and usage come first; "which number is wrong" is one
signal among several, not the headline.

Three constraints still shape the design:

- **Storage means statefulness, which the project has never had.** The deploy has a volume at
  `/data` for the spend ledger and extraction cache. An append-only file there is the entire
  storage story.
- **Feedback must not close its own loop.** "Sourced defaults trace to research; the calculator
  never invents numbers" is a founding rule. Anything auto-editing `assumptions.py` from user text
  breaks it. The honest loop is: feedback naming a bad default becomes a *research question* for
  `solar-investment-research`. A human reads the file.
- **Traffic will be tiny.** Ten visitors is a realistic first month. That kills anything requiring
  statistical power and argues for capturing *raw, rich* events rather than counters — with ten
  users you read the log, you don't aggregate it.

**Prerequisite:** none of this works until the Railway volume is attached (step 3 of
`docs/deploy-handoff.md`). Without it the container filesystem is ephemeral and every event
vanishes on the next push. S1 is blocked on the deploy, not the reverse.

---

## Storage decision: JSONL, no database

One file, one JSON object per line, heterogeneous `kind` field. Everything — request logs, MCP
calls, questions, client events, thumbs, free text — lands in the same stream.

**Why not SQLite**, which is the only serious alternative and roughly equal effort: the event shape
will change three times in the first month, and schema migrations on POC telemetry are pure
friction. JSONL defers the schema decision until we've seen real events.

**This does not give up querying.** DuckDB reads JSONL directly with no import step:

```sh
duckdb -c "select kind, count(*) from read_json_auto('feedback.jsonl') group by 1 order by 2 desc"
```

When querying genuinely hurts, importing into SQLite is twenty lines. Revisit then, not now.

**Storage:** `/data/.feedback.jsonl`, `SOLAR_FEEDBACK_PATH` to override, gitignored, modeled on
`cache.py` — same JSON-file pattern, same fail-soft posture, same env-var configuration. Failing
soft is not optional: a telemetry write that raises would take down an answer.

### Size, honestly

| Line kind | Bytes |
|---|---|
| Request log | ~300 (user-agent is most of it) |
| Client event | ~200 |
| Question asked | ~700 (500-char cap + envelope) |
| Feedback + scenario URL | ~1,800 |
| MCP tool call | ~250 |

At 10 visitors/month × ~20 events: **~60 KB/month, under 1 MB/year.** At 100× that traffic, 72
MB/year. A Railway volume is a fixed-size provisioned disk, not elastic storage — there is no path
to a surprise bill, only to a full disk. The realistic risk is that the log is too *boring*, not too
big.

Organic volume is therefore irrelevant. The ceiling is what an attacker can push at a public
unauthenticated write endpoint, and **per-IP rate limiting does not bound disk** — it bounds rate,
and disk is rate integrated over time. At the existing 10 req/min with an 8 KB payload cap, one IP
writes 115 MB/day. That is what the caps below are actually for.

---

## Requirements

- **R1 — One log, appended.** Every event is one JSON object per line on the volume, with a
  timestamp and a `kind`. No database. Survives redeploys. Gitignored, path configurable like the
  ledger's.

- **R2 — The log yields before anything else does.** Two checks before every append, both a few
  lines:
  1. **Byte ceiling** on the file itself (`os.path.getsize`), default ~1% of the volume (50 MB on
     5 GB). Bounds the log.
  2. **Free-space floor** (`shutil.disk_usage`) — refuse to append if free space on the volume is
     below a reserve. This is the one that matters: it doesn't care *what* filled the disk, so if
     the extraction cache or a stray file is the culprit, the log still steps aside.

  Rationale: `/data` is shared with `.spend.json`, and `spend.py` **fails closed** — a ledger that
  can't be written stops `/ask` answering. Telemetry must never be able to take down the agent.
  Railway allows one volume per service, so isolation-by-separate-disk isn't available; yielding
  first is the substitute.

- **R3 — On hitting a limit, refuse; never evict.** Retention is forever (below), so oldest-first
  eviction would silently delete the earliest and most interesting data to make room for whoever is
  flooding us. Refusing is loud and reversible. `/health` reports the log's size and percent of
  ceiling alongside the spend figure, so "the log is 80% full" is visible rather than discovered.
  *(This is a deliberate departure from `cache.py`'s `MAX_ENTRIES` eviction — a cache entry is
  disposable, an event is not.)*

- **R4 — Caps on what one request can write.** Payload cap ~2 KB per POST (generous for a batch of
  eight small events, hostile to bulk), a per-batch event count cap, and the existing per-IP
  limiter from `/ask` reused on `/events`. **Oversized batches are rejected; oversized free text is
  truncated** — rejecting a batch costs an attacker nothing, rejecting a person's paragraph throws
  away the feedback we asked for.

- **R5 — The raw client IP is stored**, along with user-agent and referrer. This is a reversal of
  the original plan's blanket no-PII rule, which was ideology rather than a requirement: without a
  stable per-visitor value you cannot distinguish ten homeowners from one enthusiast reloading, and
  `referrer` is literally the answer to "where is traffic coming from." It's what every web server's
  access log holds. The obligation this creates is R8, not a workaround.

- **R6 — Question and feedback text are stored verbatim**, subject to R4's caps. Storing it as
  typed is what makes it useful; a redaction pass adds cost and destroys the signal. *(Decided —
  was open question 1.)*

- **R7 — Retention is forever.** It's a POC and the volume is measured in years of runway. This is
  a stated decision, not an oversight, and it's why R3 refuses rather than evicts. *(Decided — was
  open question 2.)*

- **R8 — A visible, plain-English statement of what is collected**, in the same register as the
  page's other disclaimers. R5 + R6 + R7 make this more load-bearing, not less: we store IP
  addresses and whatever you type, and we keep it. Two sentences. If we can't state it in two, we're
  collecting too much.

- **R9 — The page works identically with the endpoint unreachable, refusing, or absent.** Same
  standard `/ask` already meets and the verifier already enforces. Telemetry that can break the
  calculator is worse than no telemetry.

- **R10 — MCP calls are counted.** Same log, `kind: mcp_tool_call`, tool name and an argument
  summary. No LLM and no cookies on that path, so IP + user-agent is all there is — and for MCP the
  user-agent is genuinely informative (a Claude connector vs. a script). It is the only window into
  agent-native usage, which is half the point of the project. *(Decided — was open question 3.)*

---

## S1 — Server-side logging (do this first; it's an afternoon)

A FastAPI middleware logging every request: timestamp, method, path, status, duration, IP,
user-agent, referrer. About fifteen lines.

This is first because it is the only slice that **requires no client cooperation** — it can't be
blocked, it works for visitors who bounce in two seconds, and it covers `/mcp` (R10) for free. It
answers the questions we actually can't answer today: does anyone visit, how often, from where, is
the agent being reached, is anyone using MCP.

Two more things land free on the server side:

- **Outcome per `/ask`:** which option was routed, whether the agent answered or the page fell back,
  and which error kind if any. That's "is the agent even working in the wild."
- **Question frequency.** The extraction cache already stores every question the page didn't write,
  keyed by hash. Add the normalized text and a hit counter and it becomes a frequency-ranked list of
  what people asked. *(Check first: this changes what a cached entry holds, so it interacts with
  `cache_version()`. Adding a field should invalidate cleanly — verify.)*

---

## S2 — The `intent` field (nearly free)

The router already makes one `claude-opus-4-8` structured-output call per uncached question. Add one
field to the output schema:

```
intent: "calculate" | "feedback" | "out_of_scope"
```

Same call, a handful of extra output tokens. This turns the existing question box into a labeled
feedback channel with no new UI at all — which is the answer to "how is feedback solicited": mostly,
it isn't. People type what they think into the box that's already there, and we finally read it.

**Log the intent; do not route on it in v1.** This is the load-bearing constraint. If the classifier
labels a real question "feedback" and the page stops calculating, we've broken the product to serve
telemetry. Log-only, read a month of classifications, *then* decide whether it should influence
behavior.

**When the LLM is down or the spend cap has tripped**, log the raw text with `intent: "unknown"`.
The text is the asset; the label is derivable offline whenever we want it. Every question survives
regardless of whether the model was reachable.

---

## S3 — Client events (where the sharpest signal is)

| Event | Payload | What it answers |
|---|---|---|
| `option_selected` | option key | Which of the seven anyone cares about. Likely to surprise. |
| **`assumption_edited`** | key, from, to, option in view, and the assumption's tag | **Which default nobody believes.** |
| `compared` | the option keys | Whether side-by-side is a real need or one we assumed. |

Batched — a single assumption-edit drag would otherwise fire twenty requests. The page holds events
in memory and flushes on a debounce and on `visibilitychange`.

`assumption_edited` is the reason to do this slice. Two distinct signals fall out of one event:

- An edit to a **sourced** default means our sourced number doesn't match this person's reality —
  either the source is stale or the default is a bad central estimate for real Maine homes.
- An edit to an **unsourced** placeholder is a direct vote on which honest unknown
  (`installed_cost_per_w`, `residual_coverage`, the resilience value, `electrician_cost`) to
  research first. Right now that ordering is a guess.

Recording `from` and `to` matters more than the count: the *direction and magnitude* of the
correction is the research finding. Ten people all raising `installed_cost_per_w` from $2.95 to
about $3.60 is a sourced-number update with evidence, not a vague complaint.

---

## S4 — The one active ask (last, and smallest)

One row under the estimate, inline in the ledger — **not a separate box and not a separate page**. A
feedback page is a product; this is a row.

The interaction: 👍 / 👎, and **on click** a single optional text box appears ("what didn't add
up?"). Click first, text second — nobody types into a box they weren't invited to. Submitting
attaches the current scenario URL, which already encodes option, bill, usage, and every edited
assumption (R8b, shipped in W2). That attachment is the whole design: a thumbs-down alone is noise;
a thumbs-down *with the scenario that produced it* is reproducible.

**What the thumb actually adds:** on its own, very little. Almost nobody clicks these and the ones
who do are unrepresentative. Its real function is as an **affordance** — a visible thumb is what
signals that feedback is wanted here, which is what gets someone to use the text box. The thumb is
the door; the text is the room. Judge it on whether text submissions happen at all, not on the
up/down ratio.

It goes last because it's the lowest-yield slice. It's in the plan because it's a few hours and it
catches the one thing passive data structurally cannot: a person who thinks the whole framing is
wrong.

---

## What closes the loop (and what deliberately doesn't)

```
no traffic at all                       ──►  the problem is distribution, not the calculator
assumption_edited on an unsourced key   ──►  a research question in solar-investment-research
assumption_edited on a sourced key      ──►  re-check the source; is our default stale or wrong?
intent=out_of_scope, repeated           ──►  docs/BACKLOG.md
intent=feedback                         ──►  read it
a thumbs-down with a scenario URL       ──►  open the URL, reproduce, decide
mcp_tool_call from a real client        ──►  the agent-native thesis has a user
```

Every arrow ends at a human. That's the design, not a limitation we'll grow out of: the loop between
"a number looks wrong" and "a sourced number lands" already exists — it's the research repo — and
this is its intake, not a replacement for it. The compound-engineering version (an agent that reads
the log, drafts research questions, opens them) is a real thing to build *later*, and a much better
thing to build once there's a month of real events to test it against. Building it now means
designing an automation against imagined data.

**Never:** auto-editing `assumptions.py`. It collides head-on with the founding rule and would
convert one confused visitor into a wrong sourced default.

---

## Sequencing and size

```
S1 request log + MCP  ──►  S2 intent field  ──►  S3 client events  ──►  S4 active ask
   (~half a day)           (~2 hours)             (~a day)             (~half a day)
```

S1 ships alone and is immediately useful. Do not start S3 before the deploy is live and S1 has
recorded something real — the first actual events will change what's worth recording, and that's
cheaper to learn than to design around. If S1 shows nobody visits at all, S3 and S4 are answering a
question nobody asked and the real work is somewhere else entirely.

## Definition of done

- `pytest tests service/tests` passes; `python tools/verify_web.py check` exits 0.
- The page renders and answers identically with `/events` returning 500, and with it absent.
- A real edit on the deployed page appears as one line in `/data/.feedback.jsonl`.
- With the log at its byte ceiling, appends refuse, `/health` says so, and `/ask` still answers.
- With the volume near full, the log refuses to append and the spend ledger still writes.
- The page states, in plain English, what it collects — including the IP and the retention.
