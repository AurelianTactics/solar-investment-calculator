"""Instrumentation at the HTTP surface: what gets recorded, and what it must never break.

Two things are under test and the second matters more than the first.

**What's recorded** — one line per request from the middleware (the only telemetry that needs no
client cooperation, and the only window onto ``/mcp``), a richer line per ``/ask`` carrying the
question verbatim and its intent label, and client events on ``/events``.

**What it must never break** — ``/events`` is a public, unauthenticated *write* endpoint, which is
a different threat than ``/ask``: rate limiting bounds request rate, and disk is rate integrated
over time, so the body and batch caps are what actually bound it. And with the log refusing for any
reason, ``/ask`` must still answer. Telemetry that can take down the calculator is worse than no
telemetry.

The LLM is never reached — the agent is stubbed.

Run with: pytest service/tests
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SOLAR_MCP_ALLOWED_HOSTS", "testserver")

import app as app_module  # noqa: E402
from feedback import FeedbackLog  # noqa: E402


# ``client`` (lifespan-entered, so /mcp routes) is session-scoped in conftest.py — see there for
# why it cannot be per-module.


@pytest.fixture(autouse=True)
def log(tmp_path, monkeypatch):
    """A throwaway log per test, swapped in for the module-level one the handlers close over."""
    fresh = FeedbackLog(path=str(tmp_path / "feedback.jsonl"))
    monkeypatch.setattr(app_module, "log", fresh)
    app_module._buckets.clear()
    yield fresh
    app_module._buckets.clear()


@pytest.fixture(autouse=True)
def _stub_agent(tmp_path):
    """No key, no network, a throwaway ledger and cache — /ask must answer without the model."""
    from agent import Agent, Extraction, cache_version
    from cache import ExtractionCache
    from spend import SpendLedger

    extraction = Extraction(option="rooftop", inputs={"capacity_kw": 8}, note="stub",
                            intent="calculate")
    app_module._agent = Agent(
        extractor=lambda question: extraction,
        ledger=SpendLedger(path=str(tmp_path / "spend.json"), cap_usd=5.0),
        cache=ExtractionCache(path=str(tmp_path / "cache.json"), version=cache_version()),
    )
    yield
    app_module._agent = None


def lines(log: FeedbackLog, kind: str | None = None) -> list[dict]:
    if not os.path.exists(log.path):
        return []
    with open(log.path, encoding="utf-8") as fh:
        out = [json.loads(line) for line in fh if line.strip()]
    return [line for line in out if kind is None or line["kind"] == kind]


class TestRequestLog:
    def test_every_request_logs_one_line(self, client, log):
        client.get("/health")
        recorded = lines(log, "request")
        assert len(recorded) == 1
        assert recorded[0]["path"] == "/health"
        assert recorded[0]["status"] == 200
        assert recorded[0]["method"] == "GET"
        assert isinstance(recorded[0]["ms"], int)

    def test_records_ip_user_agent_and_referrer(self, client, log):
        """R5: the raw client IP, deliberately. Without a stable per-visitor value you cannot tell
        ten homeowners from one enthusiast reloading, and the referrer IS "where did they come
        from". This is what any web server's access log holds; R8 is the obligation it creates."""
        client.get("/health", headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1",
                                       "user-agent": "Mozilla/5.0 (test)",
                                       "referer": "https://news.example.com/maine-solar"})
        entry = lines(log, "request")[0]
        assert entry["ip"] == "203.0.113.9"          # the client, not the proxy
        assert entry["ua"] == "Mozilla/5.0 (test)"
        assert entry["referrer"] == "https://news.example.com/maine-solar"

    def test_covers_mcp_which_runs_no_javascript(self, client, log):
        """R10: MCP is the only window onto agent-native usage, and no client event can ever
        describe it — there is no page and no script on that path."""
        client.post("/mcp",
                    headers={"content-type": "application/json",
                             "accept": "application/json, text/event-stream"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        paths = [line["path"] for line in lines(log, "request")]
        # The ROUTED path: a bare /mcp is normalized to /mcp/ upstream of this middleware, which
        # is the useful end of the trade — all MCP traffic groups under one path.
        assert "/mcp/" in paths

    def test_a_refusing_log_does_not_break_the_request(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(app_module, "log",
                            FeedbackLog(path=str(tmp_path / "full.jsonl"), max_bytes=0))
        assert client.get("/health").status_code == 200


class TestAskLog:
    def test_question_is_stored_verbatim_with_its_intent(self, client, log):
        client.post("/ask", json={"question": "Is rooftop worth it at 9000 kWh?"})
        entry = lines(log, "ask")[0]
        assert entry["question"] == "Is rooftop worth it at 9000 kWh?"
        assert entry["intent"] == "calculate"
        assert entry["option"] == "rooftop"
        assert entry["error"] is None

    def test_intent_is_unknown_when_the_model_never_ran(self, client, log, tmp_path):
        """S2: the text is the asset; the label is derivable offline. A question asked while the
        LLM is down or the cap is tripped must still be recorded, not dropped."""
        from agent import Agent, cache_version
        from cache import ExtractionCache
        from spend import SpendLedger

        app_module._agent = Agent(
            extractor=lambda q: (_ for _ in ()).throw(RuntimeError("anthropic is down")),
            ledger=SpendLedger(path=str(tmp_path / "s2.json"), cap_usd=5.0),
            cache=ExtractionCache(path=str(tmp_path / "c2.json"), version=cache_version()),
        )
        client.post("/ask", json={"question": "what would a battery save me"})
        entry = lines(log, "ask")[0]
        assert entry["question"] == "what would a battery save me"
        assert entry["intent"] == "unknown"
        assert "llm_error" in entry["error"]

    def test_refused_questions_are_logged_too(self, client, log):
        client.post("/ask", json={"question": "x" * (app_module.MAX_QUESTION_CHARS + 1)})
        # Refused before the agent: no `ask` line to write, but the request itself is recorded.
        assert lines(log, "ask") == []
        assert lines(log, "request")[0]["path"] == "/ask"

    def test_ask_still_answers_when_the_log_refuses(self, client, monkeypatch, tmp_path):
        """The definition of done: telemetry must never be what stops the agent answering."""
        monkeypatch.setattr(app_module, "log",
                            FeedbackLog(path=str(tmp_path / "full.jsonl"), max_bytes=0))
        body = client.post("/ask", json={"question": "Is rooftop worth it?"}).json()
        assert "error" not in body
        assert body["option"] == "rooftop"

    def test_a_full_log_does_not_stop_the_spend_ledger(self, client, monkeypatch, tmp_path):
        """Both live on one Railway volume, and the ledger fails CLOSED. The log yields first."""
        monkeypatch.setattr(app_module, "log",
                            FeedbackLog(path=str(tmp_path / "full.jsonl"), max_bytes=0))
        ledger = app_module._agent.ledger
        ledger.record(1000, 1000)
        assert ledger.total_usd > 0
        assert client.get("/health").json()["spend_usd_today"] > 0


class TestEvents:
    def test_accepts_a_batch_of_client_events(self, client, log):
        res = client.post("/events", json={"events": [
            {"kind": "option_selected", "option": "battery"},
            {"kind": "assumption_edited", "key": "installed_cost_per_w", "from": 2.95, "to": 3.6,
             "option": "rooftop", "tag": "unsourced - pending research"},
            {"kind": "compared", "options": ["community", "rooftop"]},
        ]})
        assert res.json() == {"ok": True, "written": 3}

        edit = lines(log, "assumption_edited")[0]
        assert (edit["from"], edit["to"]) == (2.95, 3.6)
        assert edit["key"] == "installed_cost_per_w"
        assert edit["tag"] == "unsourced - pending research"
        assert lines(log, "compared")[0]["options"] == ["community", "rooftop"]

    def test_direction_and_magnitude_survive_as_numbers(self, client, log):
        """S3: the research finding is that ten people all raised this to about $3.60 — which
        needs `from`/`to` to stay numeric, not stringified."""
        client.post("/events", json={"events": [
            {"kind": "assumption_edited", "key": "installed_cost_per_w", "from": 2.95, "to": 3.6}]})
        edit = lines(log, "assumption_edited")[0]
        assert isinstance(edit["from"], float) and isinstance(edit["to"], float)

    def test_feedback_carries_the_scenario_url(self, client, log):
        """S4: a thumbs-down alone is noise; one WITH the scenario that produced it is
        reproducible."""
        url = "https://example.com/?o=rooftop&bill=220&a.installed_cost_per_w=3.6"
        client.post("/events", json={"events": [
            {"kind": "feedback", "verdict": "down", "text": "payback looks too optimistic",
             "scenario_url": url}]})
        entry = lines(log, "feedback")[0]
        assert entry["verdict"] == "down"
        assert entry["text"] == "payback looks too optimistic"
        assert entry["scenario_url"] == url

    def test_oversized_body_is_rejected(self, client, log):
        """R4: rate limiting bounds request RATE; disk is rate integrated over time. The body cap
        is what actually bounds what one client can write."""
        fat = json.dumps({"events": [{"kind": "feedback", "text": "x" * 5000}]})
        res = client.post("/events", content=fat,
                          headers={"content-type": "application/json"})
        assert res.json()["error"] == "too_large"
        assert lines(log) == [] or all(line["kind"] == "request" for line in lines(log))

    def test_too_many_events_in_one_batch_is_rejected(self, client, log):
        batch = [{"kind": "option_selected", "option": "rooftop"}
                 for _ in range(app_module.MAX_EVENTS_PER_BATCH + 1)]
        assert client.post("/events", json={"events": batch}).json()["error"] == "too_many_events"
        assert lines(log, "option_selected") == []

    def test_long_free_text_is_truncated_not_rejected(self, client, log):
        """Rejecting a batch costs an attacker nothing; rejecting a person's paragraph throws away
        the feedback we asked for."""
        client.post("/events", json={"events": [
            {"kind": "feedback", "verdict": "down", "text": "y" * 900}]})
        assert len(lines(log, "feedback")[0]["text"]) == 900

        app_module._buckets.clear()
        client.post("/events", json={"events": [{"kind": "feedback", "text": "z" * 1500}]})
        assert len(lines(log, "feedback")[1]["text"]) == app_module.MAX_TEXT_CHARS

    def test_unknown_kinds_are_dropped(self, client, log):
        """An allow-list, not a passthrough: /events is public, so without one the log's contents
        would be whatever a stranger decided to POST."""
        res = client.post("/events", json={"events": [
            {"kind": "option_selected", "option": "rooftop"},
            {"kind": "arbitrary_junk", "payload": "anything"},
            "not even an object",
        ]})
        assert res.json()["written"] == 1
        assert [line["kind"] for line in lines(log) if line["kind"] != "request"] \
            == ["option_selected"]

    def test_malformed_json_is_refused_without_raising(self, client):
        res = client.post("/events", content=b"{not json",
                          headers={"content-type": "application/json"})
        assert res.status_code == 200 and res.json()["error"] == "bad_json"

    def test_events_rate_limit_does_not_starve_asking(self, client, log):
        """Separate buckets: flushing events while tuning assumptions must not consume the
        allowance for asking questions."""
        for _ in range(app_module.EVENTS_RATE_LIMIT_PER_MINUTE + 2):
            client.post("/events", json={"events": [{"kind": "option_selected",
                                                     "option": "rooftop"}]})
        assert client.post("/events", json={"events": []}).json()["error"] == "rate_limited"
        assert "error" not in client.post("/ask", json={"question": "rooftop?"}).json()

    def test_a_refusing_log_still_returns_ok(self, client, monkeypatch, tmp_path):
        """R9: the page must behave identically whether this endpoint stores anything or not."""
        monkeypatch.setattr(app_module, "log",
                            FeedbackLog(path=str(tmp_path / "full.jsonl"), max_bytes=0))
        res = client.post("/events", json={"events": [{"kind": "option_selected",
                                                       "option": "rooftop"}]})
        assert res.status_code == 200
        assert res.json() == {"ok": True, "written": 0}


class TestHealthReportsTheLog:
    def test_health_shows_size_against_ceiling(self, client, log):
        log.append("request", path="/")
        body = client.get("/health").json()
        assert body["log"]["accepting"] is True
        assert body["log"]["bytes"] > 0
        assert "spend_usd_today" in body        # the spend figure is still there

    def test_health_announces_a_full_log(self, client, monkeypatch, tmp_path):
        """R3: "the log is full" should be visible, not discovered from missing events."""
        monkeypatch.setattr(app_module, "log",
                            FeedbackLog(path=str(tmp_path / "full.jsonl"), max_bytes=0))
        body = client.get("/health").json()
        assert body["ok"] is True
        assert body["log"]["accepting"] is False
        assert body["log"]["refusing_because"] == "log_full"
