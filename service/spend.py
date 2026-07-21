"""Spending ledger for the agent service — the cap is a ceiling, not a target.

Cost accumulates from per-response ``usage`` token counts (input/output tokens x the model's
per-MTok prices) into a gitignored JSON file, so the cap survives process restarts. The cap is
checked BEFORE each LLM call: once the recorded total reaches it, the service answers
``cap_exceeded`` instead of spending more.

**The window is one UTC day, not forever.** A cumulative total is right for a dev machine — it's a
lifetime budget you notice and reset by hand. Public, it isn't a cap, it's a fuse: the service
works until it has spent $cap *ever*, then serves ``cap_exceeded`` permanently until a human
deletes a file. The stored day is compared against today on every read, and a total from any other
day counts as 0. So the guarantee the deploy actually makes is **$cap per day**, and it recovers
on its own.

Failure posture is unchanged and deliberate: a corrupt ledger fails CLOSED (treated as over cap),
because the alternative — an unreadable file becoming free money — is the expensive direction to be
wrong in. That's easy to lose in a refactor; the tests pin it.

Configuration (env vars, all optional):
  SOLAR_AGENT_SPEND_CAP_USD   cap in dollars PER DAY (default 5.0)
  SOLAR_AGENT_LEDGER_PATH     ledger file (default service/.spend.json). On Railway point this at
                              an attached volume (/data/.spend.json) — the container filesystem is
                              ephemeral, so otherwise every redeploy silently resets the day.
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass

# claude-opus-4-8 pricing (USD per million tokens) — from the Claude API reference.
PRICE_PER_MTOK = {"input": 5.0, "output": 25.0}

DEFAULT_CAP_USD = 5.0
DEFAULT_LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".spend.json")


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_PER_MTOK["input"]
            + output_tokens * PRICE_PER_MTOK["output"]) / 1_000_000


@dataclass
class SpendLedger:
    path: str = DEFAULT_LEDGER_PATH
    cap_usd: float = DEFAULT_CAP_USD

    @classmethod
    def from_env(cls) -> "SpendLedger":
        return cls(
            path=os.environ.get("SOLAR_AGENT_LEDGER_PATH", DEFAULT_LEDGER_PATH),
            cap_usd=float(os.environ.get("SOLAR_AGENT_SPEND_CAP_USD", DEFAULT_CAP_USD)),
        )

    @staticmethod
    def today() -> str:
        """The current window. UTC so the window doesn't shift under the deploy's timezone."""
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    def _read(self) -> dict:
        """Today's spend. A total recorded on any other day is a new window, so it reads as 0."""
        today = self.today()
        if not os.path.exists(self.path):
            return {"day": today, "total_usd": 0.0, "calls": 0}
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            # Parse BEFORE deciding the window. A stale day is not a licence to skip validation:
            # if the file is garbage we must fail closed regardless of what day it claims, or
            # "unreadable" quietly becomes "fresh budget" for anything not dated today.
            total = float(data.get("total_usd", 0.0))
            calls = int(data.get("calls", 0))
            if str(data.get("day", "")) != today:
                # Yesterday's spend (or a pre-daily-window file with no "day" at all) — the window
                # rolled. Keeping the old numbers here is what turned the cap into a fuse.
                return {"day": today, "total_usd": 0.0, "calls": 0}
            return {"day": today, "total_usd": total, "calls": calls}
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            # A corrupt ledger fails CLOSED: treat it as over-cap rather than free money.
            return {"day": today, "total_usd": float("inf"), "calls": 0}

    @property
    def total_usd(self) -> float:
        """Spend so far TODAY — not since the file was created."""
        return self._read()["total_usd"]

    @property
    def over_cap(self) -> bool:
        return self.total_usd >= self.cap_usd

    def record(self, input_tokens: int, output_tokens: int) -> float:
        """Add one response's cost; returns today's new total. Persists immediately."""
        data = self._read()
        if data["total_usd"] == float("inf"):
            raise RuntimeError(f"spend ledger unreadable: {self.path} — fix or delete it")
        data["total_usd"] += cost_usd(input_tokens, output_tokens)
        data["calls"] += 1
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return data["total_usd"]
