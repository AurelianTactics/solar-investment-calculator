# Service — the page, the agent endpoint, and the MCP server

One FastAPI app (`app.py`) serving three things from one origin:

| Path | What | Costs money? |
|---|---|---|
| `/` | the static page from `web/` | no |
| `/ask` | natural-language question → calculator answer | **yes** — the only path that can |
| `/mcp` | the calculator as MCP tools | no — there's no model on that path |
| `/events` | client events + feedback, appended to the log | no — a file append |
| `/health` | liveness, today's spend, the log's size | no |

`/ask` turns "What savings would I get with community solar when my bill is $150 a month?" into the
same structured payload `python src/cli.py --json` emits. One LangGraph graph: **extract** (a
single `claude-opus-4-8` structured-output call that picks the option and pulls out stated numbers)
→ **compute** (direct `src/` imports — the LLM never does arithmetic).

`tools_core.py` is where "run the calculator and return the payload" is implemented, once. `/ask`,
the MCP server, and the parity tests are its three callers, so an agent and a human asking the same
question cannot get different numbers. The input clamp lives there too, which is what makes the
public MCP surface safe (see below).

Deploying it: `railway.toml` plus `docs/deploy-handoff.md`.

## Setup (one time)

Dependencies live in a uv venv created **outside the repo** (central location so it's shared
across git worktrees), from the checked-in `requirements.txt` at the repo root:

```powershell
uv venv $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc
uv pip install -r requirements.txt --python $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe
```

The service needs an Anthropic API key (Claude Code's own login does **not** provide one — get a
key at console.anthropic.com). Put it in a **`.env` file at the repo root** — the service loads it
automatically on startup via `python-dotenv`, so you never type the key into the shell:

```dotenv
# .env  (repo root; gitignored)
ANTHROPIC_API_KEY=<your key>
```

A real environment variable, if already set in the shell, wins over the `.env` value. So the
old shell-var approach still works if you prefer it:

```powershell
$env:ANTHROPIC_API_KEY = "<your key>"        # PowerShell, this session only — overrides .env
```

## Run

```powershell
& $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe service\app.py
# -> http://127.0.0.1:8765   (port: SOLAR_AGENT_PORT)
```

Smoke test:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/ask -Method Post `
  -ContentType 'application/json' `
  -Body '{"question": "What savings would I get with community solar when my bill is $150 a month?"}'
```

The numbers must match `python src/cli.py --bill 150 --json` exactly — the service imports the
same core.

## Spending cap — dollars per day

Every response's token usage is priced ($5/$25 per MTok for opus) and accumulated in the
gitignored `service/.spend.json`, so the cap survives restarts. The window is **one UTC day**: a
total recorded on any other day reads as zero. That distinction only matters in public, where a
cumulative-forever total isn't a cap but a fuse — it blows once and stays blown until a human
deletes a file.

The cap is checked **before** each LLM call; once reached, `/ask` returns
`{"error": "cap_exceeded"}` and the frontend falls back to the form flow. A corrupt ledger fails
**closed** (treated as over cap): an unreadable file must never become free money.

| env var | default | meaning |
|---|---|---|
| `SOLAR_AGENT_SPEND_CAP_USD` | `5.0` | spend ceiling **per day** |
| `SOLAR_AGENT_LEDGER_PATH` | `service/.spend.json` | ledger location (point at a volume on a deploy) |
| `SOLAR_AGENT_PORT` | `8765` | HTTP port (`PORT` wins, for the deploy) |
| `SOLAR_AGENT_ENV_FILE` | repo-root `.env` | which `.env` to auto-load on startup (missing file = no-op) |
| `SOLAR_AGENT_RATE_LIMIT_PER_MINUTE` | `10` | per-IP `/ask` allowance |
| `SOLAR_AGENT_MAX_QUESTION_CHARS` | `500` | `/ask` refuses longer questions before the model sees them |

Reset the budget by deleting the ledger file (a deliberate act, on purpose).

## MCP server — the calculator as tools

Four tools over `tools_core`: `list_options`, `get_assumptions`, `calculate`, `compare`.
**No LLM is on this path** — the agent calling the tools *is* the model, so there's no key, no
ledger, and no cap to reason about. What makes it worth exposing is the shape of what it returns:
not just a number, but every labeled assumption, its source, what that source *is*, and the full
step chain — enough for an agent to cite its work and a user to fact-check it.

```powershell
# local, no hosting at all
& $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe service\mcp_server.py --stdio
```

Mounted at `/mcp` on the deploy (streamable HTTP, stateless), public and unauthenticated by
decision: there's no user data, no secret, and nothing to authorize. The one real risk — a single
request driving an unbounded loop, e.g. `{"horizon_years": 1e9}` — is bounded on the **input** in
`tools_core.check_inputs`, because a rate limit bounds request *frequency* and can do nothing about
one bad request. Out-of-range values are rejected, never silently clamped, so an agent can't get an
answer to a question it didn't ask. `/ask` routes through the same core and inherits the bound.

| env var | default | meaning |
|---|---|---|
| `SOLAR_MCP_ALLOWED_HOSTS` | (none) | extra hostnames for the DNS-rebinding allow-list, comma-separated |
| `RAILWAY_PUBLIC_DOMAIN` | (injected by Railway) | picked up automatically — without it, a deploy rejects every `/mcp` request as an invalid Host |

## Extraction cache — the model is the last resort, not the first

Three layers keep questions away from the model, and only the third costs anything:

1. **Elision** (`web/app.js`) — the page rewrites the question box from its own state, so a
   question the page *wrote* is answered by recomputing directly. No network at all.
2. **Local parsing** (`parseQuestionLocally`) — comparison questions and many others are read by
   the page's own keyword/number parser.
3. **This cache** (`service/cache.py`) — for questions the page didn't write: normalized text →
   the serialized `Extraction`. A repeat of any question, from any visitor, after any restart,
   costs nothing. Refusals are cached too, so "what's the weather" buys one call, not one per ask.

Caching routing is safe because an `Extraction` is a pure function of the question text — the
arithmetic re-runs from `src/` on every request regardless, so a hit can never serve a stale
*number*, only a stale *routing*. Routing does expire, though: entries are qualified by a version
tag over the model, the option keys, and the routing prompt, so adding a seventh option or editing
the prompt invalidates the file instead of routing to yesterday's option set forever.

The ledger fails **closed** (a corrupt ledger must not become free money); the cache fails
**soft** — missing, corrupt, or stale means *miss*, never an error. A cached question is also
answered when the spend cap is reached, since serving it spends nothing.

| env var | default | meaning |
|---|---|---|
| `SOLAR_AGENT_CACHE_PATH` | `service/.extraction-cache.json` | cache location (gitignored) |

Delete the file to force fresh routing.

## Instrumentation — one log, appended, that yields to everything else

`feedback.py` writes one JSON object per line to a single file. Requests, `/ask` questions with
their intent label, MCP tool calls, client events, thumbs and free text all share the stream,
distinguished by `kind`. There is no database: the event shape will change several times early on,
and migrations on POC telemetry are pure friction. DuckDB reads JSONL directly when you want to
query it (`read_json_auto`), so nothing is given up by waiting.

Four writers:

| `kind` | written by | holds |
|---|---|---|
| `request` | the middleware in `app.py` | method, routed path, status, duration, IP, user-agent, referrer |
| `ask` | `/ask` | the question verbatim, its `intent`, the routed option, whether it was cached, any error |
| `mcp_tool_call` | each tool in `mcp_server.py` | tool name and an argument *summary* (option keys, which input keys — not values) |
| `option_selected` / `assumption_edited` / `compared` / `feedback` | `/events`, from `web/app.js` | see the plan's S3/S4 |

`assumption_edited` is the one with real research value: it carries `from`, `to`, and the assumption's
*outgoing* tag, so an edit to a **sourced** default reads as "our source is stale or a bad central
estimate", while an edit to an **unsourced** placeholder is a vote on which honest unknown to
research first. Direction and magnitude are the finding — not the count.

**The log yields before anything else does.** It shares one Railway volume with the spend ledger,
and the ledger fails *closed* — a ledger it can't write stops `/ask` answering. So two checks run
before every append: a byte ceiling on the log, and a free-space floor on the volume (the one that
matters, since it doesn't care *what* filled the disk). On either it **refuses; it never evicts** —
retention is forever, so evicting would delete the earliest events on behalf of whoever is flooding
us. `/health` reports size against ceiling so "the log is 80% full" is visible, not discovered.
Every failure is soft: `append()` returns False and never raises.

`/events` is public and unauthenticated, and per-IP rate limiting does **not** bound disk — it
bounds rate, and disk is rate integrated over time. What actually bounds it: a 2 KB body cap
enforced on the raw body, a 20-event batch cap, a field-level allow-list, and the ceiling above.
Oversized batches are rejected but oversized free text is **truncated** — rejecting a batch costs an
attacker nothing, while rejecting a person's paragraph throws away the feedback we asked for.

| env var | default | meaning |
|---|---|---|
| `SOLAR_FEEDBACK_PATH` | `service/.feedback.jsonl` | log location (gitignored). On Railway: `/data/.feedback.jsonl` |
| `SOLAR_FEEDBACK_MAX_BYTES` | 50 MB | byte ceiling; at it, appends refuse |
| `SOLAR_FEEDBACK_MIN_FREE_BYTES` | 200 MB | free space the log won't eat into |
| `SOLAR_EVENTS_RATE_LIMIT_PER_MINUTE` | 30 | per-IP, in its own bucket so it can't starve `/ask` |

The `intent` label on `/ask` (`calculate` | `feedback` | `out_of_scope`) rides along on the routing
call that already exists. **It is logged and never acted on.** A classifier that mislabeled a real
question would otherwise stop the page calculating — breaking the product to serve telemetry. When
the model is unreachable or the cap has tripped, the question is still logged with
`intent: "unknown"`; the text is the asset and the label is derivable offline.

## Error contract (what the frontend keys on)

| condition | response |
|---|---|
| routable question | CLI-shaped payload + `agent` + `followup` fields |
| repeat of any earlier question | same payload shape, recomputed fresh, **zero** LLM calls |
| off-topic question | `{"error": "unanswerable"}` |
| cap reached (today) | `{"error": "cap_exceeded", "detail": ...}` |
| LLM timeout/failure | `{"error": "llm_error: ..."}` |
| bad/over-range input | `{"error": "compute_error: ..."}` |
| question over the length cap | `{"error": "question_too_long", "detail": ...}` |
| too many questions from one IP | `{"error": "rate_limited", "detail": ...}` |
| `/events`: batch stored (fully or partly) | `{"ok": true, "written": n}` — `n` may be 0 if the log is refusing |
| `/events`: over the body/batch caps, bad JSON, or rate limited | `{"ok": false, "error": "too_large" \| "too_many_events" \| "bad_json" \| "rate_limited"}` |
| service not running | (no response — the frontend's 4s fetch timeout handles it) |

Every one of these is HTTP 200 with an `error` field, because the frontend's job on all of them is
identical: fall back to its own calculator and say why. The page must work fully without this
service, and that fallback is verifier-enforced.

## Tests

```powershell
& $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe -m pytest service\tests
```

Every test stubs the LLM (the `Agent(extractor=...)` seam) — no network, no key, no spend. The MCP
tests stub nothing, because there is no model on that path to stub; if they ever start needing a
key, something has gone wrong.

| file | what it holds |
|---|---|
| `test_tools_core.py` | **parity as a test** — every payload equals `src/cli.py --json` for the same inputs; plus the input clamp |
| `test_mcp_server.py` | the four tools, their payloads, and that no key or spend is involved |
| `test_deploy_surface.py` | rate limit, real-client-IP extraction, length cap, static mount, `/mcp` over HTTP |
| `test_feedback.py` | the log yields first — refuses at the ceiling and on a low disk, never evicts, never raises |
| `test_instrumentation.py` | what gets recorded, the `/events` caps, and that `/ask` still answers with the log refusing |
| `test_spend.py` | pricing, the rolling daily window, fail-closed-on-corrupt |
| `test_cache.py` | cache hits/misses, version invalidation, fail-soft |
| `test_agent.py` | routing, honest tagging, the error contract |
