"""HTTP surface — the static page, the agent endpoint, and the MCP server on one app.

    GET  /            the calculator page (web/), served same-origin
    POST /ask         {"question": "..."} -> the CLI --json payload shape (+ agent/followup
                      fields), or {"error": "cap_exceeded" | "unanswerable" | "llm_error: ..."}
    GET  /health      liveness + today's spend against the daily cap
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

Run locally (uv venv outside the repo — see service/README.md):
    $env:USERPROFILE\\claude_code_repos\\my-uv-envs\\solar-calc\\Scripts\\python.exe service/app.py
"""

from __future__ import annotations

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


app = FastAPI(title="Maine Solar Ledger")
# The page is served same-origin on the deploy, but the verifier and the dev flow drive it from
# file:// (origin "null"), so CORS stays open. The service holds no secrets a browser could reach.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_agent: Agent | None = None
_buckets: "OrderedDict[str, list[float]]" = OrderedDict()


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


def rate_limited(ip: str, now: float | None = None) -> bool:
    """Sliding-window counter per IP. True means this request should be refused."""
    now = time.time() if now is None else now
    hits = [t for t in _buckets.get(ip, []) if now - t < RATE_LIMIT_WINDOW_S]
    if len(hits) >= RATE_LIMIT_PER_MINUTE:
        _buckets[ip] = hits
        _buckets.move_to_end(ip)
        return True
    hits.append(now)
    _buckets[ip] = hits
    _buckets.move_to_end(ip)
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
    return get_agent().answer(question)


@app.get("/health")
def health() -> dict:
    ledger = get_agent().ledger
    return {"ok": True, "spend_usd_today": round(ledger.total_usd, 4), "cap_usd_per_day":
            ledger.cap_usd, "day": ledger.today()}


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
