"""MCP server — the calculator as tools an agent can call directly.

Four tools over ``tools_core``: ``list_options``, ``get_assumptions``, ``calculate``, ``compare``.

**No LLM is on this path, by design.** The agent calling these tools *is* the model; it arrives
having already decided it wants ``calculate("rooftop", {"capacity_kw": 8})``. So this surface is
pure Python arithmetic over ``src/`` — no ``ANTHROPIC_API_KEY``, no spend ledger, no cap, no
``cap_exceeded`` state to reason about. That is what makes hosting it publicly with no auth cheap
and honest: there is no user data, no secret, and nothing to authorize. The one real risk is a
single request driving an unbounded loop, and that is bounded in ``tools_core.check_inputs`` (see
its docstring) rather than asserted away.

What makes this worth exposing is the *shape* of what it returns. Most calculator APIs hand back a
number; this one hands back the number plus every labeled assumption, its source, what that source
*is* and why it's credible, and the full step chain — the same payload the CLI's ``--json`` emits.
An agent using it can cite its work, and a human can fact-check it. Assumptions tagged
``unsourced — pending research`` say so in the payload; an agent relaying one should say so too.

Two transports, one set of tool definitions:

    python service/mcp_server.py --stdio      # local: no hosting, for development and testing
    (mounted at /mcp by service/app.py)       # public: streamable HTTP on the Railway deploy
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP  # noqa: E402

import tools_core  # noqa: E402
from feedback import FeedbackLog  # noqa: E402

_log = FeedbackLog.from_env()


def _log_call(tool: str, **args) -> None:
    """Record one tool call. Agent-native usage is half this project's thesis and, without this,
    entirely invisible: there is no LLM, no cookie and no page on the MCP path.

    Only the tool name and an argument *summary* — the option keys and which input keys were
    overridden, not their values. There is no client identity to record here either; the request
    middleware in ``app.py`` logs the IP and user-agent for the same request a moment earlier, and
    for MCP the user-agent is genuinely informative (a Claude connector reads differently from a
    script). Best-effort by construction — ``FeedbackLog.append`` never raises.
    """
    _log.append("mcp_tool_call", tool=tool, **args)

INSTRUCTIONS = """Estimate what each residential solar option saves a Maine homeowner, with every
number traceable. Call list_options to see what can be modeled, get_assumptions(option) to read an
option's inputs with their sources, calculate(option, inputs) for one estimate, and compare for a
side-by-side table.

Two things to relay accurately to a user:
  * Any assumption tagged "unsourced — pending research" is a placeholder, not an established
    fact. Say so rather than presenting it as sourced.
  * NPV > 0 means buying beats investing the same cash at the opportunity rate. Comparisons are
    only meaningful at one shared opportunity_rate.

This is a proof of concept built on general Maine defaults — not financial advice and not a quote.
"""

mcp = FastMCP("maine-solar-calculator", instructions=INSTRUCTIONS)


def configure_http() -> None:
    """Settings that only apply when this server is reached over HTTP rather than stdio.

    **Stateless.** Every tool here is a pure function of its arguments — there is no session state
    to keep — so each request stands alone. That removes the initialize/session-id handshake as a
    thing that can go wrong for a connector, and it means a redeploy (Railway containers are
    ephemeral) can never strand a client holding a dead session id.

    **DNS-rebinding protection stays on, with the deploy's host allowed.** The SDK defaults to
    localhost-only, which is right for a locally bound server and wrong for a public one: unset,
    the deploy would reject every request as an invalid Host. Railway exposes its domain as
    ``RAILWAY_PUBLIC_DOMAIN``, so the correct host is picked up automatically;
    ``SOLAR_MCP_ALLOWED_HOSTS`` (comma-separated) covers a custom domain or a test harness. Note
    this is not the protection that matters here — there is no local privilege to steal from a
    public calculator — but silently disabling a security default is worse than configuring it.
    """
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    extra = [h.strip() for h in os.environ.get("SOLAR_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if domain:
        extra += [domain, f"{domain}:*"]
    if extra:
        sec = mcp.settings.transport_security
        sec.allowed_hosts = list(sec.allowed_hosts) + extra
        sec.allowed_origins = (list(sec.allowed_origins)
                               + [f"https://{h}" for h in extra] + [f"http://{h}" for h in extra])


def http_handler():
    """The raw ASGI handler for streamable HTTP, ready to mount at any prefix.

    ``streamable_http_app()`` builds the session manager (lazily — this call is what creates it)
    and wraps it in a Starlette app whose single route lives at ``settings.streamable_http_path``.
    Mounting *that* under a prefix puts the endpoint at ``<prefix>/mcp`` and leaves a bare
    ``<prefix>`` returning 405 — a papercut for every connector that is handed the obvious URL. The
    session manager's own handler ignores the path, so mounting it directly makes both
    ``/mcp`` and ``/mcp/`` work. Transport security is enforced inside the transport, not in the
    discarded Starlette wrapper, so nothing is lost by skipping it.

    The caller must run ``mcp.session_manager.run()`` as part of its lifespan.
    """
    configure_http()
    mcp.streamable_http_app()          # side effect: creates the session manager
    return mcp.session_manager.handle_request


@mcp.tool()
def list_options() -> list[dict]:
    """List every solar option this calculator models: key, label, blurb, whether it needs a bill.

    Use the returned ``key`` for the ``option`` argument of the other tools.
    """
    _log_call("list_options")
    return tools_core.list_options()


@mcp.tool()
def get_assumptions(option: str) -> dict:
    """Read one option's full assumption ledger before calculating with it.

    Each assumption carries: key, label, value, unit, tag ("default (sourced)" | "user-provided" |
    "unsourced — pending research"), a plain-English ``explain``, and for sourced values a
    ``source`` with its title, url, note, and ``what_is_it`` (what the document is, who publishes
    it, why it's credible). The keys returned here are exactly the keys ``calculate``'s ``inputs``
    accepts.
    """
    _log_call("get_assumptions", option=option)
    return tools_core.get_assumptions(option)


@mcp.tool()
def calculate(option: str, inputs: dict[str, float] | None = None) -> dict:
    """Estimate one option's savings, returning the answer AND how it was reached.

    ``inputs`` overrides any assumption by key (call ``get_assumptions`` for the keys) — e.g.
    ``{"capacity_kw": 8}`` for rooftop, ``{"monthly_bill": 220}`` for community. Overridden values
    come back tagged "user-provided", so the payload always distinguishes what the user supplied
    from what the calculator defaulted.

    Returns the result, the full ``steps`` chain (each step's label, formula, inputs used, and
    value), the year-by-year cashflow, and every assumption with its source. ``ignored_inputs``
    lists any key that matched no assumption of this option — it is never silently dropped.
    """
    _log_call("calculate", option=option, input_keys=sorted(inputs or {}))
    payload, ignored = tools_core.calculate(option, inputs or {})
    payload["ignored_inputs"] = ignored
    return payload


@mcp.tool()
def compare(options: list[str], inputs: dict[str, float] | None = None) -> dict:
    """Put two or more options side by side. Every row equals what ``calculate`` says for it alone.

    ``inputs`` are SHARED: each applies to every compared option that carries the key — which is
    the point for ``opportunity_rate``, since NPVs computed at different discount rates are not
    comparable. Returns a ``summary`` table (upfront, year-1 savings, payback, NPV) plus each
    option's complete ledger under ``options``.

    Community solar stakes no capital, so its payback and NPV come back null — not applicable,
    not zero.
    """
    _log_call("compare", options=list(options or []), input_keys=sorted(inputs or {}))
    return tools_core.compare(options, inputs or {})


if __name__ == "__main__":
    if "--stdio" in sys.argv or not sys.argv[1:]:
        mcp.run(transport="stdio")
    elif "--http" in sys.argv:
        # Standalone streamable HTTP, for testing the transport without the FastAPI app.
        # The deploy does NOT use this path — it mounts http_handler() on service/app.py.
        configure_http()
        mcp.settings.host = os.environ.get("SOLAR_MCP_HOST", "127.0.0.1")
        mcp.settings.port = int(os.environ.get("SOLAR_MCP_PORT", "8766"))
        mcp.run(transport="streamable-http")
    else:
        print(f"usage: {sys.argv[0]} [--stdio | --http]", file=sys.stderr)
        raise SystemExit(2)
