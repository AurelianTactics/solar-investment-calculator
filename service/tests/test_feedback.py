"""The event log, and the promise that it yields before anything else on the disk does.

``/data`` is one volume shared with the spend ledger, and ``spend.py`` fails CLOSED — a ledger it
cannot write stops ``/ask`` answering. So the load-bearing property here is not "events are
recorded", it is **"the log gets out of the way first"**: at its byte ceiling, or with the volume
near full, it refuses to append and everything else keeps working. These tests pin that, plus the
refuse-never-evict decision that makes retention-forever safe.

Run with: pytest service/tests
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from feedback import FeedbackLog  # noqa: E402


@pytest.fixture
def log(tmp_path):
    return FeedbackLog(path=str(tmp_path / "feedback.jsonl"))


def read_lines(log: FeedbackLog) -> list[dict]:
    with open(log.path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class TestAppend:
    def test_one_object_per_line_with_ts_and_kind(self, log):
        assert log.append("request", path="/", status=200) is True
        assert log.append("ask", question="what about rooftop?") is True

        lines = read_lines(log)
        assert [line["kind"] for line in lines] == ["request", "ask"]
        assert lines[0]["path"] == "/" and lines[0]["status"] == 200
        assert lines[1]["question"] == "what about rooftop?"
        assert all(line["ts"] for line in lines)

    def test_heterogeneous_kinds_share_one_stream(self, log):
        for kind in ("request", "ask", "assumption_edited", "feedback", "mcp_tool_call"):
            log.append(kind)
        assert [line["kind"] for line in read_lines(log)] == [
            "request", "ask", "assumption_edited", "feedback", "mcp_tool_call"]

    def test_text_is_stored_verbatim(self, log):
        """R6: storing what was typed, as typed, is what makes the log worth reading."""
        typed = 'The $2.95/W is way off — I was quoted "3.60" for an 8kW system in Bangor.\n'
        log.append("feedback", text=typed)
        assert read_lines(log)[0]["text"] == typed

    def test_unserializable_field_does_not_raise(self, log):
        assert log.append("request", weird=object()) is True
        assert read_lines(log)[0]["kind"] == "request"

    def test_unwritable_path_is_soft(self, tmp_path):
        """A telemetry write that raised would take down the answer it only meant to describe."""
        blocked = tmp_path / "afile"
        blocked.write_text("not a directory")
        broken = FeedbackLog(path=str(blocked / "nested" / "feedback.jsonl"))
        assert broken.append("request") is False       # False, not an exception


class TestYieldsFirst:
    def test_refuses_at_byte_ceiling(self, tmp_path):
        log = FeedbackLog(path=str(tmp_path / "feedback.jsonl"), max_bytes=200)
        while log.append("request", path="/some/path"):
            pass
        assert log.size_bytes() >= 200
        assert log.refusal() == "log_full"
        assert log.append("request") is False

    def test_refuses_when_free_space_is_low(self, tmp_path, monkeypatch):
        log = FeedbackLog(path=str(tmp_path / "feedback.jsonl"),
                          min_free_bytes=10 * 1024 * 1024 * 1024 * 1024)   # 10 TB: unreachable
        assert log.refusal() == "disk_low"
        assert log.append("request") is False

    def test_disk_check_ignores_what_filled_the_disk(self, tmp_path):
        """The free-space floor is the check that matters: an empty log still refuses when the
        volume is full, because the culprit may be the cache, the ledger, or a stray file."""
        log = FeedbackLog(path=str(tmp_path / "feedback.jsonl"),
                          min_free_bytes=10 * 1024 * 1024 * 1024 * 1024)
        assert log.size_bytes() == 0                # nothing WE wrote
        assert log.append("request") is False       # ...and it still steps aside

    def test_unknown_free_space_does_not_disable_logging(self, tmp_path, monkeypatch):
        """Unknown must not mean refuse, or a platform quirk silently kills instrumentation."""
        import feedback as feedback_module

        log = FeedbackLog(path=str(tmp_path / "feedback.jsonl"))
        monkeypatch.setattr(feedback_module.shutil, "disk_usage",
                            lambda _p: (_ for _ in ()).throw(OSError("no such thing")))
        assert log.free_bytes() is None
        assert log.append("request") is True

    def test_refuses_rather_than_evicting(self, tmp_path):
        """R3: retention is forever, so evicting to make room would delete the earliest and most
        interesting events on behalf of whoever is currently flooding us."""
        log = FeedbackLog(path=str(tmp_path / "feedback.jsonl"), max_bytes=300)
        log.append("feedback", text="the first thing anyone ever told us")
        while log.append("request", path="/noise"):
            pass
        first = read_lines(log)[0]
        assert first["kind"] == "feedback"
        assert first["text"] == "the first thing anyone ever told us"


class TestStatus:
    def test_status_reports_size_against_ceiling(self, tmp_path):
        log = FeedbackLog(path=str(tmp_path / "feedback.jsonl"), max_bytes=1000)
        log.append("request", path="/")
        status = log.status()
        assert status["accepting"] is True
        assert status["refusing_because"] is None
        assert 0 < status["pct_of_ceiling"] < 100
        assert status["max_bytes"] == 1000

    def test_status_says_why_it_is_refusing(self, tmp_path):
        """"The log is full" should be visible on /health, not discovered from missing events."""
        log = FeedbackLog(path=str(tmp_path / "feedback.jsonl"), max_bytes=50)
        while log.append("request", path="/some/path"):
            pass
        status = log.status()
        assert status["accepting"] is False
        assert status["refusing_because"] == "log_full"
        assert status["pct_of_ceiling"] >= 100


class TestConfiguration:
    def test_from_env_overrides_every_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SOLAR_FEEDBACK_PATH", str(tmp_path / "custom.jsonl"))
        monkeypatch.setenv("SOLAR_FEEDBACK_MAX_BYTES", "123")
        monkeypatch.setenv("SOLAR_FEEDBACK_MIN_FREE_BYTES", "456")
        log = FeedbackLog.from_env()
        assert log.path.endswith("custom.jsonl")
        assert (log.max_bytes, log.min_free_bytes) == (123, 456)

    def test_default_path_is_beside_the_other_service_state(self):
        monkeypatched = os.environ.pop("SOLAR_FEEDBACK_PATH", None)
        try:
            assert FeedbackLog.from_env().path.endswith(".feedback.jsonl")
        finally:
            if monkeypatched is not None:
                os.environ["SOLAR_FEEDBACK_PATH"] = monkeypatched
