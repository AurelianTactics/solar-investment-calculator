# Deploy handoff — what's built, what you have to do, what to check

**Status: W4 (Railway) and W5 (public MCP) of `docs/plans/2026-07-15-001-feat-poc-closeout-plan.md`,
plus all four slices of `docs/plans/2026-07-20-001-feat-minimal-user-feedback.md`
(instrumentation), are implemented and tested locally. Nothing has been deployed.** Everything that
could be done without your Railway account, a credit card, and an API key is done; this document is
the rest.

Written 2026-07-20, updated 2026-07-21 with the instrumentation work, on branch `mcp-v001`. Nothing
here is urgent — the local dev flow (`service/app.py` on port 8765, the page from `file://`) works
exactly as before.

> **Read the privacy decisions before you deploy.** The instrumentation stores raw IP addresses and
> whatever visitors type, indefinitely. That is a deliberate, reversible choice, and it is the one
> thing here I'd want you to actively agree with rather than inherit — see
> [Decisions I made that you might want to overrule](#decisions-i-made-that-you-might-want-to-overrule).

---

## What you actually have to do

### 1. Create the Railway service (~15 min)

The repo is deploy-ready: `railway.toml` carries the build and start command, and the start command
already includes the proxy flags the rate limit depends on. From the Railway dashboard: new project
→ deploy from this GitHub repo → it picks up `railway.toml`.

### 2. Set these environment variables

| Variable | Value | Why |
|---|---|---|
| `ANTHROPIC_API_KEY` | your key, as a **secret** | The only secret. Without it `/ask` errors and the page silently falls back to its own calculator — degraded, not broken. |
| `SOLAR_AGENT_SPEND_CAP_USD` | `1` or `2` to start | Dollars **per day**, not lifetime. Raise it once you've seen real traffic. |
| `SOLAR_AGENT_LEDGER_PATH` | `/data/.spend.json` | See the volume below. |
| `SOLAR_AGENT_CACHE_PATH` | `/data/.extraction-cache.json` | Same volume. A warm cache is what makes repeat questions free. |
| `SOLAR_FEEDBACK_PATH` | `/data/.feedback.jsonl` | Same volume. The instrumentation log — requests, questions, client events, feedback. Without this it writes inside the container and every event is lost on the next deploy. |

Optional, all with working defaults — set them only if you want different numbers:

| Variable | Default | What it does |
|---|---|---|
| `SOLAR_FEEDBACK_MAX_BYTES` | `52428800` (50 MB) | Byte ceiling for the log. At it, appends refuse (they never evict). |
| `SOLAR_FEEDBACK_MIN_FREE_BYTES` | `209715200` (200 MB) | Free space the log refuses to eat into, so the spend ledger always has room. |
| `SOLAR_EVENTS_RATE_LIMIT_PER_MINUTE` | `30` | Per-IP limit on `/events`, in its own bucket so it can't starve `/ask`. |

`RAILWAY_PUBLIC_DOMAIN` is injected by Railway and picked up automatically — you don't set it. It's
what gets the deploy's own hostname onto the MCP server's allowed-host list; without it every `/mcp`
request would be rejected as an invalid Host.

### 3. Attach a volume at `/data`

Railway's container filesystem is ephemeral. Without a volume, the spend ledger, the extraction
cache, and the event log all reset on every redeploy. The cache resetting is a minor cost; the
ledger resetting means the daily cap silently restarts each time you push; **the event log resetting
means the instrumentation collects nothing at all** — every visit, question and piece of feedback
vanishes the next time you deploy, and you'd never see an empty file to tell you.

This step is now load-bearing rather than merely advisable. If you only half-do this deploy, do
this part.

All three files share the one volume (Railway allows one per service), which is why the log yields
first: it stops appending while there is still room, so a flood of telemetry can never be what
stops `/ask` writing its ledger. See `service/feedback.py`.

### 4. Keep it at one replica

`railway.toml` sets `numReplicas = 1`. Both the spend ledger and the rate-limit bucket are
per-instance with no atomic increments, so N replicas means N × the daily cap and N × the rate
limit. If you ever need to scale, that's the thing to move first, not a knob to turn.

---

## What to check once it's up

Substitute your domain. Each of these is a claim the code makes that only a real deploy can settle.

```sh
# 1. The page is served, same-origin with the agent.
curl -s https://<app>.up.railway.app/ | head -5

# 2. Health reports today's spend against the DAILY cap, AND the log's size against its ceiling.
curl -s https://<app>.up.railway.app/health
#    -> {"ok":true,"spend_usd_today":0.0,"cap_usd_per_day":1.0,"day":"2026-07-21",
#        "log":{"path":"/data/.feedback.jsonl","bytes":...,"accepting":true,...}}
#    The path is the thing to read here: if it does NOT say /data, SOLAR_FEEDBACK_PATH didn't take
#    and you are logging to a disk that disappears on the next deploy.

# 3. The agent answers. This is the only call that costs money.
curl -s -X POST https://<app>.up.railway.app/ask \
  -H 'content-type: application/json' \
  -d '{"question":"Is rooftop solar worth it if I use 9000 kWh a year?"}' | head -20

# 4. The rate limit sees YOU, not Railway's proxy. Fire 12 quickly; the last few must come back
#    {"error":"rate_limited"}. If NONE of them do, --proxy-headers isn't taking effect and every
#    visitor is sharing one bucket keyed on the proxy — that's the failure to look for.
for i in $(seq 1 12); do
  curl -s -X POST https://<app>.up.railway.app/ask -H 'content-type: application/json' \
    -d '{"question":"test '"$i"'"}' | head -c 60; echo
done

# 5. MCP is reachable and needs no auth.
curl -s -X POST https://<app>.up.railway.app/mcp \
  -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
#    -> the four tools: list_options, get_assumptions, calculate, compare

# 6. The event endpoint accepts a batch and refuses an oversized one.
curl -s -X POST https://<app>.up.railway.app/events \
  -H 'content-type: application/json' \
  -d '{"events":[{"kind":"option_selected","option":"rooftop"}]}'
#    -> {"ok":true,"written":1}

curl -s -X POST https://<app>.up.railway.app/events \
  -H 'content-type: application/json' \
  -d "{\"events\":[{\"kind\":\"feedback\",\"text\":\"$(head -c 5000 /dev/zero | tr '\0' 'x')\"}]}"
#    -> {"ok":false,"error":"too_large"}
```

**The one check that needs two deploys — does the volume actually persist?** This is the claim no
test can make, and the instrumentation is worthless if it's false:

```sh
# Before: note the byte count.
curl -s https://<app>.up.railway.app/health   # -> "log":{"bytes":4210,...}
# Now push any trivial commit, wait for the redeploy, and ask again.
curl -s https://<app>.up.railway.app/health   # bytes must be >= what it was, NEVER back to 0
```

A reset to `0` means the volume isn't mounted where the app is writing, and every event so far is
gone. Fix that before reading anything into the data.

**Reading the log.** SSH/exec into the service (Railway dashboard → the service → shell) and it's
just a file. No dashboard is planned or wanted at this traffic — with ten visitors you read the
log, you don't aggregate it:

```sh
tail -5 /data/.feedback.jsonl
grep '"kind": "feedback"' /data/.feedback.jsonl      # what people actually said
grep '"kind": "assumption_edited"' /data/.feedback.jsonl   # which default nobody believes
```

When that gets old, `duckdb -c "select kind, count(*) from
read_json_auto('/data/.feedback.jsonl') group by 1"` reads JSONL directly with no import step.

**In a browser**, the thing worth looking at with your own eyes: open the page and ask a question.
It should answer *through the agent* (no "the calculator agent isn't reachable" notice) — that's the
same-origin `/ask` working. Then check the page still answers with the service stopped: the notice
appears and you still get numbers. That fallback is the one behavior the verifier already enforces
from `file://`, but seeing it on the deploy is worth the minute.

**Add `https://<app>.up.railway.app/mcp` as a custom connector** in Claude and ask it something like
"compare rooftop and community solar for a Maine home using 9,000 kWh a year." What you're looking
for is not the number — it's whether the model relays the *sources and the unsourced tags*. That's
the whole thesis of the project in the shape an agent consumes.

---

## Decisions I made that you might want to overrule

### The instrumentation ones, which are the ones that need you

These four came from the plan and are all cheap to reverse — but they are choices about other
people's data, so they should be yours rather than inherited.

**Raw IP addresses are stored, along with user-agent and referrer.** The plan reversed its own
earlier blanket no-PII rule here, on the grounds that it was ideology rather than a requirement:
without a stable per-visitor value you cannot tell ten homeowners from one enthusiast reloading,
and the referrer is literally the answer to "where is traffic coming from." It's what every web
server's access log holds. **If you'd rather not**, hashing the IP with a per-deploy salt keeps
"distinct visitors" and drops the identifier — a three-line change in `client_ip` at
`service/app.py`. Doing it later doesn't retroactively clean what's already stored.

**Question and feedback text are stored verbatim**, capped but not redacted. Storing it as typed is
what makes it useful and a redaction pass would destroy the signal. The exposure is that a visitor
can type anything into a box — including, eventually, something about themselves — and we keep it.

**Retention is forever, and the log refuses rather than evicts.** It's a POC and the volume holds
years of runway at this traffic. Eviction was rejected deliberately: it would delete the earliest
and most interesting events to make room for whoever is currently flooding us. The consequence is
that a full log stops recording rather than quietly rolling, which `/health` reports.

**`/events` is public and unauthenticated**, like `/mcp`. There's nothing to authorize — it writes
to a log nobody can read back through the API. The real exposure is disk, and per-IP rate limiting
does **not** bound disk (it bounds rate; disk is rate integrated over time), so the actual bounds
are the 2 KB body cap, the 20-event batch cap, the field-level allow-list, and the log's own byte
ceiling. Someone determined can still write junk into the log; they cannot fill the volume or reach
the ledger. If it ever becomes a nuisance, deleting the `/events` route degrades the page to
server-side logging only and nothing breaks.

**A privacy statement is on the page** (footer, R8) naming the IP, the free text, and the
indefinite retention in two sentences. If you change any of the decisions above, that paragraph in
`web/index.html` is what has to change with it — it is the only place a visitor learns any of this.

### The deploy ones, from W4/W5

**The daily cap starts at whatever you set, and I'd start low.** The plan said $1–2/day. A tripped
cap degrades to the page's own calculator, which answers most questions anyway — so the downside of
too low is small and visible, while too high is an invisible bill.

**MCP is public with no auth.** This follows the plan's recommendation, and the reasoning is
specific rather than general enthusiasm: there is no user data, no secret, and no LLM on that path —
it's pure arithmetic over public Maine energy data. Auth would protect nothing while guaranteeing
nobody tries it. The one real risk was a single request driving an unbounded loop
(`horizon_years: 1e9`), and that's bounded in `tools_core.check_inputs` — rejected, not silently
clamped, so an agent can never get an answer to a question it didn't ask. Rate limiting handles
ordinary flooding; the clamp handles the one-shot. If you'd rather not expose it at all, deleting
the two lines in `service/app.py` that mount `/mcp` removes it and nothing else breaks.

**DNS-rebinding protection stays on.** The MCP SDK defaults to localhost-only hosts, which would
reject every request on a public deploy. Rather than switching the check off, the deploy's own
domain is added to the allow-list. It isn't the protection that matters for a public calculator, but
silently disabling a security default is a bad habit to acquire.

**MCP runs stateless.** Every tool is a pure function of its arguments, so there's no session to
keep. This removes the session-handshake failure mode for connectors and means a redeploy can't
strand a client holding a dead session id.

---

## One behavior change outside the deploy, worth knowing about

`python src/cli.py --bill 220 --json` used to report `default_monthly_bill` as `$168.41
[default (sourced)]` — the average it *didn't* use — while showing `inputs.monthly_bill = 220`. The
agent and web surfaces have always retagged that assumption `user-provided`. Building the shared
`tools_core` made the two disagree in a test, so the CLI now retags too. Same numbers, honest
provenance, and the three surfaces now agree. Covered by
`service/tests/test_tools_core.py::TestCliParity`.

---

## What's built, in one paragraph each

**`service/tools_core.py`** — the single payload builder. `agent.compute_payload` was *moved* here
rather than copied, and `agent.py` imports it back; the MCP server and the parity tests are the
other two callers. One definition, three callers, so an agent and a human asking the same question
cannot get different numbers. The input clamp lives here so both `/ask` and `/mcp` inherit it.

**`service/mcp_server.py`** — four tools over `tools_core`, no model anywhere on the path. Runs
`--stdio` locally (zero hosting, good for testing) and mounts at `/mcp` on the deploy.

**`service/spend.py`** — the ledger is now a rolling UTC day. It was a lifetime total, which is
correct for a dev machine and wrong in public: it wasn't a cap, it was a fuse that blew once and
stayed blown until someone deleted a file. Fail-closed-on-corrupt is unchanged and pinned by tests.

**`service/app.py`** — one app serving the page, `/ask`, and `/mcp` from one origin. `/ask` is
bounded four ways: the daily dollar cap, a per-IP rate limit keyed on the real client (the first
`X-Forwarded-For` hop, because behind Railway's proxy `request.client.host` is the proxy for every
request on earth), a 500-character question cap, and the input clamp.

**`web/app.js`** — `SERVICE_URL` is now relative (`/ask`) when the page is hosted and the localhost
port when it's on `file://`. Deciding by protocol rather than hostname keeps the verifier's
`file://` flow working unchanged. `EVENTS_URL` follows the same rule.

**`service/feedback.py`** — the append-only JSONL log, and the whole storage story. No database:
the event shape will change several times in the first month and migrations on POC telemetry are
friction, so JSONL defers the schema decision. Two guards before every append — a byte ceiling on
the file, and a free-space floor on the volume — and every failure is soft, returning False rather
than raising. That posture is the point: it shares a disk with a ledger that fails *closed*, so
telemetry must never be what stops the agent answering.

**`/events` and the request middleware in `service/app.py`** — one log line per request (the only
telemetry that needs no client cooperation, and the only window onto `/mcp`), plus a batched
client-event endpoint behind its own rate-limit bucket, body cap, batch cap and field allow-list.
Free text is truncated where a batch is rejected: rejecting a batch costs an attacker nothing,
while rejecting someone's paragraph throws away the feedback we asked for.

**The `intent` field on the routing call** — the existing `/ask` structured-output call now also
labels each question `calculate | feedback | out_of_scope` for a handful of extra output tokens,
which turns the question box into a labeled feedback channel with no new UI. **It is recorded and
never routed on.** If the classifier called a real question "feedback" and the page stopped
calculating, that would be breaking the product to serve telemetry. Read a month of labels before
letting it influence anything. When the model is unreachable or the cap has tripped the question is
still logged, with `intent: "unknown"` — the text is the asset, the label is derivable offline.

**The feedback row in `web/`** — thumbs under the estimate, and only on a click does an optional
text box appear. Every submission attaches the scenario URL, which already encodes the option, the
bill, the usage and every edited assumption: a thumbs-down alone is noise, one *with the scenario
that produced it* is reproducible. Design evidence, including a bug that only looking caught, is in
`docs/design/2026-07-21-feedback-row/`.

## Verification already done

```sh
pytest tests service/tests      # 320 passed
python tools/verify_web.py check  # exits 0
```

The new tests worth knowing about: `service/tests/test_tools_core.py` asserts every MCP/agent
payload equals `python src/cli.py --json` for the same inputs (parity as a test, not a claim);
`test_deploy_surface.py` covers the rate limit, the proxy-header IP extraction, the length cap, and
`/mcp` over HTTP; `test_spend.py::TestDailyWindow` covers the rollover. For the instrumentation,
`test_feedback.py` pins the yielding behavior (refuses at the ceiling, refuses when the disk is
low, never evicts, never raises) and `test_instrumentation.py` pins the HTTP surface — including
the two that matter most: `/ask` still answers with the log refusing, and a full log does not stop
the spend ledger writing.

Beyond the automated suite, the instrumentation was **driven end to end against a running
service**: a thumbs-down, a typed note with its scenario URL, an assumption edit (2.95 → 3.60,
carrying the outgoing `default (sourced)` tag), an option selection, a comparison, and an MCP
`calculate` call all landed as lines in the log. Looking at the page also caught a real bug — the
feedback note box rendered open on load, because a class rule beat the `hidden` attribute — which
every test passed straight through. Before/after in `docs/design/2026-07-21-feedback-row/`.

What tests **cannot** cover, and why the checks above exist: whether Railway's proxy actually
forwards the headers, whether the volume actually persists across a redeploy, and whether a real
MCP client can actually connect. Those need the deploy.

## Deliberately not built

**Nothing reads the log automatically, and nothing ever edits `assumptions.py` from it.** That's a
founding-rule constraint, not a gap: "sourced defaults trace to research; the calculator never
invents numbers." Feedback naming a bad default becomes a *research question* in
`solar-investment-research`, and a human reads the file. Auto-editing would convert one confused
visitor into a wrong sourced default. The agent that reads the log and drafts research questions is
a real thing to build later — and a much better thing to build once there's a month of real events
to test it against, rather than designing an automation against imagined data.

**No dashboard, no database, no analytics vendor, no accounts.** All explicitly out of scope in the
plan, and at ten visitors a month reading the file beats any of them.

**One plan item I skipped, deliberately.** S1 suggested adding a hit counter and the normalized
question text to the extraction cache, to get a frequency-ranked list of what people ask. I didn't:
every question is already logged verbatim on every `/ask` with a `cached` flag, so frequency *and*
cache-hit rate both fall out of the log by grouping — and the cache alternative would have meant
rewriting the whole cache file on every hit (turning the free path into a write) and changing a
data structure whose fail-soft contract the service depends on. Same signal, no risk. If you want
the ranking: `grep '"kind": "ask"' /data/.feedback.jsonl | jq -r .question | sort | uniq -c | sort -rn`.
