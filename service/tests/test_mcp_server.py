"""MCP server tests — the tool surface, and the claims that make it safe to host publicly.

No stubbing is needed anywhere here: there is no model on this path. That is the property being
tested as much as anything else — if an ``ANTHROPIC_API_KEY`` ever becomes necessary to call
``calculate``, this file stops working, which is the alarm we want.

Tools are driven through ``FastMCP.call_tool`` (the same entry point the transport uses) via
``asyncio.run`` rather than pulling in an async-test plugin for four calls.

Run with: pytest service/tests
"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools_core  # noqa: E402
from mcp_server import mcp  # noqa: E402


def call(name: str, **arguments):
    """Call a tool and return its result decoded, as a client would receive it.

    ``call_tool`` hands back either content blocks or a structured dict; a tool returning a bare
    list (``list_options``) comes back wrapped as ``{"result": [...]}``.
    """
    out = asyncio.run(mcp.call_tool(name, arguments))
    content, structured = out if isinstance(out, tuple) else (out, None)
    if isinstance(structured, dict):
        return structured.get("result", structured)
    return json.loads(content[0].text)


class TestToolsRegistered:
    def test_all_four_tools_exist(self):
        names = {t.name for t in asyncio.run(mcp.list_tools())}
        assert names == {"list_options", "get_assumptions", "calculate", "compare"}

    def test_every_tool_documents_itself_for_a_model(self):
        # The description is the only thing a calling agent reads before deciding to use a tool.
        for tool in asyncio.run(mcp.list_tools()):
            assert tool.description and len(tool.description) > 80, tool.name

    def test_server_instructions_flag_the_unsourced_caveat(self):
        # An agent relaying a placeholder as fact is the failure mode this project exists to avoid.
        assert "unsourced" in mcp.instructions


class TestNoModelOnThisPath:
    def test_calculate_works_with_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        payload = call("calculate", option="rooftop")
        assert payload["result"]["upfront_cost"] > 0

    def test_no_spend_is_recorded(self, monkeypatch, tmp_path):
        ledger_path = tmp_path / "spend.json"
        monkeypatch.setenv("SOLAR_AGENT_LEDGER_PATH", str(ledger_path))
        call("calculate", option="battery")
        assert not ledger_path.exists()   # nothing on this path can spend


class TestPayloads:
    def test_calculate_returns_steps_and_sourced_assumptions(self):
        # The reason this tool is worth exposing: not just the number, but how it was reached.
        payload = call("calculate", option="rooftop", inputs={"capacity_kw": 8})
        assert payload["result"]["upfront_cost"] == pytest.approx(23600.0)
        assert payload["steps"] and all(s["formula"] for s in payload["steps"])
        src = payload["assumptions"]["installed_cost_per_w"]["source"]
        assert src["title"] and src["what_is_it"]
        assert payload["assumptions"]["capacity_kw"]["tag"] == "user-provided"

    def test_calculate_matches_tools_core_exactly(self):
        expected, _ = tools_core.calculate("battery+rooftop")
        got = call("calculate", option="battery+rooftop")
        got.pop("ignored_inputs", None)
        assert got == expected

    def test_list_options_is_the_full_option_set(self):
        assert [o["key"] for o in call("list_options")] == list(tools_core.ALL_OPTION_KEYS)

    def test_get_assumptions_marks_placeholders(self):
        a = call("get_assumptions", option="plugin-battery")["assumptions"]
        assert a["installed_cost_per_kwh"]["is_unsourced"]
        assert a["enrollment_discount_per_kwh"]["tag"] == "default (sourced)"

    def test_compare_summary_is_side_by_side(self):
        result = call("compare", options=["community", "rooftop", "battery"])
        assert [r["option"] for r in result["summary"]] == ["community", "rooftop", "battery"]
        assert result["summary"][0]["npv"] is None      # community stakes no capital

    def test_unmapped_input_comes_back_named(self):
        payload = call("calculate", option="community", inputs={"capacity_kw": 8})
        assert payload["ignored_inputs"] == {"capacity_kw": 8}


class TestPublicExposureIsBounded:
    """The whole no-auth argument rests on this: the one-shot blowup is bounded on the INPUT,
    because a rate limit bounds request frequency and can do nothing about a single bad request."""

    def test_absurd_horizon_is_an_error_not_a_computation(self):
        with pytest.raises(Exception) as e:
            call("calculate", option="rooftop", inputs={"horizon_years": 1e9})
        assert "between 1 and 100" in str(e.value)

    def test_unknown_option_is_an_error(self):
        with pytest.raises(Exception):
            call("calculate", option="../../etc/passwd")


class TestTransportConfig:
    def test_http_mode_allows_the_railway_domain(self, monkeypatch):
        import mcp_server

        monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "solar.up.railway.app")
        before = list(mcp.settings.transport_security.allowed_hosts)
        try:
            mcp_server.configure_http()
            assert "solar.up.railway.app" in mcp.settings.transport_security.allowed_hosts
            # Protection stays ON — the deploy host is allowed, not the check disabled.
            assert mcp.settings.transport_security.enable_dns_rebinding_protection
        finally:
            mcp.settings.transport_security.allowed_hosts = before

    def test_http_mode_is_stateless(self, monkeypatch):
        import mcp_server

        monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
        mcp_server.configure_http()
        # Every tool is a pure function of its arguments, so a redeploy can't strand a session.
        assert mcp.settings.stateless_http


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
