# Deploy handoff — what's built, what you have to do, what to check

**Status: W4 (Railway) and W5 (public MCP) of `docs/plans/2026-07-15-001-feat-poc-closeout-plan.md`
are implemented and tested locally. Nothing has been deployed.** Everything that could be done
without your Railway account, a credit card, and an API key is done; this document is the rest.

Written 2026-07-20, on branch `mcp-v001`. Nothing here is urgent — the local dev flow
(`service/app.py` on port 8765, the page from `file://`) works exactly as before.

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

`RAILWAY_PUBLIC_DOMAIN` is injected by Railway and picked up automatically — you don't set it. It's
what gets the deploy's own hostname onto the MCP server's allowed-host list; without it every `/mcp`
request would be rejected as an invalid Host.

### 3. Attach a volume at `/data`

Railway's container filesystem is ephemeral. Without a volume, both the spend ledger and the
extraction cache reset on every redeploy. The cache resetting is a minor cost; the ledger resetting
means the daily cap silently restarts each time you push.

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

# 2. Health reports today's spend against the DAILY cap.
curl -s https://<app>.up.railway.app/health
#    -> {"ok":true,"spend_usd_today":0.0,"cap_usd_per_day":1.0,"day":"2026-07-21"}

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
```

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
`file://` flow working unchanged.

## Verification already done

```sh
pytest tests service/tests      # 284 passed
python tools/verify_web.py check  # exits 0
```

The new tests worth knowing about: `service/tests/test_tools_core.py` asserts every MCP/agent
payload equals `python src/cli.py --json` for the same inputs (parity as a test, not a claim);
`test_deploy_surface.py` covers the rate limit, the proxy-header IP extraction, the length cap, and
`/mcp` over HTTP; `test_spend.py::TestDailyWindow` covers the rollover.

What tests **cannot** cover, and why the checks above exist: whether Railway's proxy actually
forwards the headers, whether the volume actually persists, and whether a real MCP client can
actually connect. Those need the deploy.
