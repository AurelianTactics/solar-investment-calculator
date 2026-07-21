"""HTTP surface — the static page, the agent endpoint, and the MCP server on one app.

    GET  /            the calculator page (web/), served same-origin
    POST /ask         {"question": "..."} -> the CLI --json payload shape (+ agent/followup
                      fields), or {"error": "cap_exceeded" | "unanswerable" | "llm_error: ..."}
    POST /events      {"events": [...]} -> client events + feedback, appended to the log
    GET  /health      liveness + today's spend against the daily cap + the log's size
    /mcp              MCP over streamable HTTP (no LLM, no key, no spend — see mcp_server.py)

Application-level conditions (cap reached, off-topic question) return HTTP 200 with an
``error`` field — the frontend reads the body and falls back to the form flow with the right
notice. Transport-level failures (service down, timeout) need no server cooperation: the
frontend's fetch timeout handles them.

**``/ask`` is the only path here that can spend money**, and on a public deploy it is
unauthenticated. Three bounds stack on it, each covering what the others can't:

  * the **daily spend cap** (``spend.py``) bounds the damage in dollars — the guarantee that
    matters, and the one a determined abuser cannot exceed;
  * a **per-IP token bucket** bounds ordinary flooding. It is keyed on the first ``X-Forwarded-For``
    hop, not ``request.client.host``: behind Railway's TLS proxy, ``client.host`` is the *proxy's*
    address for every request on earth, so a bucket keyed on it throttles either everyone as one
    client or no one. Run uvicorn with ``--proxy-headers --forwarded-allow-ips=*``;
  * a **question length cap** rejects a pasted novel before it reaches the model, where it would
    have been billed by the token.

Neither the rate limit nor the cap stops a single malformed request from driving an unbounded
loop — that is bounded on the input, in ``tools_core.check_inputs``, which both this endpoint and
the MCP server route through.

An in-process bucket is proportionate for a POC on a single instance; it resets on redeploy and
does not coordinate across replicas. Don't scale this horizontally without moving both the bucket
and the ledger somewhere with atomic increments.

**Instrumentation.** A middleware appends one line per request to ``feedback.py``'s log — the only
telemetry that needs no client cooperation, so it covers visitors who bounce in two seconds and
``/mcp`` clients that run no JavaScript at all. ``/ask`` and ``/events`` add richer lines of their
own on top. ``/events`` is a public unauthenticated *write* endpoint, which is a different threat
than ``/ask``: per-IP rate limiting bounds request rate, and disk is rate integrated over time, so
the body-size and per-batch caps here are what actually bound what one client can write. The log
itself yields before the spend ledger does (see ``feedback.py``) — telemetry must never be what
stops the agent answering.

Run locally (uv venv outside the repo — see service/README.md):
    $env:USERPROFILE\\claude_code_repos\\my-uv-envs\\solar-calc\\Scripts\\python.exe service/app.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load the repo-root .env (e.g. ANTHROPIC_API_KEY) before anything reads os.environ, so the
# service picks up the key from the file without it being set in the shell. Real environment
# variables win over .env values (override=False). Point SOLAR_AGENT_ENV_FILE elsewhere to use a
# different file; a missing file is a silent no-op.
from dotenv import load_dotenv  # noqa: E402

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_FILE = os.environ.get("SOLAR_AGENT_ENV_FILE", os.path.join(_REPO_ROOT, ".env"))
load_dotenv(_ENV_FILE, override=False)

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from agent import Agent  # noqa: E402
from feedback import FeedbackLog  # noqa: E402
import mcp_server as mcp_server_module  # noqa: E402
from mcp_server import mcp as mcp_server  # noqa: E402

HOST = os.environ.get("SOLAR_AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", os.environ.get("SOLAR_AGENT_PORT", "8765")))
WEB_DIR = os.path.join(_REPO_ROOT, "web")

# A real question is a sentence. 500 chars is generous for one and cheap to reject.
MAX_QUESTION_CHARS = int(os.environ.get("SOLAR_AGENT_MAX_QUESTION_CHARS", "500"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("SOLAR_AGENT_RATE_LIMIT_PER_MINUTE", "10"))
RATE_LIMIT_WINDOW_S = 60.0
_RATE_LIMIT_MAX_IPS = 10_000        # bounded so the limiter can't itself become the memory leak

# /events gets its own bucket rather than sharing /ask's. A page that flushes a few event batches
# while you tune assumptions must not consume the allowance for asking questions — one surface
# throttling the other would be an instrumentation change breaking the product.
EVENTS_RATE_LIMIT_PER_MINUTE = int(os.environ.get("SOLAR_EVENTS_RATE_LIMIT_PER_MINUTE", "30"))
# Generous for a batch of eight small events, hostile to bulk. Enforced on the RAW body, before
# parsing, so a large payload is refused rather than parsed and then measured.
MAX_EVENT_BYTES = int(os.environ.get("SOLAR_EVENTS_MAX_BYTES", "2048"))
MAX_EVENTS_PER_BATCH = int(os.environ.get("SOLAR_EVENTS_MAX_PER_BATCH", "20"))
# Free text is TRUNCATED where a batch is REJECTED: rejecting a batch costs an attacker nothing,
# while rejecting someone's paragraph throws away the feedback we went out of our way to ask for.
MAX_TEXT_CHARS = 1000
MAX_FIELD_CHARS = 200


app = FastAPI(title="Maine Solar Ledger")
# The page is served same-origin on the deploy, but the verifier and the dev flow drive it from
# file:// (origin "null"), so CORS stays open. The service holds no secrets a browser could reach.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_agent: Agent | None = None
_buckets: "OrderedDict[str, list[float]]" = OrderedDict()
log = FeedbackLog.from_env()


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


def client_ip(request: Request) -> str:
    """The real client, not the proxy in front of it.

    Railway terminates TLS at a proxy and appends the client to ``X-Forwarded-For``; the first hop
    is the original client. Falls back to the socket peer for the local/dev case where there is no
    proxy at all.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limited(ip: str, now: float | None = None, scope: str = "ask",
                 limit: int | None = None) -> bool:
    """Sliding-window counter per IP, per endpoint scope. True means refuse this request."""
    now = time.time() if now is None else now
    limit = RATE_LIMIT_PER_MINUTE if limit is None else limit
    bucket = f"{scope}:{ip}"
    hits = [t for t in _buckets.get(bucket, []) if now - t < RATE_LIMIT_WINDOW_S]
    if len(hits) >= limit:
        _buckets[bucket] = hits
        _buckets.move_to_end(bucket)
        return True
    hits.append(now)
    _buckets[bucket] = hits
    _buckets.move_to_end(bucket)
    while len(_buckets) > _RATE_LIMIT_MAX_IPS:
        _buckets.popitem(last=False)
    return False


class Ask(BaseModel):
    question: str


@app.post("/ask")
def ask(body: Ask, request: Request) -> dict:
    question = (body.question or "").strip()
    if not question:
        return {"error": "unanswerable", "detail": "empty question"}
    if len(question) > MAX_QUESTION_CHARS:
        # Rejected before the model sees it — length is billed by the token.
        return {"error": "question_too_long",
                "detail": f"question is {len(question)} characters; the limit is "
                          f"{MAX_QUESTION_CHARS}. Ask a shorter question."}
    if rate_limited(client_ip(request)):
        return {"error": "rate_limited",
                "detail": f"more than {RATE_LIMIT_PER_MINUTE} questions in a minute from your "
                          f"address. Wait a moment and ask again."}
    started = time.time()
    result = get_agent().answer(question)
    # The question text is the asset and is stored verbatim; the intent label is a bonus that the
    # LLM being down (or the cap being tripped) must not cost us — hence "unknown" rather than a
    # dropped line. Every question that reaches the agent is recorded, answered or not.
    meta = result.get("agent") or {}
    # Prefer the answered payload's label; fall back to an error response's carried intent (an
    # unanswerable/out_of_scope question was still classified), then to "unknown" (LLM down / cap).
    intent = meta.get("intent") or result.get("intent") or "unknown"
    log.append("ask",
               ip=client_ip(request),
               question=question,
               intent=intent,
               option=meta.get("option"),
               cached=meta.get("cached"),
               error=result.get("error"),
               ms=int((time.time() - started) * 1000))
    return result


def _clean_event(raw: object) -> dict | None:
    """One client event, reduced to fields we know how to store. None means drop it.

    An allow-list rather than a passthrough: ``/events`` is public and unauthenticated, so without
    this the log's line size would be whatever a stranger decided to POST, and the body cap alone
    would be the only thing standing between us and arbitrary JSON in the record we most want to
    stay readable.
    """
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind", ""))[:40]
    if kind not in ("option_selected", "assumption_edited", "compared", "feedback"):
        return None
    out: dict = {}
    for name in ("option", "key", "tag", "options", "verdict"):
        value = raw.get(name)
        if value is None:
            continue
        if isinstance(value, list):
            out[name] = [str(v)[:MAX_FIELD_CHARS] for v in value[:10]]
        else:
            out[name] = str(value)[:MAX_FIELD_CHARS]
    for name in ("from", "to"):
        value = raw.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[name] = value
    for name in ("text", "scenario_url"):
        value = raw.get(name)
        if value:
            out[name] = str(value)[:MAX_TEXT_CHARS]
    return {"kind": kind, **out}


@app.post("/events")
async def events(request: Request) -> dict:
    """Client events and feedback. Fire-and-forget: the page never depends on this answering."""
    ip = client_ip(request)
    if rate_limited(ip, scope="events", limit=EVENTS_RATE_LIMIT_PER_MINUTE):
        return {"ok": False, "error": "rate_limited"}
    raw = await request.body()
    if len(raw) > MAX_EVENT_BYTES:
        return {"ok": False, "error": "too_large"}
    try:
        body = json.loads(raw or b"{}")
        incoming = body.get("events") if isinstance(body, dict) else None
    except (json.JSONDecodeError, ValueError, AttributeError):
        return {"ok": False, "error": "bad_json"}
    if not isinstance(incoming, list):
        return {"ok": False, "error": "bad_json"}
    if len(incoming) > MAX_EVENTS_PER_BATCH:
        return {"ok": False, "error": "too_many_events"}

    referrer = request.headers.get("referer", "")[:MAX_FIELD_CHARS]
    user_agent = request.headers.get("user-agent", "")[:MAX_FIELD_CHARS]
    written = 0
    for item in incoming:
        event = _clean_event(item)
        if event is None:
            continue
        kind = event.pop("kind")
        if log.append(kind, ip=ip, ua=user_agent, referrer=referrer, **event):
            written += 1
    return {"ok": True, "written": written}


@app.get("/health")
def health() -> dict:
    ledger = get_agent().ledger
    return {"ok": True, "spend_usd_today": round(ledger.total_usd, 4), "cap_usd_per_day":
            ledger.cap_usd, "day": ledger.today(), "log": log.status()}


# MCP over streamable HTTP (see mcp_server.http_handler for why the raw handler rather than
# FastMCP's Starlette wrapper). Starlette does not run a mounted sub-app's lifespan, so the
# session manager is started from THIS app's lifespan by hand — without it, every /mcp request
# fails with "task group is not initialized".
_mcp_handler = mcp_server_module.http_handler()
app.router.lifespan_context = lambda _app: mcp_server.session_manager.run()
app.mount("/mcp", _mcp_handler)


@app.middleware("http")
async def _normalize_mcp_path(request: Request, call_next):
    """Make the bare ``/mcp`` work, not just ``/mcp/``.

    A Starlette mount matches ``/mcp/...``; the exact path ``/mcp`` would normally fall through to
    the router's trailing-slash redirect — except the catch-all StaticFiles mount at ``/`` below
    matches first and answers 405. Connectors get handed ``https://host/mcp``, so rewriting the
    path before routing is worth four lines. Runs before routing, which is the whole trick.
    """
    if request.scope["path"] == "/mcp":
        request.scope["path"] = "/mcp/"
    return await call_next(request)


@app.middleware("http")
async def _log_request(request: Request, call_next):
    """One log line per request — the cheapest instrumentation there is, and the only kind that
    needs no client cooperation.

    It cannot be blocked, it catches visitors who leave in two seconds, and it covers ``/mcp``,
    which runs no JavaScript at all and is otherwise invisible.

    The path recorded is the one that was *routed*, not the one sent: this runs inside
    ``_normalize_mcp_path``, so a bare ``/mcp`` is logged as ``/mcp/``. That's the useful end of
    the trade — all MCP traffic lands under one path rather than splitting by which form the
    connector happened to use.

    A failure to log must never become a failure to answer, so the append is best-effort and the
    response is returned whatever happens to it.
    """
    started = time.time()
    response = await call_next(request)
    try:
        log.append("request",
                   method=request.method,
                   path=request.scope.get("path", ""),
                   status=response.status_code,
                   ms=int((time.time() - started) * 1000),
                   ip=client_ip(request),
                   ua=request.headers.get("user-agent", "")[:MAX_FIELD_CHARS],
                   referrer=request.headers.get("referer", "")[:MAX_FIELD_CHARS])
    except Exception:
        pass
    return response

# The page LAST: a catch-all mount at "/" would otherwise shadow the routes above. Same-origin
# with /ask, which is what lets web/app.js call a relative path on the deploy.
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        print("  Set it for this shell, e.g.:  $env:ANTHROPIC_API_KEY = '<your key>'", file=sys.stderr)
        print("  Details: service/README.md", file=sys.stderr)
        raise SystemExit(1)
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, proxy_headers=True, forwarded_allow_ips="*")
