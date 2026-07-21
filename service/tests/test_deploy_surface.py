"""What the public deploy exposes, and what bounds it.

``/ask`` is the only path here that can spend money, and on the deploy it is unauthenticated. The
bounds on it stack, each covering what the others can't — a daily dollar cap (``test_spend.py``),
a per-IP rate limit, a question-length cap, and an input clamp (``test_tools_core.py``). This file
holds the two that live in the HTTP layer, plus the routing that makes the deploy a single origin.

The LLM is never reached: the agent is stubbed or the paths under test refuse before routing.

Run with: pytest service/tests
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SOLAR_MCP_ALLOWED_HOSTS", "testserver")

import app as app_module  # noqa: E402


# The lifespan-entered ``client`` fixture is session-scoped in conftest.py: starting the MCP
# session manager can only happen once per process, so it cannot be per-module.


@pytest.fixture(autouse=True)
def _isolated_agent(tmp_path):
    """A stubbed agent per test: no key, no network, and a throwaway ledger and cache.

    ``/ask`` must still answer for the rate-limit and length tests, and it must never reach the
    model to do it.
    """
    from agent import Agent, Extraction
    from cache import ExtractionCache
    from spend import SpendLedger
    from agent import cache_version

    extraction = Extraction(option="community", inputs={"monthly_bill": 150}, note="stub")
    app_module._agent = Agent(
        extractor=lambda question: extraction,
        ledger=SpendLedger(path=str(tmp_path / "spend.json"), cap_usd=5.0),
        cache=ExtractionCache(path=str(tmp_path / "cache.json"), version=cache_version()),
    )
    app_module._buckets.clear()         # each test gets a fresh rate-limit window
    yield
    app_module._agent = None
    app_module._buckets.clear()


class TestSameOriginDeploy:
    """One service, one origin: the page, the agent, and the MCP server."""

    def test_the_page_is_served(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "<html" in res.text.lower()

    def test_app_js_is_served(self, client):
        assert client.get("/app.js").status_code == 200

    def test_health_reports_the_daily_window(self, client):
        body = client.get("/health").json()
        assert body["ok"] and "spend_usd_today" in body and "cap_usd_per_day" in body

    def test_static_mount_does_not_shadow_the_api(self, client):
        # The catch-all page mount is registered last for exactly this reason.
        assert client.get("/health").status_code == 200
        assert client.post("/ask", json={"question": ""}).status_code == 200

    def test_the_page_calls_a_relative_ask_when_hosted(self):
        # Same-origin deploy -> relative /ask (no CORS); file:// -> the local port, which is the
        # dev and verifier flow whose fallback notice is verifier-enforced.
        web = os.path.join(os.path.dirname(__file__), "..", "..", "web", "app.js")
        with open(web, encoding="utf-8") as fh:
            src = fh.read()
        assert 'location.protocol === "file:"' in src
        assert '"/ask"' in src


class TestMcpMounted:
    def test_bare_and_slashed_paths_both_work(self, client):
        headers = {"Accept": "application/json, text/event-stream",
                   "Content-Type": "application/json"}
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        for path in ("/mcp", "/mcp/"):
            res = client.post(path, json=body, headers=headers)
            assert res.status_code == 200, path
            names = {t["name"] for t in res.json()["result"]["tools"]}
            assert names == {"list_options", "get_assumptions", "calculate", "compare"}

    def test_calculate_over_http_returns_steps(self, client):
        import json

        headers = {"Accept": "application/json, text/event-stream",
                   "Content-Type": "application/json"}
        res = client.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "calculate",
                       "arguments": {"option": "rooftop", "inputs": {"capacity_kw": 8}}},
        })
        payload = json.loads(res.json()["result"]["content"][0]["text"])
        assert payload["result"]["upfront_cost"] == pytest.approx(23600.0)
        assert payload["steps"]


class TestAskIsBounded:
    def test_a_pasted_novel_is_refused_before_the_model(self, client):
        # Length is billed by the token, so this rejection must happen in the HTTP layer.
        body = client.post("/ask", json={"question": "x" * 5000}).json()
        assert body["error"] == "question_too_long"

    def test_a_normal_question_is_not_length_limited(self, client, monkeypatch):
        long_but_reasonable = "Is a rooftop system worth it if I use 9,000 kWh a year? " * 3
        assert len(long_but_reasonable) < app_module.MAX_QUESTION_CHARS
        body = client.post("/ask", json={"question": long_but_reasonable}).json()
        assert body.get("error") != "question_too_long"

    def test_empty_question_is_refused(self, client):
        assert client.post("/ask", json={"question": "   "}).json()["error"] == "unanswerable"

    def test_rate_limit_trips_after_the_allowance(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "RATE_LIMIT_PER_MINUTE", 3)
        app_module._buckets.clear()
        errors = [client.post("/ask", json={"question": f"q{i}"}).json().get("error")
                  for i in range(5)]
        assert errors[-1] == "rate_limited"
        assert errors.count("rate_limited") == 2      # the first 3 got through to the agent

    def test_rate_limit_is_per_client_not_global(self, client, monkeypatch):
        monkeypatch.setattr(app_module, "RATE_LIMIT_PER_MINUTE", 2)
        app_module._buckets.clear()
        for _ in range(3):
            client.post("/ask", json={"question": "q"}, headers={"X-Forwarded-For": "1.1.1.1"})
        # A different visitor must not inherit the first one's exhausted bucket.
        body = client.post("/ask", json={"question": "q"},
                           headers={"X-Forwarded-For": "2.2.2.2"}).json()
        assert body.get("error") != "rate_limited"


class TestClientIpBehindAProxy:
    """Railway terminates TLS at a proxy. Keyed on ``request.client.host``, the bucket would see
    the proxy for every request on earth — throttling either everyone as one client or no one."""

    def _request(self, headers):
        class _Req:
            def __init__(self, h):
                self.headers = h
                self.client = type("C", (), {"host": "10.0.0.1"})()
        return _Req(headers)

    def test_first_forwarded_hop_wins(self):
        req = self._request({"x-forwarded-for": "203.0.113.7, 10.0.0.1, 10.0.0.2"})
        assert app_module.client_ip(req) == "203.0.113.7"

    def test_falls_back_to_the_socket_peer_locally(self):
        assert app_module.client_ip(self._request({})) == "10.0.0.1"

    def test_bucket_is_bounded(self):
        # The limiter must not become the memory leak it exists to prevent.
        app_module._buckets.clear()
        for i in range(app_module._RATE_LIMIT_MAX_IPS + 50):
            app_module.rate_limited(f"10.0.{i // 256}.{i % 256}")
        assert len(app_module._buckets) <= app_module._RATE_LIMIT_MAX_IPS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
