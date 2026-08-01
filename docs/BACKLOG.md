# Backlog

Ideas captured, not scheduled. **Nothing here is committed** — don't pull an item into work
without a deliberate decision.

> **Provenance: agent-generated, lightly human-reviewed.** This file and the four plans it points
> to (`docs/plans/2026-07-29-*`, `docs/plans/2026-07-30-001-*`) were written by Claude from the raw
> notes in `docs/ideas/ideas.md` and from a verification pass. A human has read them for direction,
> not line by line: the tiering, the effort estimates, the "why now" arguments, and every number in
> the plans are an **agent's proposal**. The human-authored source is `docs/ideas/ideas.md` — when
> this file says something that isn't traceable there or to a commit, treat it as a suggestion that
> hasn't been checked. Items are not committed work and effort marks are guesses.

Formalized 2026-07-29 from three sources: the previous backlog (concept + `STRATEGY.md` + the
Phase 1 brainstorm), the working notes in `docs/ideas/ideas.md`, and findings from the first real
verification pass against the live Railway deploy. Revised 2026-07-30 to add Tier 0, which is the
question the rest of the file assumes an answer to. `docs/ideas/ideas.md` stays as the raw scratch
pad; **this file is the formal version** — when the two disagree, this one wins.

## How to read this

Each item carries an effort and a **why-now**, because the hard part of picking work here is not
"is this a good idea" (most are) but "what does this unlock, and what breaks if I skip it."

| Effort | Means |
|---|---|
| **S** | An afternoon. |
| **M** | A day or two. |
| **L** | A week+, or needs research to land first. |
| **?** | Genuinely unscoped — the first task is scoping it. |

Four items have build-ready plans written and are marked **→ PLAN**. Those are the ones to reach
for first if you come back with limited time and want to just start.

---

## Tier 0 — is this worth pursuing at all

*Why this tier exists: every other item below is a "make it better" item, and none of them asks
whether better is the constraint. The tiers underneath are ranked as if the answer is "yes, for
strangers, indefinitely" — which nobody has decided. **Tier 0 changes the ranking of Tiers 1–7,
so doing it after them is doing them on a coin flip.***

- **→ PLAN** `docs/plans/2026-07-30-001-decide-is-this-worth-pursuing.md` — **[M, mostly waiting]**
  the three meanings of "worth it", a cost baseline, a three-arm trial (free first), pre-registered
  thresholds, and a verdict that re-ranks this file.
- **Nobody has measured what this costs.** **[S]** Railway invoice + actual Anthropic spend to
  date. "It loses money but people use it" is unreadable without the number after "loses."
- **Nobody has measured whether anyone uses it.** **[S]** The instrumentation shipped 2026-07-21
  and the log has never been read as a whole. Do this before building anything that assumes an
  audience.
- **How to monetize — and whether to.** **[?]** *In the raw notes and missing here until
  2026-07-30.* The honest finding in the plan: the only mechanism with real money in it
  (installer lead generation) is the exact thing this tool was built as an alternative to, and
  taking it means retiring `STRATEGY.md` rather than extending it. The non-conflicting paths
  (white-label to a nonprofit or Efficiency Maine, a grant, sponsorship) are small and slow.
  **Don't drift into lead-gen one feature at a time** — it's a product change, decided in writing
  or not at all.
- **`STRATEGY.md` may already be out of date.** **[S]** It says the audience is the author and
  that helping others is "a welcome bonus, not the goal." Much of Tiers 1 and 4 only makes sense
  if that has changed. Either update the strategy or cut the work — the current pairing is
  incoherent and costs an afternoon to fix.
- **Instrumentation gaps that would make any trial unreadable.** **[S]** Query strings aren't
  logged (so `utm_source` is invisible and trial traffic can't be separated from organic); there's
  no session id (funnels fall back to `(ip, ua, day)`, which is both less accurate *and* more
  identifying than a random per-tab id); nothing asks "did this help you decide?". Details in the
  plan.

## Tier 1 — the deploy can still break silently

*Why this tier is first: on 2026-07-29 the site went down during a routine redeploy and nothing
told anyone. It came back only because someone happened to be looking. Everything below is a
variant of "we would not know."*

> **Contingent on Tier 0.** This tier's value is proportional to how many strangers are on the
> site. If the verdict is NARROW (a personal tool), most of it should be cut rather than
> scheduled. The one exception is cache-busting, which a trial needs in order to be readable —
> take that slice early, leave the rest until there's a verdict.

- **→ PLAN** `docs/plans/2026-07-29-001-feat-deploy-hardening.md` — **[M]** covers the next four
  items as one piece of work.
- **Static assets are cached with no cache-busting.** **[S]** Proven live: after deploying a new
  `web/app.js`, a returning browser kept serving the old one. For an *instrumentation* change this
  is worse than cosmetic — the events silently don't fire and the log looks like nobody edits
  anything. Needs a version query string or content-hashed filename.
- **No post-deploy smoke check.** **[S]** The Railway healthcheck hits `/health`, which returned
  200 while `/mcp` had been 421 for a week. A healthcheck that only proves the process is alive
  isn't a healthcheck for this app.
- **Dependency ceilings are now set but unowned.** **[S]** `requirements.txt` pins majors as of
  2026-07-29. Nothing tells you when a ceiling is holding you back on a security patch. Decide on
  a cadence for deliberately raising them (tests + a deploy behind each bump).
- **No favicon.** **[S]** Every page load logs a 404. Trivial, visible in every console.
- **`/health` doesn't report which commit is running.** **[S]** Diagnosing today's outage needed
  SSH to answer "is the deployed code the code I'm reading." A `version` field with the git SHA
  would have replaced a chunk of that.

## Tier 2 — correctness has an expiry date

*The founding rule is "sourced defaults trace to research." That's a claim about freshness, and
right now nothing checks it. There is also one known-wrong number.*

- **→ PLAN** `docs/plans/2026-07-29-003-fix-source-freshness-and-arbitrage.md` — **[M]** the
  known calculation error plus a freshness check.
- **The time-of-use arbitrage is ~1.9% too generous.** **[S]** *Known bug, carried from
  `docs/ideas/ideas.md`.* The master equation values each shifted kWh at on-peak minus off-peak
  ($0.367366) as if charging were lossless. Fix in the research repo first, then here — that
  ordering is the founding rule, not bureaucracy.
- **Sources go stale on a schedule we don't track.** **[M]** `maine.gov/energy/electricity-prices`
  updated 2026-07-01 and nothing noticed. The NEB article behind several defaults is from 2024.
  CMP refiles rates; the federal credit is a political object.
- **A third of assumptions ship `unsourced — pending research`** and the research order is a
  guess. **[S once there's data]** The `assumption_edited` event was built to answer exactly this
  — it now works (fixed 2026-07-29), so this unblocks itself as traffic arrives.
- **Validate against real bills.** **[M]** Gather actual CMP bills and check projections against
  reality. The tests prove internal consistency, not that the examples still describe Maine.
- **Battery lifetime and pricing are thin.** **[M]** 10-year storage life looks short; battery
  pricing rests on roughly one Tesla Powerwall article.

## Tier 3 — the product argument

*The user-facing complaint that has survived every iteration.*

- **→ PLAN** `docs/plans/2026-07-29-002-feat-financial-argument.md` — **[M]** how the money case
  is presented.
- **The financial argument needs a real shape.** **[M]** Flagged repeatedly in the notes. Wanted:
  non-discounted payback *and* discounted; "if I'd invested this instead, what return would I need
  to match?"; a progressive-disclosure panel showing NPV, IRR and the rest for people who want it.
  This is the differentiator — it's the thing a solar salesperson will not show you.
- **The page is still too busy.** **[?]** Said in the notes after many iterations and a full
  layout bake-off (`docs/design/2026-07-20-layout-bakeoff/`). Three different layouts all looked
  fine on the 4-row default and cramped on `battery+rooftop`. **Scope this before building** — the
  honest read is that density is inherent to a ledger that shows 25 assumptions, so the next move
  may be *progressive disclosure* rather than another layout.
- **Glossary / terminology, linked to the research wiki.** **[S]** Newcomers hit "NEB",
  "arbitrage", "on-peak share" with no way in.
- **Links to learning resources.** **[S]** Adjacent to the glossary.

## Tier 4 — reach

> **Contingent on Tier 0, more than any other tier.** Every item here widens the audience, which
> is only worth paying for if the current audience of one town's worth of people is engaging.
> Widening reach before knowing that is buying a bigger megaphone without checking whether anyone
> liked the first sentence.

- **Zip code or address → utility and rates.** **[M]** Removes the biggest "is this even about
  me?" barrier. Currently CMP is assumed.
- **More states.** **[L]** The single largest audience multiplier, and the one most likely to
  break the architecture's Maine assumptions. Do one second state as a spike before promising N.
- **CMP vs Versant side by side.** **[M]** The in-Maine version of the same idea, much cheaper.
- **Leasing / PPAs / non-purchase financing.** **[L]** A large share of real residential solar,
  and the returns work completely differently. Currently invisible.
- **Commercial / non-residential.** **[L]**
- **Efficiency Maine programs, heat-pump payback.** **[M]** Other ways to cut the bill — arguably
  a better answer than solar for some visitors, which is on-thesis.
- **Native mobile app.** **[L]** Nothing yet suggests the website is the constraint.

## Tier 5 — agent-native and self-improvement

- **Expose the *research* repo as MCP tools.** **[M]** The calculator half shipped 2026-07-20;
  this is the other half, and it's what would let an agent check a number's provenance.
- **An agent that reads the event log and drafts research questions.** **[M]** Deliberately not
  built yet, and the reason is good: build it against a month of real events rather than imagined
  ones. **Never** let it auto-edit `assumptions.py` — that collides head-on with the founding rule.
- **Cache/route more example queries** so the LLM doesn't re-infer common ones. **[S]** Every
  `/ask` already logs its question with a `cached` flag, so the ranking falls out of the log:
  `grep '"kind": "ask"' /data/.feedback.jsonl | jq -r .question | sort | uniq -c | sort -rn`.
- **More interaction with the agent / the agent soliciting feedback.** **[?]** Notes say this needs
  fleshing out. Agreed — it's a direction, not an item.
- **Full agent-native parity** across every surface. **[M]** Mostly true today; needs an audit to
  find where it isn't.

## Tier 6 — modeling gaps

- **Plug-in battery: the over-the-line "rescue" case.** **[M]** *Deferred 2026-07-20.* Currently
  modeled for exactly one situation — a home already under the 15.8% on-peak line. Over it, the
  baseline becomes the flat rate, the battery must first claw back the enrollment penalty, and
  break-even installed cost *falls* as on-peak share worsens ($908/kWh at 16% → $581 at 25% → $363
  at 40%). Presenting both through one set of outputs is what made it unreadable ("Case 1/2/3"),
  so the code refuses rather than half-answers. **Reviving it needs a UI answer first** — probably
  a separate question ("your evenings are expensive; can a battery rescue you?") — plus the honest
  caveat that winter electric heat is the on-peak load a small plug-in usually can't reach. Math
  preserved in `src/tou.py` (case 3) and at `071b18b`.
- **Installed battery's `tou_enrolled` mode still speaks in cases.** **[S]** `src/battery.py`
  names "Case 2 / Case 3" in step labels. Off by default, so it escaped the 2026-07-20 cleanup —
  same readability complaint applies if it ever becomes prominent.
- **Community-inclusive combinations** (community + rooftop, etc.). **[M]**
- **Inflation** handled explicitly rather than folded into escalation. **[S]**
- **Non-ROI reasons to buy**: energy security, resilience, disaster preparedness. **[S]** Partly
  present as `resilience_value_per_year`, deliberately $0 by default.
- **Advanced input**: line-item bill breakdown, monthly history, $/kWh, past N months. **[M]**
- **Bill ingestion**: photo or PDF upload, auto-parse line items, user confirms. **[L]** High
  delight, high effort, and it makes every other input path optional.
- **Keeping up with legislation changes.** **[?]** Related to source freshness; the federal credit
  is the obvious exposure.

## Tier 7 — the repo itself

- **`CLAUDE.md` and its surrounding docs keep growing.** **[S]** Called out in the notes ("uh
  oh"). It is now long enough that it competes for attention with the code it describes. A
  deliberate prune — moving detail into the docs it already links — is overdue.
- **Regular tidying.** **[S]** Ongoing.
- **More user testing.** **[?]** The instrumentation now exists to make this cheap; what's missing
  is anyone to test with. Distribution, not tooling. **Promoted into Tier 0** as arm 1 of the
  trial (five people, in person, $0) — it's the highest-signal thing on this entire page and it
  was sitting in the last tier.

---

## Explicitly not doing

Recorded so they don't get re-litigated:

- **A dashboard, a database, an analytics vendor, or accounts** for the event log. At ten visitors
  a month you read the log. `duckdb -c "select kind, count(*) from
  read_json_auto('/data/.feedback.jsonl') group by 1"` when reading gets old.
- **Anything that auto-edits `assumptions.py`** from user feedback. Founding-rule violation:
  it converts one confused visitor into a wrong sourced default.
- **Routing on the `intent` label.** It is logged and never acted on. A misclassification must
  never be able to stop the page calculating.
- **Horizontal scaling.** The spend ledger and rate-limit buckets are per-instance with no atomic
  increments; N replicas means N × the daily cap. Fix the ledger before touching `numReplicas`.
