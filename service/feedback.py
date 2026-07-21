"""Append-only event log — the whole storage story for instrumentation.

One file, one JSON object per line, heterogeneous ``kind``. Request logs, MCP tool calls,
questions, client events, thumbs and free text all land in the same stream. There is no database
and no schema: the event shape will change several times in the first month, and migrations on POC
telemetry are pure friction. JSONL defers that decision until real events exist. Querying is not
given up — DuckDB reads the file directly::

    duckdb -c "select kind, count(*) from read_json_auto('.feedback.jsonl') group by 1 order by 2 desc"

**This module yields to everything else on the disk.** ``/data`` is one Railway volume shared with
``spend.py``, and the ledger fails CLOSED — a ledger it cannot write stops ``/ask`` answering.
Telemetry must never be what takes the agent down, and Railway allows one volume per service, so
isolation-by-separate-disk is not available. Yielding first is the substitute, in two checks before
every append:

  1. a **byte ceiling** on the log itself, which bounds what this file can ever cost;
  2. a **free-space floor** on the volume, which is the one that actually matters — it does not
     care *what* filled the disk, so if the extraction cache or a stray file is the culprit, the
     log still steps aside and leaves the last megabytes to the ledger.

**On hitting either limit it refuses; it never evicts.** This is a deliberate departure from
``cache.py``'s oldest-first eviction: a cache entry is disposable, an event is not. Retention here
is forever, so evicting to make room would silently delete the earliest and most interesting data
on behalf of whoever is currently flooding us. Refusing is loud (``/health`` reports the log's size
against its ceiling) and reversible.

Every failure mode is soft. ``append`` returns False and never raises — a telemetry write that
raised would take down the answer it was only supposed to describe.

Configuration (env vars, all optional):
  SOLAR_FEEDBACK_PATH        log file (default service/.feedback.jsonl). On Railway point this at
                             the attached volume (/data/.feedback.jsonl) — without it the
                             container filesystem is ephemeral and every event vanishes on deploy.
  SOLAR_FEEDBACK_MAX_BYTES   byte ceiling for the log (default 50 MB, ~1% of a 5 GB volume).
  SOLAR_FEEDBACK_MIN_FREE_BYTES  refuse to append below this much free space (default 200 MB).
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
from dataclasses import dataclass

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".feedback.jsonl")

# ~1% of a 5 GB volume. At the traffic this project realistically sees (tens of visitors a month,
# well under 1 MB/year) the ceiling exists for the abuse case, not the organic one.
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
# Room left for the spend ledger and the extraction cache to keep writing after the log stops.
DEFAULT_MIN_FREE_BYTES = 200 * 1024 * 1024


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


@dataclass
class FeedbackLog:
    path: str = DEFAULT_PATH
    max_bytes: int = DEFAULT_MAX_BYTES
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES

    @classmethod
    def from_env(cls) -> "FeedbackLog":
        return cls(
            path=os.environ.get("SOLAR_FEEDBACK_PATH", DEFAULT_PATH),
            max_bytes=int(os.environ.get("SOLAR_FEEDBACK_MAX_BYTES", DEFAULT_MAX_BYTES)),
            min_free_bytes=int(
                os.environ.get("SOLAR_FEEDBACK_MIN_FREE_BYTES", DEFAULT_MIN_FREE_BYTES)
            ),
        )

    def size_bytes(self) -> int:
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def free_bytes(self) -> int | None:
        """Free space on the log's volume, or None if it can't be determined.

        Unknown must not mean "refuse": a platform where ``disk_usage`` fails would silently
        disable all instrumentation. The byte ceiling still bounds the file in that case.
        """
        try:
            return shutil.disk_usage(os.path.dirname(os.path.abspath(self.path))).free
        except OSError:
            return None

    def refusal(self) -> str | None:
        """Why the next append would be refused, or None if it would be accepted."""
        if self.size_bytes() >= self.max_bytes:
            return "log_full"
        free = self.free_bytes()
        if free is not None and free < self.min_free_bytes:
            return "disk_low"
        return None

    def append(self, kind: str, **fields) -> bool:
        """Write one event. Returns whether it was written; never raises, for any reason.

        The caller is a request handler in every case, and no telemetry outcome — full log, full
        disk, unserializable field, read-only filesystem — is worth failing a user's request over.
        """
        try:
            if self.refusal() is not None:
                return False
            record = {"ts": utcnow(), "kind": kind}
            record.update(fields)
            line = json.dumps(record, ensure_ascii=False, default=str)
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            return True
        except Exception:
            return False

    def status(self) -> dict:
        """What ``/health`` reports, so "the log is 80% full" is visible rather than discovered."""
        size = self.size_bytes()
        return {
            "path": self.path,
            "bytes": size,
            "max_bytes": self.max_bytes,
            "pct_of_ceiling": round(100.0 * size / self.max_bytes, 2) if self.max_bytes else None,
            "free_bytes": self.free_bytes(),
            "accepting": self.refusal() is None,
            "refusing_because": self.refusal(),
        }
