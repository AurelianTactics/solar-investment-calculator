"""Spending ledger for the agent service — the cap is a ceiling, not a target.

Cost accumulates from per-response ``usage`` token counts (input/output tokens x the model's
per-MTok prices) into a gitignored JSON file, so the cap survives process restarts. The cap is
checked BEFORE each LLM call: once the recorded total reaches it, the service answers
``cap_exceeded`` instead of spending more.

Configuration (env vars, all optional):
  SOLAR_AGENT_SPEND_CAP_USD   cap in dollars (default 5.0)
  SOLAR_AGENT_LEDGER_PATH     ledger file (default service/.spend.json)
"""

from __future__ import annotations

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

    def _read(self) -> dict:
        if not os.path.exists(self.path):
            return {"total_usd": 0.0, "calls": 0}
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            return {"total_usd": float(data.get("total_usd", 0.0)),
                    "calls": int(data.get("calls", 0))}
        except (json.JSONDecodeError, OSError, ValueError):
            # A corrupt ledger fails CLOSED: treat it as over-cap rather than free money.
            return {"total_usd": float("inf"), "calls": 0}

    @property
    def total_usd(self) -> float:
        return self._read()["total_usd"]

    @property
    def over_cap(self) -> bool:
        return self.total_usd >= self.cap_usd

    def record(self, input_tokens: int, output_tokens: int) -> float:
        """Add one response's cost; returns the new total. Persists immediately."""
        data = self._read()
        if data["total_usd"] == float("inf"):
            raise RuntimeError(f"spend ledger unreadable: {self.path} — fix or delete it")
        data["total_usd"] += cost_usd(input_tokens, output_tokens)
        data["calls"] += 1
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return data["total_usd"]
