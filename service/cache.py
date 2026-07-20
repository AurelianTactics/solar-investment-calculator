"""Extraction cache — the middle of three layers that keep the model out of the loop.

The page itself answers questions it wrote (elision, ``web/app.js``) and comparison questions
(``parseQuestionLocally``). This layer catches the rest: a question the page did NOT write costs
one LLM call the first time it is asked, by anyone, and nothing thereafter.

**Why caching an ``Extraction`` is safe.** It is a pure function of the question text — routing
plus number extraction, explicitly not arithmetic. The computation is re-run fresh from ``src/``
on every request regardless, so a hit can never serve a stale *number*, only a stale *routing*.

**Why routing still expires.** "The routing for a fixed string doesn't change" holds only while
the routing target set is fixed, and it isn't — combos landed in July and ``docs/BACKLOG.md``
lists more options. So every entry is qualified by a ``version`` tag derived from the model, the
option keys, and the routing prompt (see ``agent.cache_version``). A version mismatch is a miss
for every entry, so adding an option or editing the prompt transparently invalidates the file
rather than routing to the old option set forever with no signal.

Storage is the same JSON-file pattern as ``SpendLedger``, but with the opposite failure posture:
the ledger fails CLOSED (a corrupt ledger must not become free money), while a cache fails SOFT —
unreadable, corrupt or stale means MISS, never an error. A cache that can break the service is
worse than no cache.

Configuration:
  SOLAR_AGENT_CACHE_PATH   cache file (default service/.extraction-cache.json)
"""

from __future__ import annotations

import hashlib
import json
import os
import re

DEFAULT_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".extraction-cache.json"
)

# A cache that grows without bound is a disk-space bug waiting for a deploy. Well past any real
# session, small enough to stay a single readable file.
MAX_ENTRIES = 2000


def normalize(question: str) -> str:
    """Fold the differences that don't change what a question means.

    Case, surrounding and internal whitespace, and terminal punctuation — so "Is a battery worth
    it?" and "is a battery worth it" are one entry. Nothing more aggressive than that: word order
    and phrasing DO change routing, so they must stay part of the key.
    """
    s = re.sub(r"\s+", " ", (question or "").strip().lower())
    return s.rstrip("?!. \t")


def key_for(question: str) -> str:
    return hashlib.sha256(normalize(question).encode("utf-8")).hexdigest()[:32]


class ExtractionCache:
    """normalized question -> serialized ``Extraction``, qualified by a routing version tag."""

    def __init__(self, path: str = DEFAULT_CACHE_PATH, version: str = "") -> None:
        self.path = path
        self.version = version

    @classmethod
    def from_env(cls, version: str) -> "ExtractionCache":
        return cls(path=os.environ.get("SOLAR_AGENT_CACHE_PATH", DEFAULT_CACHE_PATH),
                   version=version)

    def _read(self) -> dict:
        """The whole file, or ``{}`` for every failure mode. Never raises."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict) or data.get("version") != self.version:
                return {}          # stale routing target set / prompt / model -> miss everything
            entries = data.get("entries")
            return entries if isinstance(entries, dict) else {}
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return {}              # missing or corrupt: a miss, not a crash

    def get(self, question: str) -> dict | None:
        hit = self._read().get(key_for(question))
        return hit if isinstance(hit, dict) else None

    def put(self, question: str, extraction: dict) -> None:
        """Best-effort write. A failure here costs one future LLM call, so it is never fatal."""
        entries = self._read()
        entries[key_for(question)] = extraction
        if len(entries) > MAX_ENTRIES:                     # oldest-first: dicts keep insertion order
            entries = dict(list(entries.items())[-MAX_ENTRIES:])
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump({"version": self.version, "entries": entries}, fh, indent=2)
        except OSError:
            pass
