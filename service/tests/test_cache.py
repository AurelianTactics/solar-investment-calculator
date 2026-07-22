"""Extraction-cache tests — hit, miss, negative cache, invalidation, and failing soft.

The LLM is stubbed as always; here the stub does double duty as a call COUNTER, which is the
only way to assert the point of the cache: that the second identical question does not reach it.

Run with: pytest service/tests
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from agent import Agent, Extraction, cache_version  # noqa: E402
from cache import ExtractionCache, normalize  # noqa: E402
from spend import SpendLedger, cost_usd  # noqa: E402


class Counting:
    """A stub extractor that records every question it was actually asked."""

    def __init__(self, option="community", inputs=None, unanswerable=False):
        self.calls = []
        self._ex = Extraction(option=option, inputs=inputs or {},
                              unanswerable=unanswerable, note="stub")

    def __call__(self, question):
        self.calls.append(question)
        return self._ex


def make_agent(tmp_path, extractor, cap=5.0, version=None):
    return Agent(
        extractor=extractor,
        ledger=SpendLedger(path=str(tmp_path / "spend.json"), cap_usd=cap),
        cache=ExtractionCache(path=str(tmp_path / "cache.json"),
                              version=cache_version() if version is None else version),
    )


class TestNormalization:
    def test_folds_case_whitespace_and_terminal_punctuation(self):
        assert normalize("  Is a  BATTERY worth it? ") == "is a battery worth it"
        assert normalize("Is a battery worth it") == normalize("is a  battery worth it?!")

    def test_keeps_differences_that_change_routing(self):
        # Word order and content are the routing signal — normalization must not erase them.
        assert normalize("rooftop vs battery") != normalize("battery vs rooftop")
        assert normalize("rooftop solar") != normalize("balcony solar")


class TestCacheHitAndMiss:
    def test_repeat_question_costs_no_llm_call(self, tmp_path):
        ex = Counting("rooftop", {"capacity_kw": 8})
        agent = make_agent(tmp_path, ex)
        first = agent.answer("What about an 8 kW roof?")
        second = agent.answer("what about an 8 kW roof")   # same question, normalized
        assert len(ex.calls) == 1                          # the whole point
        assert first["option"] == second["option"] == "rooftop"
        assert first["result"] == second["result"]

    def test_a_different_question_still_calls_the_model(self, tmp_path):
        ex = Counting()
        agent = make_agent(tmp_path, ex)
        agent.answer("community solar at $150?")
        agent.answer("is a home battery worth it?")
        assert len(ex.calls) == 2

    def test_cache_survives_a_new_agent_process(self, tmp_path):
        # The file is the point: a repeat from ANY visitor, after a restart, is still free.
        first = Counting()
        make_agent(tmp_path, first).answer("community solar at $150?")
        second = Counting()
        payload = make_agent(tmp_path, second).answer("Community solar at $150?")
        assert second.calls == []
        assert payload["option"] == "community"

    def test_numbers_are_recomputed_not_replayed(self, tmp_path):
        # A hit restores ROUTING only; the arithmetic re-runs from src/ every time, which is what
        # makes caching safe. Same extraction in, same freshly computed payload out.
        ex = Counting("community", {"monthly_bill": 150})
        agent = make_agent(tmp_path, ex)
        live = agent.answer("q about community solar")
        cached = agent.answer("q about community solar")
        assert cached["result"]["annual_savings"] == live["result"]["annual_savings"]
        assert cached["steps"] == live["steps"]


class TestNegativeCaching:
    def test_refusal_is_cached_too(self, tmp_path):
        # Otherwise "what's the weather" buys a model call every single time it is asked.
        ex = Counting(unanswerable=True)
        agent = make_agent(tmp_path, ex)
        assert agent.answer("what's the best chowder in Portland?")["error"] == "unanswerable"
        assert agent.answer("What's the best chowder in Portland?")["error"] == "unanswerable"
        assert len(ex.calls) == 1


class TestInvalidation:
    def test_version_change_invalidates_every_entry(self, tmp_path):
        # Adding an option / editing the routing prompt / changing the model must not leave every
        # cached question routing to the old target set forever with no signal.
        first = Counting()
        make_agent(tmp_path, first, version="v1").answer("community solar at $150?")
        second = Counting()
        make_agent(tmp_path, second, version="v2").answer("community solar at $150?")
        assert len(second.calls) == 1

    def test_version_tag_tracks_the_option_keys(self):
        import agent as agent_module

        before = cache_version()
        original = agent_module.OPTION_KEYS
        try:
            agent_module.OPTION_KEYS = original + ("hypothetical-7th-option",)
            assert cache_version() != before
        finally:
            agent_module.OPTION_KEYS = original
        assert cache_version() == before


class TestFailsSoft:
    def test_corrupt_cache_file_misses_rather_than_crashing(self, tmp_path):
        # The ledger fails CLOSED (corrupt = over cap); a cache must fail SOFT (corrupt = miss).
        path = tmp_path / "cache.json"
        path.write_text("{not json at all", encoding="utf-8")
        ex = Counting()
        payload = make_agent(tmp_path, ex).answer("community solar at $150?")
        assert payload["option"] == "community"
        assert len(ex.calls) == 1
        assert json.loads(path.read_text(encoding="utf-8"))["entries"]  # and it healed itself

    def test_entry_from_an_older_schema_is_a_miss(self, tmp_path):
        path = tmp_path / "cache.json"
        cache = ExtractionCache(path=str(path), version=cache_version())
        cache.put("community solar at $150?", {"option": "no-such-option", "note": "stale"})
        ex = Counting()
        payload = make_agent(tmp_path, ex).answer("community solar at $150?")
        assert payload["option"] == "community"
        assert len(ex.calls) == 1

    def test_missing_file_is_just_a_miss(self, tmp_path):
        cache = ExtractionCache(path=str(tmp_path / "nope" / "cache.json"), version="v")
        assert cache.get("anything") is None


class TestCacheAndTheSpendCap:
    def test_cached_question_is_answered_over_the_cap(self, tmp_path):
        # The cap bounds SPEND. A cached question spends nothing, so blocking it would deny a free
        # answer for no benefit.
        ex = Counting()
        agent = make_agent(tmp_path, ex, cap=cost_usd(200_000, 0))
        agent.answer("community solar at $150?")
        agent.ledger.record(200_000, 0)          # lands exactly on the cap (inclusive ceiling)
        payload = agent.answer("community solar at $150?")
        assert payload.get("error") != "cap_exceeded"
        assert payload["option"] == "community"
        assert len(ex.calls) == 1

    def test_uncached_question_is_still_blocked_at_the_cap(self, tmp_path):
        ex = Counting()
        agent = make_agent(tmp_path, ex, cap=cost_usd(200_000, 0))
        agent.ledger.record(200_000, 0)  # lands exactly on the cap (inclusive ceiling)
        assert agent.answer("a question never asked before")["error"] == "cap_exceeded"
        assert ex.calls == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
