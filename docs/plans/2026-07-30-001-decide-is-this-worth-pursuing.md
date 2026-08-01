---
title: "decide: is this worth pursuing — the viability trial"
type: decide
status: ready
date: 2026-07-30
---

> **Provenance: agent-generated, lightly human-reviewed.** Written by Claude on 2026-07-30 from a
> human prompt ("is there even a business case? how would I assess, test, run a trial?"). The
> framing, the thresholds, and the cost estimates are an agent's proposal, not a researched market
> analysis. **The numbers in "Pre-registered thresholds" are guesses that a human must accept,
> change, or reject before any money is spent** — pre-registration only works if a human owns them.

# decide: is this worth pursuing — the viability trial

## Summary

Every other plan in `docs/plans/` answers *how to build this better*. None of them answers **whether
to keep building it at all**, and the answer changes which of them are worth doing. This plan is the
missing one: define what "worth pursuing" could mean here (three different answers, only one of them
commercial), establish the cost side nobody has measured, run a **bounded distribution trial** with
thresholds written down in advance, and come back with a go / narrow / stop verdict that re-ranks
the backlog.

Cost of the trial: **~$0 for the first arm, $150–300 if it gets to paid**. Elapsed: ~4 weeks, most
of it waiting.

## Problem Frame

The project is deployed, correct, instrumented, and — as far as anyone knows — unused. The backlog
formalized on 2026-07-29 has 40-odd items across seven tiers, three with build-ready plans, and
**every one of them is a "make it better" item.** Not one asks whether better is the constraint.

That gap matters because the existing plans are not equally valuable under different answers:

| If the honest answer is… | Deploy hardening (`-001`) | Source freshness (`-003`) | Financial argument (`-002`) |
|---|---|---|---|
| **A personal decision tool** (STRATEGY.md's stated audience) | Mostly wasted — nobody is there to notice an outage | Matters, but a chore reminder does it | Still the point: it sharpens *your* model |
| **A public utility for Maine homeowners** | Necessary — silent breakage is the whole risk | Necessary — strangers relying on stale numbers is the harm | Necessary |
| **A business** | Necessary, plus everything not yet listed | Necessary | Necessary, and probably reshaped around a funnel |

So sequencing the backlog without answering this is sequencing on a coin flip. That is the real
reason to do this first, ahead of work that is individually well-argued.

**There is also a live contradiction to resolve.** `STRATEGY.md` says the audience is "a Maine
homeowner working through their own solar decision — starting with the author… Helping others is a
welcome bonus, not the goal." If that is still true, most of Tier 1 and Tier 4 should be cut, not
scheduled, and this trial is unnecessary — the tool has already succeeded. The fact that a trial
feels worth running suggests the strategy has drifted and hasn't been updated to say so. **Deciding
which document is out of date is step one and costs nothing.**

## The three things "worth it" could mean

Naming them separately matters because they have different evidence, different costs, and mostly
exclude each other.

### (A) It already succeeded — a personal tool and a build artifact

The author now has a defensible model of Maine solar economics, a live service, an MCP server, and a
verification harness. Under this reading the remaining question is only *"which upkeep is worth an
afternoon"*, and the honest answer to most Tier 1/Tier 4 work is **no**.
**Evidence needed:** none. This is already true. The question is whether it is *sufficient*.

### (B) A public good — low cost, real usage, no revenue

"This loses money but people use it and it's helping." This is a genuine outcome and probably the
most likely good one. It requires exactly two facts: **cost is small and bounded** (it is — see
below) and **someone is actually using it** (unknown, and the point of the trial).
The bar is deliberately low; the failure mode is not "not profitable," it's "nobody comes."

### (C) A business

Requires a revenue mechanism, and **this is where honesty bites hardest.** The candidates:

| Mechanism | Realistic? | The problem |
|---|---|---|
| **Installer lead generation** | The only one with real money in it. Solar leads sell for ~$50–250 | **It destroys the product.** The entire premise is "not a biased installer quote." A calculator that sells your details to installers *is* the thing this was built against. Adopting it means building a different product and retiring `STRATEGY.md`. |
| **Affiliate on balcony/plug-in kits** | Plausible, small | Lower conflict than lead-gen but the same direction: the calculator now has a preferred answer. Would need to be disclosed on-page, and the recommendation logic audited by someone who isn't the affiliate. |
| **White-label / license to a nonprofit, co-op, or Efficiency Maine** | Plausible, one-off | Not a product business; a consulting engagement with a code deliverable. Notably **has no conflict** — their interest is the same as the reader's. |
| **Sponsorship or a grant** (state energy office, climate nonprofit) | Plausible, small, slow | Closest to (B) with the lights paid for. Realistically needs usage evidence first — which is the trial. |
| **Paid API / MCP access** | Unlikely | `/mcp` is genuinely useful, but the buyer for "Maine residential solar math as a tool call" is not obviously anyone. |
| **Donations** | Near zero | At this scale, noise. |

**The finding to state plainly: the highest-revenue path is the one that breaks the product's
reason to exist, and the paths that preserve it are small.** That is not a reason to stop — it is a
reason to stop expecting (C) and to test for (B) instead. Any trial designed to test (C) would be
designed differently (capture emails, measure lead intent), and doing that half-heartedly inside a
(B) trial produces evidence for neither.

## What this costs today (measure this first — it's an hour)

The cost side of a business case has never been established. Nobody has read the bill.

- **Railway**: base plan + compute + the `/data` volume. Read the actual invoice, not the pricing
  page.
- **Anthropic API**: bounded by `SOLAR_AGENT_SPEND_CAP_USD` (set to $1–2/day) and, in practice, by
  the fact that almost nobody is asking. `/health` reports `spend_usd_today`; the log has every
  `/ask` line with its `cached` flag. **Actual spend to date is the number that matters** and it is
  recoverable from the ledger and the invoice.
- **Domain**: currently $0 — running on `solar-options.up.railway.app`. A real trial arguably wants
  a real domain (~$12/yr); a `.up.railway.app` link in an ad reads as untrustworthy, which would
  confound the result.
- **Human time**: the dominant cost, and the one an agent will systematically under-report.

Write the result into this file as a **Cost baseline** section before the trial starts. A verdict
of "it loses money but it's worth it" is unreadable without a number after "loses."

## What we can already measure (and the four gaps that would ruin the read)

`service/feedback.py` already logs, per line: `request` (method, path, status, ms, ip, ua,
referrer), `ask` (the question verbatim + `intent` + `cached`), `mcp_tool_call`, client events
(`option_selected`, `compared`, `assumption_edited`), and `feedback` (verdict + free text). That is
a genuinely good starting position — the funnel is mostly already there.

**Fix these before spending anything, or the trial produces noise:**

1. **Query strings are not logged.** The request middleware records `request.scope["path"]`, which
   excludes the query. So `?utm_source=reddit` is invisible and **you cannot separate trial traffic
   from organic.** This is the one true blocker. Log the query string (or just an allow-list of
   `utm_*` / `ref` params) on request lines and pass it through on client events. **[S]**
2. **No session identifier.** Funnels have to be reconstructed from `(ip, ua, day)`, which mobile
   carrier NAT will merge and which is also the most privacy-invasive way to do it. A random
   per-tab id in `sessionStorage`, logged with each event, is both **more accurate and less
   identifying** than what is stored today. **[S]**
3. **Cache-busting is unfixed** (`docs/plans/2026-07-29-001`, S2). A returning visitor may run old
   JS and not fire events. Ad traffic is mostly new visitors so the damage is limited, but any
   return-visit metric is untrustworthy until S2 lands. **Take S2 from the deploy-hardening plan
   before the trial; leave the rest of that plan until after the verdict.**
4. **Nothing captures "did this help you decide?"** The `feedback` event captures a verdict and free
   text, which is the right shape, but the trial's central question is decision-usefulness. One
   added prompt — shown *after* engagement, never on arrival — is the difference between "300 people
   loaded a page" and "4 people said it changed what they were going to do." **[S]**

## The trial — three arms, cheapest first

Run them in order. **Each can end the exercise**; do not pre-commit to reaching arm 3.

### Arm 0 — the organic baseline (2 weeks, $0, no work)

Read the log for the two weeks before anything else changes. You cannot interpret a trial without
knowing what a normal week looks like. Expect near-zero; **record it anyway**, because "we went from
0 to 3" and "we went from 40 to 43" are different findings.

### Arm 1 — five real people (1 week, $0, highest signal per dollar)

Sit with **three to five actual Maine homeowners** — neighbors, colleagues, the local subreddit,
anyone with a CMP bill — and watch them use it without help. Do not explain it. Note where they
stop, what they misread, and whether they say anything like "so I'd do X."

n=5 moderated sessions beat 300 anonymous ones for the question *"does this change a decision?"*,
and this arm can end the whole exercise in either direction: if five people find it genuinely
useful, (B) is confirmed and the ad trial is optional; if five people bounce off the density, the
answer is a product problem and no amount of paid traffic fixes it.

**This arm also directly tests the Tier 3 complaint** ("the page is still too busy") with real
evidence instead of the author's own taste, which is the honest reason that item is still `[?]`.

### Arm 2 — free distribution (1 week, $0)

One honest post in each of two or three places where the audience actually is: `r/Maine`,
`r/solar`, a Maine homeowners or off-grid Facebook group, a Front Porch Forum-style local list.
Not an ad — a "I built this to answer my own question, here's what I learned about CMP rates" post,
which is the format those places tolerate and paid ads are not.

**Predicted to outperform paid**, and if it does, that *is* the finding: distribution is free and
the answer to Tier 7's "more user testing — distribution, not tooling" is a Reddit account.

### Arm 3 — paid trial (2–3 weeks, $150–300)

Only if arms 1 and 2 leave the question genuinely open — e.g. people who arrive find it useful, but
nobody arrives.

| Channel | Budget | Why | Warning |
|---|---|---|---|
| **Google Search**, long-tail informational (`"is community solar worth it in maine"`, `"cmp time of use rate worth it"`) | $75 | Highest intent by far; the reader is mid-decision | **Solar is one of the most expensive keyword verticals there is** — lead-gen buyers with $100+ per-lead economics set the price, and a free calculator cannot outbid them. Stay off head terms (`solar panels maine`); they will eat $75 in a handful of clicks. |
| **Reddit**, geo-targeted Maine + solar subreddits | $50 | Cheap clicks, right audience, tolerant of "I built a thing" | Low intent; expect a poor engagement rate and don't over-read it |
| **Meta**, Maine + homeowner + age band | $75 | Cheapest reach, good for volume | Lowest intent of the three; treat as a page-comprehension test, not a demand test |

Every link carries a distinct `utm_source`, which is why gap (1) is a blocker rather than a nicety.
**Cap the daily spend at the platform level, not by watching it.**

## Pre-registered thresholds — set these before spending

Written in advance so the result cannot be rationalized afterward. **A human must sign off on these
numbers; an agent guessed them.**

Definitions, computable from the existing log:

- **Session** — one `(session_id, day)`; today, one `(ip, ua, day)` until gap (2) is closed.
- **Engaged** — a session with any `option_selected`, `compared`, `assumption_edited`, or `ask`.
- **Deep** — a session with an `assumption_edited` or an `ask`. This is the one that matters: it
  means someone put *their own situation* in, which is the only reason to use this over a generic
  calculator.

On roughly 150–300 trial sessions:

| Metric | Threshold | Reading if missed |
|---|---|---|
| Engaged rate | **≥ 25%** | The page doesn't communicate what it is in five seconds |
| Deep rate | **≥ 10%** | People look but won't invest effort — the transparency premise isn't landing |
| Feedback submissions | **≥ 3 free-text** | Nobody cares enough to type. Weak but real signal |
| Return visits | **≥ 5** | Nobody is coming back to a decision tool for a decision that takes weeks |
| Cost per deep session | **≤ $10** | (B) is affordable at a hobby budget; above this, paid traffic is not the route |

**Arm 1 has one qualitative threshold and it outranks all of the above: does at least one of five
people, unprompted, describe a decision they would make differently?** If yes, the tool works and
everything else is a distribution problem. If no, the numbers above are measuring the wrong thing.

## The verdict, and what each one does to the backlog

Write the verdict into `STRATEGY.md` — not just here — because it changes the audience line, which
is the sentence the whole backlog is implicitly ranked against.

| Verdict | Meaning | Backlog consequence |
|---|---|---|
| **GO (B)** — real usage, small cost | Public good, keep it running | Tier 1 (deploy hardening) and Tier 2 (source freshness) become genuinely necessary; Tier 4 reach opens up; monetization stays closed |
| **NARROW (A)** — nobody comes, but it works | Personal tool that happens to be online | **Cut most of Tier 1 and Tier 4.** Keep Tier 3's financial argument (it serves the author) and Tier 2's arbitrage fix (a wrong number is a wrong number). Consider taking the deploy down and keeping the CLI + MCP |
| **PIVOT (C)** — real demand, needs money | Only if arms 1–3 show unusual pull | Requires a deliberate decision to accept the conflict of interest, in writing, before any lead-gen work — and a rewritten `STRATEGY.md`. Do not drift into this one item at a time |
| **STOP** | No usage, no personal need remaining | Archive with the research repo intact. This is a legitimate outcome and the reason for pre-registered thresholds |

## Definition of done

- **Cost baseline** recorded here: actual Railway + Anthropic spend to date, monthly run rate.
- Gaps (1), (2), and (4) closed; `-001` S2 (cache-busting) landed.
- Arm 0 baseline recorded; arms 1 and 2 run and written up; arm 3 run **only if** 1 and 2 left it
  open, and inside its budget cap.
- A human has accepted or rewritten the thresholds **before** any spend.
- A verdict written into this file **and** into `STRATEGY.md`, with the backlog re-ranked
  accordingly and the cuts actually made — a verdict that deletes nothing wasn't a verdict.

## Out of scope

Building any monetization (lead capture, affiliate links, payments). Analytics vendors, dashboards,
or accounts — the log plus `duckdb` is the analysis tool, per "Explicitly not doing." Expanding to a
second state to widen the trial audience: that is a large modeling change and would confound the
result with a correctness risk.
