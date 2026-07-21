# Solar Investment Calculator

A transparency-first tool that turns a Maine homeowner's electricity situation into a trustworthy,
fact-checkable estimate of what each solar option would save. Every number is a labeled, editable,
sourced assumption — never a black-box output. **Why** this exists and who it's for: `STRATEGY.md`.

## What this is

Python 3 core + a static web mirror + a local LangGraph agent service. The prototype-era "standard
library only" rule is **retired** (2026-07-09) — do not resurrect it. Dependencies are managed with
**uv**: a venv created **outside the repo**, installed from the checked-in `requirements.txt`:

```sh
uv venv %USERPROFILE%\claude_code_repos\my-uv-envs\solar-calc          # one-time, outside the repo
uv pip install -r requirements.txt --python %USERPROFILE%\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe
```

The core (`src/`) and verifier (`tools/`) stay stdlib-only by construction — only `service/` and
the test runner need the venv.

Seven option states are modeled:

- **community solar** — zero capital; `src/solar_calc.py`.
- **balcony / plug-in, rooftop, battery, plugin-battery** — capital options on the shared
  capital-allocation engine (`src/capital.py`): each is a small pure module (`src/balcony.py`,
  `src/rooftop.py`, `src/battery.py`, `src/plugin_battery.py`) that produces upfront cost +
  annual savings, then asks the engine for payback/NPV vs. investing the cash. Battery and
  plugin-battery share the TOU arbitrage engine (`src/tou.py`): battery via the off-by-default
  `tou_enrolled` mode (which still uses the full three-case branch), plugin-battery as its whole
  point. **Plugin-battery is deliberately scoped to one case** (2026-07-20): the home already
  under the 15.8% on-peak line, where enrolling in TOU lowers the bill on its own and the battery
  adds arbitrage on top. Over the line, `compute` raises `OutOfScope` (a `ValueError`, so the CLI
  and web already handle it) instead of half-answering — the rescue case is backlogged with its
  UI problem stated. Don't reintroduce case-branching output here without solving that first.
- **battery+rooftop, battery+balcony** — stream-wise additive combos (`src/combo.py` mechanism,
  `src/battery_rooftop.py` / `src/battery_balcony.py` thin configs): each component keeps its own
  escalation/degradation/horizon stream; `capital.combine()` sums per-year cashflows and derives
  NPV/payback from the summed stream. Battery keys are `battery_`-prefixed in combo assumption
  dicts so collisions (`federal_itc_pct`, `horizon_years`) stay per-component. Plugin-battery
  stands alone (no pairings).

`src/assumptions.py` is the shared assumption data model + per-option defaults. Every assumption
carries `explain` (newcomer-grade plain English) and sourced defaults carry `source.what_is_it`
(what the document is, who publishes it, why credible) — both flow to CLI text, `--json`, and the
web. `src/cli.py` is the human + agent surface. `web/` is a question-first UI (question box →
agent service, with automatic client-side form fallback) mirroring the Python formulas with an
on-load self-check.

Any option, and any **two or more** options side by side, are reachable three ways — by asking, by
clicking (the refine drawer's mode switch → option picker), or headlessly (`--compare`,
`selectCompare`). No capability lives only behind the question box.

**The service** (`service/`) is one FastAPI app serving three things from one origin: the static
page (`/`), the agent endpoint (`/ask`), and the MCP server (`/mcp`). Setup/run/error contract:
`service/README.md`. Deploying it: `railway.toml` + `docs/deploy-handoff.md`.

- `POST /ask {question}` routes a natural-language question via one `claude-opus-4-8`
  structured-output call, computes through direct `src/` imports, and returns the CLI `--json`
  payload shape. **The only path that spends money**, and it's bounded four ways: a *rolling
  daily* spend cap (`service/.spend.json`, gitignored, fails closed on corrupt), a per-IP rate
  limit keyed on the first `X-Forwarded-For` hop (behind a TLS proxy, `request.client.host` is the
  proxy for every request — a bucket keyed on it throttles everyone as one client or nobody), a
  question-length cap, and the input clamp below. Needs `ANTHROPIC_API_KEY`; the web page works
  fully without the service (that fallback is verifier-enforced).
- `/mcp` exposes the calculator as MCP tools (`list_options`, `get_assumptions`, `calculate`,
  `compare`) with **no LLM on the path** — no key, no ledger, no cap. Public and unauthenticated by
  decision (nothing to authorize; the reasoning is in `docs/deploy-handoff.md`).

**`service/tools_core.py` is the single payload builder** — `/ask`, MCP, and the parity tests are
its three callers. Don't add a second one: a human and an agent asking the same question must not
get different numbers, and `test_tools_core.py` asserts every payload equals `src/cli.py --json`.
The **input clamp** lives there so both surfaces inherit it: loop-driving overrides
(`horizon_years`, `battery_horizon_years`) are bounded at 100 and **rejected, never silently
clamped** — a rate limit bounds request frequency and does nothing about one `1e9`-year request.

```sh
%USERPROFILE%\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe service\app.py            # page + /ask + /mcp (port 8765)
%USERPROFILE%\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe service\mcp_server.py --stdio   # MCP alone, no hosting
```

## Active metric — run before reporting any calculation change done

**Formula correctness:** outputs must match the hand-verified worked examples encoded as tests. A
change that breaks a known case is a regression.

```sh
pytest tests                                 # the metric (all options; core tests run on system python)
pytest tests service/tests                   # + service tests (needs the venv; LLM always stubbed)
python src/cli.py --bill 150                 # community (default); --json for agents
python src/cli.py --option battery+rooftop   # combos work everywhere options do
python src/cli.py --option rooftop --set capacity_kw=8   # --set overrides any assumption
python src/cli.py --compare community,balcony            # 2+ options side by side (no LLM)
```

**Comparisons are tabulated, never recomputed.** `--compare` (and the web's `selectCompare`) run
each option's own code and lay the answers side by side: every row must equal what
`--option <key>` says alone, and `tests/test_cli_compare.py` holds that parity. Overrides split by
scope on both surfaces — `--set key=value` is *shared* (it moves every compared option carrying
the key, mirroring the web's "Shared inputs" block), `--set option:key=value` moves one row.
`opportunity_rate` is the one that matters: NPVs at different discount rates aren't comparable.

**pytest** is the test runner (existing `unittest`-style tests are collected as-is; new tests may
be written pytest-style).

The Python core is the **source of truth**. `web/app.js` is a mirror with a per-option self-check
banner (all seven states, combos included); keep it in sync when a formula changes.

**Web rendering metric — run after any `web/` change.** "The website works" must be *observed*, not
claimed. Verification is **two-layered**:

1. **Deterministic loop** — `tools/verify_web.py run` (alias `/verify-web`) drives all seven option
   states in a headless chromium-family browser (Chrome/Chromium/Edge, discovered on any OS),
   asserts each renders, the parity self-check did not fire, and the agent-fallback notice appears
   when asking with the service unreachable; writes screenshots + a hashed evidence record to
   gitignored `.verify/`.
2. **Agent perception loop** — `/verify-web-page <state>`: drive the real page via the playwright
   plugin's MCP browser tools (navigate → a11y snapshot → screenshot → console), judge it against
   intent, and **record** the verdict: `python tools/verify_web.py record <state> --result
   pass|fail --screenshot ...`. Findings are recorded as `fail` first (fail → fix → re-run →
   pass); a fresh failing verdict blocks the gate like any failing evidence.

A **Stop hook** (`.claude/hooks/verify_web_gate.py`) blocks end-of-turn if `web/` changed without
fresh passing evidence, or if a fresh failing perception verdict exists (freshness = content
hash). The gate itself stays deterministic and token-free — judgment happens during evidence
*production*, never in the gate. Definition of done for web work: `verify_web.py check` exits 0.

```sh
python tools/verify_web.py run      # browser loop: render + parity + fallback + screenshots + evidence
python tools/verify_web.py check    # deterministic gate (what the Stop hook runs); exit 0 == verified
python tools/verify_web.py run --page web/candidate.html   # drive a candidate page instead
```

`--page` exists for design candidates (it drove the W3 layout bake-off). A non-default page writes
its own `.verify/evidence-<slug>.json` + `screenshots/<slug>/` and **does not feed the Stop gate**:
the gate hashes `web/index.html` + `web/app.js` only, so an exploratory candidate can never block a
turn — nor falsely certify the live page it isn't.

The live page's design system is documented in the comment at the top of `web/index.html`. It is a
**ledger**: two families (IBM Plex Mono for numbers, Public Sans for labels), no serif, hue only on
NPV sign and the three provenance tags. Density is the constraint — judge any change against
`battery+rooftop` (25 assumptions, 9 steps) and the six-way compare, not the 4-row community
default, which is where three very different layouts all looked fine. The bake-off that established
this — screenshots, measured row pitches, and the losing candidates still drivable via `--page` —
is in `docs/design/2026-07-20-layout-bakeoff/`.

**A design judgement is evidence too.** When a change is decided by looking, the screenshots that
decided it belong in `docs/design/`, not in scratch files that get cleaned up — same standard as a
calculation.

## Canonical docs (read what's relevant before non-trivial work)

| Doc | What it holds |
|---|---|
| `STRATEGY.md` | Target problem, transparency approach, audience, active metric |
| `docs/how-to-use-and-verify.md` | How to drive the calculator and how to trust its numbers |
| `docs/options-integration-notes.md` | Per-option: what research landed, what firmed up, what surprised us, what's open |
| `docs/plans/` | Build-ready plans (community-solar POC; the options-expansion plan) |
| `docs/brainstorms/` | Phase 1 spec (community-solar requirements) |
| `docs/BACKLOG.md` | Ideas captured, not scheduled — don't pull one in without a deliberate decision |
| `docs/solutions/` | Lessons learned (e.g. verify the runtime before choosing a stack; judge-as-evidence, gate-stays-deterministic) |
| `docs/design/` | Design decisions with their evidence — screenshots + drivable losing candidates (the 2026-07-20 layout bake-off) |
| `service/README.md` | Service setup, run commands, spend cap, MCP tools, error contract |
| `docs/deploy-handoff.md` | The Railway deploy: what's built, what a human must set up, what to check |

`docs/human_to_do.md` is human-only — do not read or reference it.

## Conventions (universal)

- **Assumptions are first-class.** Every number carries a label, value+unit, a tag
  (`default (sourced)` | `user-provided` | `unsourced — pending research`), and a source. Never
  present an unsourced default as established fact.
- **Show the steps, not just the answer.** Every option returns its calculation chain for display.
- **Agent-native parity.** Anything a human can do, an agent can do via the module or `--json`.
- **Sourced defaults trace to research.** A `default (sourced)` value cites a `wiki/` article in
  `../solar-investment-research`. The calculator *pulls* sourced numbers; it never invents them. If
  research hasn't landed a number, tag it `unsourced — pending research`.
- **The capital engine is the centerpiece** for capital options: NPV > 0 means buying solar beats
  investing the same cash at the opportunity rate. Community solar is $0 capital and skips it.
