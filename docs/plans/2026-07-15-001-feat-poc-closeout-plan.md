---
title: "feat: POC closeout — copy fixes, layout bake-off, state↔text sync, Railway, public MCP"
type: feat
status: active
date: 2026-07-15
---

# feat: POC closeout — copy fixes, layout bake-off, state↔text sync, Railway, public MCP

## Summary

Close out the POC in five workstreams: (1) three small copy fixes to the live page; (2) a
state↔text sync that rewrites the question box from the current scenario and narrates which
assumptions you've edited, which in turn makes an LLM-free cache fall out for free; (3) a
three-way layout bake-off — three live, working pages sharing one `app.js`, judged on the real
thing, winner promoted to `index.html`; (4) a Railway deploy of the static page plus the agent
service; (5) a publicly reachable MCP server exposing the calculator's options, assumptions,
steps, and comparisons as agent tools. Feedback-into-self-improvement is deliberately left as an
open design question at the end, not planned here.

---

## Problem Frame

The calculator's numbers are done and verified. What's left is everything around them.

**The page reads as busy, and its flourishes read as ugly.** That's a symptom with a specific
cause, and it's worth naming precisely before redesigning anything. The current page runs
*three* font families (Fraunces serif, Public Sans, IBM Plex Mono), *five* accent colors (sun,
pine, clay, sky, ink) each with their own background/border pair, plus a paper-grain SVG
texture, two radial background gradients, double-rule borders, a glowing sun mark, pill tags,
counter-based step chips, and dotted-underline buttons. Every one of those was a reasonable
local decision. Stacked, they compete: nothing recedes, so nothing can come forward. That is
also why added flourishes look ugly — a new accent lands in a field that already has four, so it
reads as noise rather than emphasis. The fix isn't better flourishes; it's fewer systems, so the
ones that remain can carry meaning.

**The question box goes stale the moment you refine.** Ask a question, then edit `capacity_kw`
in the drawer, and the box still shows the old sentence while the headline shows new numbers.
The page computes one thing and says another.

**Every question costs an LLM call, including ones the page itself wrote.** `service/agent.py`
sends every question to `claude-opus-4-8` for routing. When the page generated the question
text from its own state, that round-trip is pure waste — it's asking a model to recover a
mapping it already has.

**Nothing is public.** No URL, no deploy. And the backlog's "MCP server exposing the calculator
as tools" is the item that would make the `STRATEGY.md` agent-native-parity claim real, rather
than aspirational.

---

## Decisions taken (from the planning session)

| Decision | Choice |
|---|---|
| Layout bake-off format | Three live pages, `web/layouts/{a,b,c}.html`, sharing the unmodified `app.js` |
| Railway scope | Static page **and** agent service |
| State↔text sync | Both: question box rewrites from state, context line narrates the edit delta |
| MCP shape | Deferred to recommendation — see the MCP workstream below |

---

## Requirements

**W1 — Copy fixes (live page, ships first)**

- R1. A disclaimer at the bottom of the page states this is a proof of concept — not financial
  advice, not a quote, numbers are estimates from sourced-but-general defaults.
- R2. The lede "Ask a plain question, get a fact-checkable answer. Every number below is a
  labeled, editable, sourced assumption — never a black box." is removed.
- R3. The `community` toggle reads "Community solar", not "Community".

**W2 — State↔text sync + cache**

- R4. Editing any assumption, toggling an option, or changing bill/usage rewrites `#question`
  into a plain-English sentence describing the *current* scenario. The box never contradicts
  the headline — including at first paint (see the default-question note in W2).
- R5. The context line under the headline names which assumptions have been edited off their
  sourced defaults (count + labels), so a customized estimate can never be mistaken for a
  default one.
- R6. A question the page generated itself resolves with **zero** LLM calls: the page holds the
  state that produced the text, so it recomputes directly.
- R7. A question the page did *not* generate is cached server-side by normalized text →
  `Extraction`, so a repeat of any question — from any visitor — costs nothing.
- R8. Rewriting `#question` never destroys text the user typed but hasn't asked yet.
- R8b. A scenario is saveable and shareable: the current state (option, bill/usage, edited
  assumptions) is encoded in the URL, and loading such a URL restores it. This is the "run or
  save their query" affordance — no database, no accounts; the URL is the save file.

**W3 — Layout bake-off**

- R9. Three layouts exist as live, working pages at `web/layouts/{a,b,c}.html`, each loading the
  same unmodified `../app.js`, each honoring the full verifier layout contract.
- R10. Each layout is a distinct design *thesis*, not a reskin — they differ in structure and
  information hierarchy, not just palette.
- R11. Every layout ships at most **two** type families and **one** accent color beyond
  ink/paper. Semantic colors (positive/negative NPV, the three assumption tags) are the only
  additions permitted on top of that accent — so hue appears in the accent and these semantic
  roles, and nowhere else.
- R12. The winner's markup + CSS is promoted into `index.html`; `web/layouts/` is deleted.

**W4 — Railway deploy**

- R13. The static page is publicly reachable at a Railway URL.
- R14. The agent service is deployed with `ANTHROPIC_API_KEY` as a Railway secret.
- R15. The spend ledger survives redeploys and uses a **rolling daily window**, not a
  cumulative-forever total.
- R16. `/ask` is rate-limited per IP and caps question length. It is the only path on the deploy
  that can spend money.

**W5 — Public MCP server**

- R17. An MCP server exposes the calculator as tools: list options, get assumptions (with
  sources and explanations), calculate, compare.
- R18. The MCP path calls `src/` directly and makes **no** LLM calls.
- R19. The server is publicly reachable over streamable HTTP on the Railway deploy, and also
  runnable locally over stdio from the same shared tool definitions.
- R20. Loop-driving overrides are bounded in the shared `tools_core` before reaching `src/`
  (`horizon_years`/`battery_horizon_years` ≤ 100), rejecting out-of-range values rather than
  clamping silently. This is what makes public no-auth exposure safe and closes the same latent
  vector on `/ask`.

---

## W1 — Copy fixes

Small, independent, and shipped first so they're done regardless of what happens to the layout
work. All three land in `web/index.html`; the layouts in W3 are then built from this corrected
copy, so they inherit it rather than repeating the fix three times.

| Change | Where |
|---|---|
| Remove the lede paragraph | `web/index.html:254-255` (`<p class="lede">`) |
| `Community` → `Community solar` | `web/index.html:284` (`data-part="community"`) |
| Add POC disclaimer | `web/index.html` footer, `:310-316` |

The disclaimer belongs in the existing `<footer>`, which already carries the "unsourced — pending
research" caveat — it's the page's established place for "read this before you trust it." Draft:

> **This is a proof of concept.** It's a transparency demo, not financial advice and not a
> quote. Every number is an estimate built from general Maine defaults — including some that are
> placeholders awaiting research. Get real quotes before spending real money.

The `Community` → `Community solar` change widens the toggle. Check the toggle row still wraps
cleanly at the 560px breakpoint.

**Verification:** `python tools/verify_web.py run` — `web/` changed, so the Stop gate requires
fresh evidence anyway.

---

## W2 — State↔text sync + cache

### The sync

The page already has everything needed: `OPTIONS[key].describe(assumptions, ctx)` produces a
plain-English scenario phrase for all six option states, and `render()` at `app.js:834` already
calls it for the context line. What's missing is the direction *state → question*, and a delta
against defaults.

Add to `app.js`:

- `questionFromState()` — build the sentence from `currentOption`, `assumptions`, and `readCtx()`.
  Reuse `describe()`; don't invent a second phrasing system that can drift from it.
- `editedAssumptions()` — the keys whose `tag === TAGS.USER_PROVIDED`. The tag machinery already
  tracks this exactly (`app.js:902`), and `renderCompare` already uses it for the ✎ row mark
  (`app.js:777`) — this is the same signal, surfaced in prose.
- Call both from `recompute()`, after the option/assumption state settles.

**First-paint contradiction — fix the default, don't exempt it.** `initPage()` ends with
`selectOption("community")` → `recompute()` (`app.js:979`), so R4 rewrites the box on the very
first paint, before the user has touched anything. Today the hardcoded landing question says
`$150` (`web/index.html:260`) while the default render computes at the `$168.41` sourced Maine
average (`app.js:33`) — so an unconditional rewrite would replace `$150` with a generated
`$168.41` sentence. That's R4 doing its job: the two numbers must not disagree on the one screen
every visitor sees. Resolve it by changing the hardcoded default question to `$168.41` so box and
headline already agree at rest, and keep R4 unconditional. Do **not** exempt first paint — an
exemption ships the exact box-vs-headline contradiction R4 exists to kill.

**R8 (don't clobber typed text) is the subtle one.** The box is an editable input the user may be
mid-thought in. Rule: track `lastGeneratedQuestion` — the exact string the page last wrote into
the box from state. The box is "page-authored" only while `qbox.value.trim() ===
lastGeneratedQuestion`; the moment the user types anything, they diverge and the page stops
overwriting. A user's unasked draft is never destroyed; once they ask, the answer's generated
sentence takes the box back over.

Store the *exact string*, not a boolean — the distinction is load-bearing for Layer 1 below. A
boolean "did the page write the box" flag is `true` after a **sample-button** click too
(`app.js:946-948` writes the box, then asks), which would make the elision below skip the network
and answer whatever the current view is instead of the sample's question. Comparing against the
generated string avoids this: sample text never equals a state-derived sentence, so a sample
correctly routes to the service.

**On R5 and the "too busy" tension.** You picked "both," which adds a line of text — and W3's
whole thesis is that the page says too much. These reconcile only if the delta line is *silent
at rest*: when nothing is edited, it renders nothing at all. It appears only when it has news
("2 assumptions edited from sourced defaults: system size, installed cost"), which is exactly
when it's worth the pixels. Do not render "0 assumptions edited."

### The cache — two layers

**Layer 1: elision (R6).** When the page authors the question, it already knows the state. So
`askQuestion()` short-circuits: if `qbox.value.trim() === lastGeneratedQuestion`, skip the network
entirely and `recompute()`. No LLM, no latency, no spend. This is the layer that matters, and
it's nearly free — the string from R8 already tells you. Match on the exact generated string, not
a "page wrote the box" boolean, so sample-button questions (which the page also writes) still
route to the service rather than silently re-answering the current view.

Worth being clear about *why* this is safe: the page isn't guessing what the text means, it
never stopped holding the state that produced it. There's no interpretation to get wrong.

**Layer 2: server-side extraction cache (R7).** For questions the page didn't write, cache in
`service/agent.py`: normalize the question (lowercase, collapse whitespace, strip terminal
punctuation), hash it, map to the serialized `Extraction`. Check before `extract_node` calls the
model; populate after a successful parse.

This is a safe thing to cache because `Extraction` is a pure function of the question text —
it's routing plus number extraction, explicitly *not* arithmetic (`agent.py:9-10`). The
computation is re-run fresh from `src/` on every request regardless, so a cache hit can never
serve a stale *number* — only a stale *routing*.

But "routing for a fixed string doesn't change" holds only while the routing *target set* is
fixed, and it isn't — combos were added in July, and `docs/BACKLOG.md` lists more options, other
utilities, and other states. If a 7th option ships, every cached question keeps routing to the
old six forever, with no signal. So the cache key is not just the question hash: it's
`hash(normalized_question)` **plus** a version tag `hash(MODEL + OPTION_KEYS + EXTRACT_PROMPT)`. A
version mismatch is treated as a miss, so changing the model, adding an option, or editing the
routing prompt transparently invalidates every stale entry.

Cache negatives too (`unanswerable=true`), or "what's the weather" costs a call every time.

Storage: same JSON-file pattern as `SpendLedger`, keyed by the composite key above, with the same
fail-closed discipline (a corrupt cache should miss, not crash). On Railway it shares the W4
volume.

**Note the existing third layer.** `parseQuestionLocally()` (`app.js:548`) already answers
compare-intent questions and many others with no LLM at all. Layers 1 and 2 sit on top of it.
Between the three, the model gets called only for genuinely novel free-form questions — which
is the only place it was ever earning its cost.

### Save / share a query (R8b)

The sync makes this nearly free, because the page already holds the state as a structured object
(`currentOption`, `assumptions`, `readCtx()`) — the same thing `questionFromState()` reads. Serialize
that into the URL query string and mirror it two ways:

- **Write:** on every `recompute()`, replace the URL (`history.replaceState`, not `pushState` —
  don't spam the back button) with the compact current state. A "copy link" affordance near the
  question box hands the user the URL; the box's own generated sentence stays copyable as before.
- **Read:** on load, if the URL carries state, hydrate `assumptions` / inputs / option from it
  *before* the first `recompute()`, so a shared link opens directly on that scenario — and, via
  R4, with the box already showing that scenario's sentence.

Keep it compact and forward-compatible: encode only assumptions edited off their defaults (the
same `TAGS.USER_PROVIDED` set R5 already computes), not the full ledger, so a typical link is
short and a later assumption addition doesn't invalidate old links. Unknown keys on read are
ignored, not fatal — same fail-soft discipline as the caches. This is pure client-side state in
the URL; it touches neither the service nor W4's storage.

**Verification:** `pytest tests service/tests` — the cache needs service tests (hit, miss,
negative-cache, corrupt-file-misses). LLM stays stubbed, as always. Plus `verify_web.py run` for
the `app.js` changes.

---

## W3 — Layout bake-off

### Structure

```
web/
  index.html          # live page — untouched until you pick
  app.js              # shared, UNMODIFIED by this workstream
  layouts/
    a.html            # thesis A
    b.html            # thesis B
    c.html            # thesis C
```

`app.js` must not change here. That's the constraint that makes the bake-off honest: if a layout
needs JS changes to work, it's not a layout, and the comparison stops being apples-to-apples.

### The contract every layout must honor

`tools/verify_web.py` and `app.js` together pin a specific set of hooks. Any layout missing one
renders nothing or fails the gate. The full list, from the `app.js:8-15` contract comment and the
`querySelector` calls:

| Hook | Kind | Used by |
|---|---|---|
| `#question`, `#ask`, `.sample` | id / class | question flow |
| `#result`, `#detail`, `#tip-body`, `#notice`, `#parity-banner` | id | render targets |
| `#refine` (a `<details>`), `#reset` | id | refine drawer |
| `#bill`, `#bill-row`, `#bill-tag`, `#annual-usage` | id | shared inputs |
| `button.toggle[data-part]` (×4) | class + attr | option state machine |
| `.big`, `.step-label`, `.cmp-table`, `.context`, `.npv-what`, `.npv-def` | class | verifier assertions + render |
| `aria-label` on `#question`; `aria-pressed` on each `.toggle`; `aria-expanded` on `.npv-what`; `role="status"` on `#notice`; `role="group"` on the toggle container | ARIA | accessibility; read by `/verify-web-page`'s a11y snapshot |

Treat this as the skeleton API. Layouts may restyle and rearrange these freely; they may not
rename or drop them. The ARIA row is part of the contract, not a nicety: the current page carries
all of it, an implementer building a fresh `<body>` from a hooks-only list would drop every bit,
and the perception loop you judge layouts with (`/verify-web-page`) reads the accessibility tree
— a layout with no ARIA produces a worse snapshot no matter how it looks.

### The three theses

Deliberately spread, so the bake-off surfaces a *direction*, not a favorite shade.

**A — Editorial.** The current page's ambition, disciplined. One column. Fraunces for the
headline and section heads only; Public Sans everywhere else; **no monospace** — tabular-nums on
Public Sans carries the numbers. One accent (the sun ochre). No paper grain, no radial
gradients, no sun mark. Cards become hairline rules — content is separated by space and a single
line, not by five boxes each with border+shadow+radius. Tests the hypothesis that the current
design is *right* and merely over-dressed.

**B — Ledger.** The page as a financial statement, which is what it actually is. Near-monochrome:
ink on paper, hairline rules, everything on a tabular grid. Monospace for every number, sans for
every label, no serif at all. The step chain and the assumption ledger become the same visual
object (they're the same *kind* of object — a labeled row with a value and a provenance tag).
Hue appears in exactly two places: NPV sign, and the three assumption tags. Tests the hypothesis
that the transparency thesis wants austerity, and that the numbers should be the only thing with
color.

**C — Product.** Modern, calm, neutral. System font stack only — one family, weights doing the
work that three families do now. Neutral grays, one blue-ish brand accent, generous whitespace,
soft cards with a single elevation level (not the current border+shadow+radius+texture stack).
Familiar SaaS shapes: the estimate is a stat block, assumptions are a settings list. Tests the
hypothesis that "trustworthy" reads as "professional and unremarkable" rather than "crafted."

Each layout ships the W1 copy fixes and renders the W2 sync, so all three are judged on the
final content.

### Verifying the layouts

Here's a real snag worth flagging before it bites: `tools/verify_web.py` hardcodes
`web/index.html` (`:294`) and hashes `WEB_FILES = ["web/index.html", "web/app.js"]` (`:40`) for
gate freshness. So out of the box the deterministic loop can't drive a layout file, and the Stop
gate won't cover `web/layouts/`.

Do the minimum that keeps the gate honest:

- Add `verify_web.py run --page web/layouts/a.html` (default stays `web/index.html`). Small
  change: thread a path through `run()` and the driver-shim builder.
- **Leave `WEB_FILES` alone.** The gate should keep protecting the live page. Bake-off candidates
  are exploratory and shouldn't be able to block a turn — and when the winner is promoted into
  `index.html`, the normal gate covers it automatically with no further change.

Then judge each candidate with `/verify-web-page` (the perception loop) — for a question that is
literally "does this look and read right," an a11y snapshot plus a screenshot judged against
intent is the tool that actually answers it. The deterministic loop only proves it renders.

### Picking

Drive all three and screenshot each in the **same three states**, then look at them side by side.
The states are not optional detail — they are where layouts actually break:

- **`community`** — the sparse case: 4 steps, 4 assumptions. Every layout looks fine here.
- **`battery+rooftop`** — the dense case: 8 steps and ~16 assumptions (every `battery_`-prefixed
  key). This is where whitespace budgets, ledger density, and type scale get stress-tested, and
  where an editorial layout that breathes at 4 rows can suffocate at 16.
- **`compare`** — the 6×5 side-by-side table that already needs `overflow-x:auto`. Tests how each
  layout handles wide tabular content without the page body scrolling sideways.

Judging only the community default and then promoting means the winner meets the combo and
compare views for the first time *after* `web/layouts/` is deleted — exactly when it's most
expensive to discover a layout can't carry them.

The promotion (R12) is a separate, deliberate step — copy the winner's `<style>` + `<body>` into
`index.html`, delete `web/layouts/`, run the full gate.

---

## W4 — Railway deploy

The service is closer to deployable than it looks: `service/app.py` is already FastAPI with CORS
wide open (`:32`) and a `/health` endpoint (`:57`). What's missing is config, persistence, and
the fact that **opening `/ask` to the internet turns a local convenience into a spend surface.**

### Two real problems to fix before this is public

**1. The ledger trips once and never recovers.** `SpendLedger` accumulates `total_usd` forever
and `over_cap` is `total_usd >= cap_usd` (`spend.py:60-61`). Locally that's correct — it's a
lifetime budget for a dev machine. Publicly, it means the service works until it has spent $5
*in total, ever*, then serves `cap_exceeded` permanently until someone SSHes in and deletes a
JSON file. That's not a cap, that's a fuse.

Fix: rolling daily window. Store `{"day": "2026-07-15", "total_usd": ..., "calls": ...}`; on read,
if `day != today`, treat the total as 0. Keep the existing fail-closed-on-corrupt behavior
(`:52-53`) — it's right, and it's the kind of thing that's easy to lose in a refactor.

**2. Railway's filesystem is ephemeral.** The ledger resets on every redeploy — which, with the
current cumulative design, is the *only* reason the fuse ever un-blows. Attach a Railway volume
at `/data`, set `SOLAR_AGENT_LEDGER_PATH=/data/.spend.json`, and put the W2 extraction cache
alongside it at `/data/.extraction-cache.json`. Single instance only; don't scale this
horizontally without moving the ledger to something with atomic increments.

### Abuse surface

`/ask` is unauthenticated, public, and spends money per call. The daily cap bounds the damage to
`$cap`/day, which is the important guarantee. On top of it (R16):

- Per-IP rate limit on `/ask` (a small in-process token bucket is proportionate here; don't add
  Redis for a POC). **Key it on the real client IP, not `request.client.host`** — Railway
  terminates TLS at a proxy, so `request.client.host` is the *proxy's* address for every request,
  and a bucket keyed on it either throttles the whole internet as one client or (if you exempt the
  proxy) throttles nobody. Run uvicorn with `--proxy-headers --forwarded-allow-ips=*` and key the
  bucket on the first `X-Forwarded-For` hop. The same fix makes any per-IP logging meaningful.
- Reject questions over ~500 chars before they reach the model — cheap, and it kills the "paste a
  novel to burn tokens" move.
- Keep the cap low to start ($1–2/day). It's a POC; a tripped cap degrades to the local parser,
  which answers most questions anyway (R7 in the original plan, and it's verifier-enforced).

The W2 cache helps here too: repeat questions from different visitors don't re-spend.

### Deploy shape

One Railway service, FastAPI serving both:

- `app.mount("/", StaticFiles(directory="web", html=True))` — the page and `app.js` from the same
  origin, which incidentally makes CORS a non-issue for the deployed page.
- `SERVICE_URL` in `app.js` (`:37`) is hardcoded to `http://127.0.0.1:8765/ask`. Same-origin
  deploy means this should become a relative `/ask` when not on `file://`. Keep the localhost
  path working for the file:// dev flow the verifier drives — the fallback notice is
  verifier-enforced and must not regress.
- `railway.toml` + start command: `uvicorn service.app:app --host 0.0.0.0 --port $PORT
  --proxy-headers --forwarded-allow-ips=*` (the proxy flags are what make the per-IP rate limit
  above see the real client).
- Env: `ANTHROPIC_API_KEY` (secret), `SOLAR_AGENT_SPEND_CAP_USD`, `SOLAR_AGENT_LEDGER_PATH`.

Do this **after** W3's winner is promoted. No point deploying a page you're about to replace.

---

## W5 — Public MCP server

### Recommendation, since you asked

**Build it, host it publicly, and don't put auth on it.** The reasoning is short and it's
specific to this project rather than general MCP enthusiasm:

**The MCP path needs no LLM.** The agent calling your tools *is* the LLM. It arrives having
already decided it wants `calculate(option="rooftop", overrides={"capacity_kw": 8})`. So the
tool is pure Python arithmetic over `src/` — no `ANTHROPIC_API_KEY`, no spend ledger, no cap, no
`cap_exceeded` state to reason about. Every hard problem in W4 simply doesn't exist on this
path. That's what makes "publicly accessible" cheap here, and it's why my answer would be
different for almost any other tool you might expose.

There's no user data, no secrets, and nothing to authorize — it's a calculator over public
Maine energy data. Auth would protect nothing while guaranteeing nobody tries it. The only real
risk is compute abuse — and here the plan has to earn the claim rather than assert it. The
compute is microseconds *for well-formed inputs*, but not for attacker-chosen ones: `overrides`
is the `--set` mechanism, which can set `horizon_years`, and `capital.compare()` validates only
`horizon_years >= 1` with no ceiling (`src/capital.py:64-65`) before building one `YearRow` per
year into a list (`:71-75`). So `calculate(option="rooftop", overrides={"horizon_years": 1e9})`
is a single-request memory blowup that a rate limit — which bounds request *frequency* — does
nothing to stop. The mitigation is bounding the inputs, not the request rate (see the input-clamp
requirement in Structure below). Rate limiting from W4 covers ordinary flooding; the clamp covers
the one-shot blowup. With both, "publicly accessible with no auth" is honest.

Note this same vector already reaches `/ask` today: `Extraction.inputs` is an open
`dict[str, float]` and `_apply_inputs` applies any key that matches an assumption
(`service/agent.py:108-126`) — it's latent only because the service currently binds to
`127.0.0.1`. The clamp belongs in the shared `tools_core` so both surfaces inherit it.

And it's the *right* tool to expose, because of what it returns. Most calculator APIs hand back
a number. This one hands back the number **plus** the labeled assumptions, their sources, what
each source *is* and why it's credible, and the full step chain — every field already exists in
the CLI `--json` payload. An agent using this can cite its work and a user can fact-check it.
That's the `STRATEGY.md` transparency thesis in the shape an agent can actually consume, and
it's the backlog's "full agent-native parity" item made real.

Build stdio too — it's nearly free once the tool definitions are shared, and it gives you a
zero-hosting local path for development and testing.

### Tool surface

| Tool | Returns |
|---|---|
| `list_options()` | The six option states: key, label, blurb, whether it needs a bill |
| `get_assumptions(option)` | Full ledger: key, label, value, unit, tag, source (title/url/note/what_is_it), explain |
| `calculate(option, monthly_bill?, annual_usage_kwh?, overrides?)` | The CLI `--json` payload: inputs, assumptions, steps, result |
| `compare(options[], monthly_bill?, annual_usage_kwh?)` | Side-by-side rows: upfront, year-1 savings, payback, NPV |

`overrides` is the `--set` mechanism (`cli.py`), so agent-native parity is literal: anything
`--set` can do, an agent can do.

### Structure

- `service/tools_core.py` — pure functions wrapping `src/`, stdlib-only. The core one,
  `calculate(option, inputs)`, is **`agent.py:compute_payload()` moved here**, not reimplemented
  alongside it: that function (`service/agent.py:129-159`) already routes the option, applies
  inputs, and calls `capital_spec()` / `render_capital_json()` / `render_community_json()` — it is
  exactly what the MCP `calculate` tool needs. `agent.py` then imports it back. Moving rather than
  copying is the whole point of a shared core: in a repo whose discipline is one source of truth
  plus parity checks, a second payload builder is precisely the drift that machinery exists to
  prevent. One definition, three callers (`/ask`, MCP, CLI-shaped tests).
- **Input clamp lives here (the W5 no-auth security requirement).** `tools_core` bounds every
  loop-driving override before it reaches `src/` — `horizon_years` and `battery_horizon_years`
  capped at ≤100. Reject out-of-range values with an error rather than silently clamping, so the
  answer an agent gets can never quietly differ from what it asked. Because both `/ask` and the
  MCP path route through `tools_core`, both inherit the bound; it closes the latent `/ask` vector
  noted above at the same time.
- `service/mcp_server.py` — tool registration over `tools_core`.
- Mount at `/mcp` on the same FastAPI app (streamable HTTP) for public use; `python
  service/mcp_server.py --stdio` for local.
- Add `mcp>=1.2` to `requirements.txt`.
- Tests in `service/tests/` — no stubbing needed, there's no model in this path. Assert the
  payloads match `cli.py --json` for the same inputs (the parity claim stated as a test), and that
  an over-range `horizon_years` override is rejected rather than materialized.

Public URL lands at `https://<app>.up.railway.app/mcp`, addable as a custom connector.

**Sequencing:** W5 touches no web code and shares only the deploy with W4. It can be built at any
point — including in parallel with the layout bake-off, since the two can't conflict.

---

## Open — feedback into a self-improvement loop

Not planned here; you flagged it as needing discussion, and it's the item where building the
wrong thing is easiest. Framing for that conversation, so it starts from the real decisions:

- **What's captured?** Freeform text, a thumbs rating, or the high-signal thing — the actual
  scenario state (option + edited assumptions) when someone bothered to complain. The third is
  the only one that tells you *which assumption* was wrong.
- **What closes the loop?** The honest answer for this project is probably not "the agent
  rewrites itself." It's that feedback naming an unsourced or wrong default becomes a research
  question for `solar-investment-research` — which is the repo whose whole job is landing sourced
  numbers. The loop already exists; feedback would be its intake.
- **What stops it going wrong?** Anything auto-editing `assumptions.py` collides directly with
  "sourced defaults trace to research; the calculator never invents numbers." A human-reviewed
  queue is the conservative shape.
- **Where does it live?** Storage means a database, which is the first real statefulness in the
  project. Worth knowing that's the cost before signing up.

---

## Sequencing

```
W1 copy fixes ──► W2 sync + cache ──► W3 bake-off ──► promote ──► W4 Railway
                                                                     ▲
W5 MCP ──────────────────────────────────────────────────────────────┘
        (independent; deploy is the only shared piece)
```

W1 before W3 so layouts inherit corrected copy. W2 before W3 so layouts are judged rendering
final behavior. W4 last so the deploy carries the winning page. W5 whenever — **with one
constraint the input-clamp adds**: the clamp (R20) lives in W5's `tools_core`, but W4 is what
makes `/ask` publicly reachable and thus exposes the unbounded-`horizon_years` vector. So either
land `tools_core` (or at least its clamp) before W4 flips `/ask` public, or gate W4's cutover on
R20. Don't ship the public deploy with the vector open waiting for W5.

## Definition of done

- `pytest tests service/tests` passes.
- `python tools/verify_web.py check` exits 0.
- `web/layouts/` is gone; one layout lives in `index.html`.
- Editing a scenario updates the URL; opening that URL restores the scenario with the box already
  showing its sentence (R8b).
- The public Railway URL serves the page; `/ask` works and is capped, rate-limited (on the real
  client IP via forwarded headers), input-bounded (R20), and daily-rolling.
- `/mcp` is reachable and an agent can call `calculate` and get steps + sourced assumptions back.
- `docs/BACKLOG.md`'s MCP item is struck through with a pointer here, matching how the combos
  item was closed.
