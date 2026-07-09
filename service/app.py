"""HTTP surface for the agent service — one endpoint, CORS-open for the static page.

    POST /ask {"question": "..."} -> the CLI --json payload shape (+ agent/followup fields),
                                     or {"error": "cap_exceeded" | "unanswerable" | "llm_error: ..."}

Application-level conditions (cap reached, off-topic question) return HTTP 200 with an
``error`` field — the frontend reads the body and falls back to the form flow with the right
notice. Transport-level failures (service down, timeout) need no server cooperation: the
frontend's fetch timeout handles them.

Run locally (uv venv outside the repo — see service/README.md):
    %USERPROFILE%\\.venvs\\solar-calc\\Scripts\\python.exe service/app.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from agent import Agent  # noqa: E402

HOST = os.environ.get("SOLAR_AGENT_HOST", "127.0.0.1")
PORT = int(os.environ.get("SOLAR_AGENT_PORT", "8765"))

app = FastAPI(title="Maine Solar Ledger — agent service")
# The static page runs from file:// (origin "null"), so CORS must be wide open. The service
# binds to localhost and holds no secrets beyond its own spend ledger.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


class Ask(BaseModel):
    question: str


@app.post("/ask")
def ask(body: Ask) -> dict:
    return get_agent().answer(body.question)


@app.get("/health")
def health() -> dict:
    ledger = get_agent().ledger
    return {"ok": True, "spend_usd": round(ledger.total_usd, 4), "cap_usd": ledger.cap_usd}


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        print("  Set it for this shell, e.g.:  $env:ANTHROPIC_API_KEY = '<your key>'", file=sys.stderr)
        print("  Details: service/README.md", file=sys.stderr)
        raise SystemExit(1)
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
