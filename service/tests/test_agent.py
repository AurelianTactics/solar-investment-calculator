"""Agent-service tests — the LLM is ALWAYS stubbed (no network, no key needed).

The seam: Agent(extractor=...) takes any callable question -> Extraction. Routing quality is
the live model's job; these tests pin the machinery around it: parity with the Python core,
honest tagging, structured errors, the cap, and the HTTP surface.

Run with: pytest service/tests
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import solar_calc  # noqa: E402
from agent import Agent, Extraction, cache_version  # noqa: E402
from cache import ExtractionCache  # noqa: E402
from spend import SpendLedger, cost_usd  # noqa: E402

SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def stub(option, inputs=None, unanswerable=False):
    ex = Extraction(option=option, inputs=inputs or {}, unanswerable=unanswerable, note="stub")
    return lambda question: ex


def make_agent(tmp_path, extractor, cap=5.0):
    # Both files are per-test: a shared cache would leak one test's routing into another's, and
    # neither belongs in the developer's real service/ directory.
    ledger = SpendLedger(path=str(tmp_path / "spend.json"), cap_usd=cap)
    cache = ExtractionCache(path=str(tmp_path / "cache.json"), version=cache_version())
    return Agent(extractor=extractor, ledger=ledger, cache=cache)


class TestRouting:
    def test_default_question_routes_to_community_with_bill_150(self, tmp_path):
        agent = make_agent(tmp_path, stub("community", {"monthly_bill": 150}))
        payload = agent.answer("What savings would I get with community solar when my bill is $150 a month?")
        assert payload["option"] == "community"
        assert payload["inputs"]["monthly_bill"] == 150
        assert payload["agent"]["extracted"] == {"monthly_bill": 150}

    def test_battery_rooftop_question_with_capacity(self, tmp_path):
        agent = make_agent(tmp_path, stub("battery+rooftop", {"capacity_kw": 8}))
        payload = agent.answer("batteries with rooftop solar for a 8kW roof")
        assert payload["option"] == "battery+rooftop"
        assert payload["assumptions"]["capacity_kw"]["value"] == 8.0


class TestParityWithTheCore:
    def test_service_numbers_equal_solar_calc_exactly(self, tmp_path):
        # The agent path cannot diverge from the source of truth (R6): same inputs, same result.
        agent = make_agent(tmp_path, stub("community", {"monthly_bill": 150}))
        payload = agent.answer("the canonical question")
        expected = solar_calc.compute(
            monthly_bill=150, price_per_kwh=0.306, bill_offset_fraction=0.82,
            subscription_discount_pct=0.15, allocation_pct=1.0,
        )
        assert payload["result"]["annual_savings"] == expected.annual_savings
        assert payload["result"]["monthly_savings"] == expected.monthly_savings

    def test_payload_shape_matches_cli_json(self, tmp_path):
        agent = make_agent(tmp_path, stub("community", {"monthly_bill": 150}))
        payload = agent.answer("q")
        assert set(payload) >= {"option", "inputs", "result", "steps", "assumptions",
                                "agent", "followup"}
        assert payload["steps"][0]["label"]  # calculation chain present


class TestHonestTagging:
    def test_extracted_bill_arrives_user_provided(self, tmp_path):
        agent = make_agent(tmp_path, stub("community", {"monthly_bill": 150}))
        payload = agent.answer("q")
        bill_asm = payload["assumptions"]["default_monthly_bill"]
        assert bill_asm["tag"] == "user-provided"
        assert bill_asm["value"] == 150.0
        assert bill_asm["source"] is None  # extraction is not a source

    def test_untouched_assumptions_keep_their_tags(self, tmp_path):
        agent = make_agent(tmp_path, stub("community", {"monthly_bill": 150}))
        payload = agent.answer("q")
        assert payload["assumptions"]["subscription_discount_pct"]["tag"] == "default (sourced)"

    def test_capital_extraction_tags(self, tmp_path):
        agent = make_agent(tmp_path, stub("rooftop", {"capacity_kw": 8}))
        payload = agent.answer("q")
        assert payload["assumptions"]["capacity_kw"]["tag"] == "user-provided"
        assert payload["assumptions"]["installed_cost_per_w"]["tag"] == "default (sourced)"


class TestInputKeyNormalization:
    def test_prefixed_key_maps_onto_bare_battery_option(self, tmp_path):
        # The extraction schema says battery_usable_kwh; the plain battery option uses bare keys.
        agent = make_agent(tmp_path, stub("battery", {"battery_usable_kwh": 20}))
        payload = agent.answer("is a 20 kWh battery worth it?")
        assert payload["assumptions"]["usable_kwh"]["value"] == 20.0
        assert payload["assumptions"]["usable_kwh"]["tag"] == "user-provided"
        assert payload["agent"]["ignored_inputs"] == {}

    def test_bare_key_maps_onto_combo_prefixed_key(self, tmp_path):
        agent = make_agent(tmp_path, stub("battery+rooftop", {"usable_kwh": 20}))
        payload = agent.answer("rooftop with a 20 kWh battery")
        assert payload["assumptions"]["battery_usable_kwh"]["value"] == 20.0

    def test_unmappable_input_is_surfaced_not_dropped(self, tmp_path):
        agent = make_agent(tmp_path, stub("community", {"monthly_bill": 150, "roof_pitch": 30}))
        payload = agent.answer("q")
        assert payload["agent"]["ignored_inputs"] == {"roof_pitch": 30}
        assert payload["result"]["annual_savings"] > 0  # the mappable input still computed


class TestFollowup:
    def test_response_names_the_tightening_input(self, tmp_path):
        agent = make_agent(tmp_path, stub("community", {"monthly_bill": 150}))
        assert "annual kWh usage" in agent.answer("q")["followup"]


class TestStructuredErrors:
    def test_unanswerable_returns_structured_refusal(self, tmp_path):
        agent = make_agent(tmp_path, stub("community", unanswerable=True))
        refusal = make_agent(tmp_path, stub("community", unanswerable=True)).answer(
            "what's the best chowder in Portland?")
        assert refusal["error"] == "unanswerable"
        # The classified intent rides along on the refusal so /ask logs the real label rather than
        # "unknown" — log-only, never routed on (the refusal is driven by unanswerable, not intent).
        assert refusal["intent"] == "calculate"
        assert agent.answer("off topic")["error"] == "unanswerable"

    def test_llm_timeout_becomes_structured_error(self, tmp_path):
        def boom(question):
            raise TimeoutError("llm timed out")
        payload = make_agent(tmp_path, boom).answer("q")
        assert payload["error"].startswith("llm_error")

    def test_cap_reached_blocks_before_spending(self, tmp_path):
        calls = []

        def counting(question):
            calls.append(question)
            return Extraction(option="community", inputs={})
        agent = make_agent(tmp_path, counting, cap=cost_usd(200_000, 0))
        agent.ledger.record(200_000, 0)  # lands exactly on the cap (inclusive ceiling)
        payload = agent.answer("q")
        assert payload["error"] == "cap_exceeded"
        assert calls == []  # the cap is a ceiling: no LLM call was attempted


class TestHttpSurface:
    def _client(self, tmp_path, extractor):
        from fastapi.testclient import TestClient
        import app as app_module
        app_module._agent = make_agent(tmp_path, extractor)
        return TestClient(app_module.app)

    def test_ask_returns_payload(self, tmp_path):
        client = self._client(tmp_path, stub("community", {"monthly_bill": 150}))
        res = client.post("/ask", json={"question": "community solar at $150?"})
        assert res.status_code == 200
        assert res.json()["result"]["annual_savings"] > 0

    def test_cap_exceeded_shape_over_http(self, tmp_path):
        client = self._client(tmp_path, stub("community"))
        import app as app_module
        app_module._agent.ledger.record(2_000_000, 0)  # $6 -> over the $5 default cap
        res = client.post("/ask", json={"question": "q"})
        assert res.status_code == 200
        assert res.json()["error"] == "cap_exceeded"

    def test_missing_key_startup_error_names_the_fix(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        # Point .env loading at a nonexistent file so no key can slip in from the repo-root .env —
        # the test's premise is "no key available anywhere".
        env["SOLAR_AGENT_ENV_FILE"] = os.path.join(SERVICE_DIR, "does-not-exist.env")
        res = subprocess.run(
            [sys.executable, os.path.join(SERVICE_DIR, "app.py")],
            capture_output=True, text=True, timeout=60, env=env,
        )
        assert res.returncode == 1
        assert "ANTHROPIC_API_KEY" in res.stderr


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
