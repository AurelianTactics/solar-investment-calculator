"""LangGraph agent: natural-language question -> routed, computed, structured answer.

The graph is deliberately small (the 2026 LangGraph idiom for one routing step):

    extract (one claude-opus-4-8 structured-output call) -> compute (pure src/ imports)

The LLM does ONLY routing + numeric extraction — it never does arithmetic. The compute node
calls the Python calculation core directly and reuses the CLI's ``--json`` renderers, so
agent-path numbers come from the source of truth by construction and the payload shape is
identical to ``python src/cli.py ... --json``. Extracted values are applied via
``with_user_value()`` so they arrive tagged ``user-provided`` (extraction is not a source).

Testable seam: ``Agent(extractor=...)`` — tests inject a fake extractor; only the default
extractor touches the network (and records its token usage in the spend ledger).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Callable, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import solar_calc  # noqa: E402
from cli import CAPITAL_OPTIONS, capital_spec, render_capital_json, render_community_json  # noqa: E402
from assumptions import default_assumptions  # noqa: E402

MODEL = "claude-opus-4-8"

OPTION_KEYS = ("community", "balcony", "rooftop", "battery", "plugin-battery",
               "battery+rooftop", "battery+balcony")

# R5: the missing input that would most tighten each option's estimate.
FOLLOWUP = {
    "community": "your annual kWh usage (from your bill's usage history)",
    "balcony": "the share of the kit's output you'd self-consume in real time",
    "rooftop": "your real annual kWh usage and a competing installer quote ($/W)",
    "battery": "what backup power through an outage is worth to you per year",
    "plugin-battery": "your on-peak share (weekday 5-9 p.m. fraction of your usage, from your "
                      "utility's hourly download) — it decides which TOU case you're in",
    "battery+rooftop": "your annual kWh usage and a real installer quote ($/W)",
    "battery+balcony": "your daytime self-consumption share and an electrician quote",
}


class Extraction(BaseModel):
    """What the routing call must produce — options picked, numbers extracted, or a refusal."""

    option: Literal[
        "community", "balcony", "rooftop", "battery", "plugin-battery",
        "battery+rooftop", "battery+balcony"
    ] = Field(description="Which solar option (or battery+PV pairing) the question is about.")
    inputs: dict[str, float] = Field(
        default_factory=dict,
        description="Numeric values stated in the question, keyed by assumption key. "
        "monthly_bill for a community-solar bill; capacity_kw for PV size in kW; "
        "annual_usage_kwh for yearly usage; battery_usable_kwh for battery size. "
        "Only include numbers the user actually stated.",
    )
    unanswerable: bool = Field(
        default=False,
        description="True if the question is not about Maine residential solar savings.",
    )
    note: str = Field(default="", description="One short sentence on how you routed it.")


EXTRACT_PROMPT = """You route questions for a Maine residential solar savings calculator.
Pick the option the question is about and pull out any numbers the asker stated.
Options: community (subscription, zero capital), balcony (plug-in kit), rooftop (owned panels),
battery (installed home storage), plugin-battery (a plug-in / DIY battery arbitraging the
optional time-of-use rate), battery+rooftop, battery+balcony (pairings).
Do NOT compute anything — the calculator does the math. If the question is not about Maine
residential solar savings, set unanswerable=true.

Question: {question}"""


class AgentState(TypedDict, total=False):
    question: str
    extraction: Optional[Extraction]
    payload: Optional[dict]
    error: Optional[str]


def build_default_extractor(ledger) -> Callable[[str], Extraction]:
    """The live extractor: one structured-output call, its usage recorded in the ledger."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export your key (see service/README.md) "
            "before starting the agent service."
        )
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model=MODEL, timeout=30, max_retries=1)
    structured = llm.with_structured_output(Extraction, include_raw=True)

    def extract(question: str) -> Extraction:
        result = structured.invoke(EXTRACT_PROMPT.format(question=question))
        raw = result.get("raw")
        usage = getattr(raw, "usage_metadata", None) or {}
        ledger.record(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        if result.get("parsing_error") or result.get("parsed") is None:
            raise ValueError(f"extraction did not parse: {result.get('parsing_error')}")
        return result["parsed"]

    return extract


def _apply_inputs(assumptions: dict, inputs: dict) -> dict:
    """Apply extracted values onto assumption records, tolerating battery_-prefix mismatches.

    The extraction schema keys battery numbers as ``battery_usable_kwh`` (the combo namespacing),
    but the plain battery option uses bare keys — and vice versa a model may emit a bare key for
    a combo. Try the key, then its prefix-flipped twin. Anything still unmapped is RETURNED, not
    silently dropped — the caller surfaces it so the answer never claims an input it didn't use.
    """
    ignored: dict = {}
    for key, val in inputs.items():
        target = key
        if target not in assumptions:
            flipped = key[len("battery_"):] if key.startswith("battery_") else "battery_" + key
            target = flipped if flipped in assumptions else None
        if target is None:
            ignored[key] = val
        else:
            assumptions[target] = assumptions[target].with_user_value(val)
    return ignored


def compute_payload(extraction: Extraction) -> tuple[dict, dict]:
    """Run the Python core for the routed option.

    Returns ``(payload, ignored_inputs)`` — the CLI --json payload shape, plus any extracted
    inputs that mapped to no assumption of the routed option (surfaced for honesty).
    """
    inputs = dict(extraction.inputs)
    if extraction.option == "community":
        a = default_assumptions()
        bill = inputs.pop("monthly_bill", None)
        if bill is not None:
            a["default_monthly_bill"] = a["default_monthly_bill"].with_user_value(bill)
        else:
            bill = a["default_monthly_bill"].value
        annual_usage = inputs.pop("annual_usage_kwh", None)
        ignored = _apply_inputs(a, inputs)  # any other extracted community assumption
        result = solar_calc.compute(
            monthly_bill=bill,
            price_per_kwh=a["price_per_kwh"].value,
            bill_offset_fraction=a["bill_offset_fraction"].value,
            subscription_discount_pct=a["subscription_discount_pct"].value,
            allocation_pct=a["allocation_pct"].value,
            annual_usage_kwh=annual_usage,
        )
        return json.loads(render_community_json(bill, a, result)), ignored

    module, merged = capital_spec(extraction.option)
    ignored = _apply_inputs(merged, inputs)
    result = module.compute_from_assumptions(merged)
    shown = CAPITAL_OPTIONS[extraction.option]["shown"]
    return json.loads(render_capital_json(extraction.option, merged, result, shown)), ignored


class Agent:
    """route + extract + compute, wired as a (small) LangGraph StateGraph."""

    def __init__(self, extractor: Optional[Callable[[str], Extraction]] = None, ledger=None):
        if ledger is None:
            from spend import SpendLedger

            ledger = SpendLedger.from_env()
        self.ledger = ledger
        self.extractor = extractor  # None -> built lazily so tests never need a key
        self._graph = self._build_graph()

    def _build_graph(self):
        from langgraph.graph import END, START, StateGraph

        def extract_node(state: AgentState) -> AgentState:
            if self.extractor is None:
                self.extractor = build_default_extractor(self.ledger)
            try:
                return {"extraction": self.extractor(state["question"])}
            except Exception as e:  # timeout, parse failure, API error -> structured fallback
                return {"error": f"llm_error: {e}"}

        def compute_node(state: AgentState) -> AgentState:
            ex = state.get("extraction")
            if state.get("error") or ex is None:
                return {}
            if ex.unanswerable:
                return {"error": "unanswerable"}
            try:
                payload, ignored = compute_payload(ex)
            except (ValueError, KeyError) as e:
                return {"error": f"compute_error: {e}"}
            payload["agent"] = {
                "model": MODEL,
                "extracted": ex.inputs,
                "ignored_inputs": ignored,  # extracted but unmappable — never silently dropped
                "option": ex.option,
                "note": ex.note,
            }
            payload["followup"] = (
                "The input that would most tighten this estimate: " + FOLLOWUP[ex.option] + "."
            )
            return {"payload": payload}

        g = StateGraph(AgentState)
        g.add_node("extract", extract_node)
        g.add_node("compute", compute_node)
        g.add_edge(START, "extract")
        g.add_edge("extract", "compute")
        g.add_edge("compute", END)
        return g.compile()

    def answer(self, question: str) -> dict:
        """Returns the CLI-shaped payload, or {"error": ...} the frontend can fall back on."""
        if self.ledger.over_cap:
            return {"error": "cap_exceeded",
                    "detail": f"agent spend cap reached (${self.ledger.cap_usd:.2f})"}
        state = self._graph.invoke({"question": question})
        if state.get("error"):
            return {"error": state["error"]}
        return state["payload"]
