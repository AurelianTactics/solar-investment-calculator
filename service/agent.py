"""LangGraph agent: natural-language question -> routed, computed, structured answer.

The graph is deliberately small (the 2026 LangGraph idiom for one routing step):

    extract (one claude-sonnet-5 structured-output call) -> compute (pure src/ imports)

The LLM does ONLY routing + numeric extraction — it never does arithmetic. The compute node
calls the Python calculation core directly and reuses the CLI's ``--json`` renderers, so
agent-path numbers come from the source of truth by construction and the payload shape is
identical to ``python src/cli.py ... --json``. Extracted values are applied via
``with_user_value()`` so they arrive tagged ``user-provided`` (extraction is not a source).

Before the extract step runs, the question is looked up in an ``ExtractionCache`` (see
``cache.py``): routing is a pure function of the question text, so a repeat of any question —
from any visitor — costs nothing. Refusals are cached too, or "what's the weather" would buy a
call every time it is asked.

The same call also labels the question's ``intent`` (calculate / feedback / out_of_scope) for a
handful of extra output tokens. **That label is recorded and never routed on.** It turns the
question box that already exists into a labeled feedback channel with no new UI — but if the
classifier called a real question "feedback" and the page stopped calculating, we would have broken
the product to serve telemetry. Log-only in v1; read a month of classifications before letting it
influence anything. When the model is unreachable or the cap has tripped there is no label at all,
and the caller records the raw text with ``intent: "unknown"`` — the text is the asset, the label
is derivable offline whenever we want it.

Testable seam: ``Agent(extractor=...)`` — tests inject a fake extractor; only the default
extractor touches the network (and records its token usage in the spend ledger).
"""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Callable, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import tools_core  # noqa: E402  (the shared payload builder — see its module docstring)

MODEL = "claude-sonnet-5"

OPTION_KEYS = ("community", "balcony", "rooftop", "battery", "plugin-battery",
               "battery+rooftop", "battery+balcony")

# R5: the missing input that would most tighten each option's estimate.
FOLLOWUP = {
    "community": "your annual kWh usage (from your bill's usage history)",
    "balcony": "the share of the kit's output you'd self-consume in real time",
    "rooftop": "your real annual kWh usage and a competing installer quote ($/W)",
    "battery": "what backup power through an outage is worth to you per year",
    "plugin-battery": "your on-peak share (weekday 5-9 p.m. fraction of your usage, from your "
                      "utility's hourly download) — it decides whether this option applies to "
                      "you at all",
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
    intent: Literal["calculate", "feedback", "out_of_scope"] = Field(
        default="calculate",
        description="What the person is doing: 'calculate' = asking for an estimate; "
        "'feedback' = telling us something is wrong, missing, or confusing; "
        "'out_of_scope' = asking for something this calculator does not model.",
    )
    note: str = Field(default="", description="One short sentence on how you routed it.")


EXTRACT_PROMPT = """You route questions for a Maine residential solar savings calculator.
Pick the option the question is about and pull out any numbers the asker stated.
Options: community (subscription, zero capital), balcony (plug-in kit), rooftop (owned panels),
battery (installed home storage), plugin-battery (a plug-in / DIY battery arbitraging the
optional time-of-use rate), battery+rooftop, battery+balcony (pairings).
Do NOT compute anything — the calculator does the math. If the question is not about Maine
residential solar savings, set unanswerable=true.

Also label what the person is doing, in `intent`: "calculate" if they want an estimate,
"feedback" if they are telling us something is wrong, stale, missing or confusing, "out_of_scope"
if they want something this calculator does not model (heat pumps, EVs, another state). The label
is recorded and never changes the answer, so when in doubt use "calculate".

Question: {question}"""


def cache_version() -> str:
    """What a cached routing decision is only valid FOR.

    A cached ``Extraction`` stays correct exactly as long as the thing that produced it does. All
    three of those inputs are here: change the model, add an option key, or edit the routing
    prompt, and every existing entry becomes a miss rather than silently routing to yesterday's
    option set.
    """
    material = "|".join((MODEL, ",".join(OPTION_KEYS), EXTRACT_PROMPT))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


class AgentState(TypedDict, total=False):
    question: str
    extraction: Optional[Extraction]
    payload: Optional[dict]
    error: Optional[str]
    cached: bool


def build_default_extractor(ledger) -> Callable[[str], Extraction]:
    """The live extractor: one structured-output call, its usage recorded in the ledger."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export your key (see service/README.md) "
            "before starting the agent service."
        )
    from langchain_anthropic import ChatAnthropic

    # thinking off: Sonnet 5 runs adaptive thinking by default (Opus 4.8 did not), and this call
    # only routes + extracts — the src/ core does every calculation, so reasoning tokens here are
    # pure latency and cost with nothing to reason about.
    llm = ChatAnthropic(
        model=MODEL, timeout=30, max_retries=1, thinking={"type": "disabled"}
    )
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


def compute_payload(extraction: Extraction) -> tuple[dict, dict]:
    """Run the Python core for the routed option.

    A thin adapter over ``tools_core.calculate`` — the one payload builder, shared with the MCP
    server. The routing decision is this module's job; producing the answer is not. Routing through
    ``tools_core`` is also what applies the input clamp to ``/ask``: ``Extraction.inputs`` is an
    open ``dict[str, float]``, so an LLM (or a prompt-injected question) could otherwise hand
    ``horizon_years: 1e9`` straight to the capital engine.

    Returns ``(payload, ignored_inputs)`` — the CLI --json payload shape, plus any extracted
    inputs that mapped to no assumption of the routed option (surfaced for honesty).
    """
    return tools_core.calculate(extraction.option, extraction.inputs)


class Agent:
    """route + extract + compute, wired as a (small) LangGraph StateGraph."""

    def __init__(self, extractor: Optional[Callable[[str], Extraction]] = None, ledger=None,
                 cache=None):
        if ledger is None:
            from spend import SpendLedger

            ledger = SpendLedger.from_env()
        if cache is None:
            from cache import ExtractionCache

            cache = ExtractionCache.from_env(cache_version())
        self.ledger = ledger
        self.cache = cache
        self.extractor = extractor  # None -> built lazily so tests never need a key
        self._graph = self._build_graph()

    def _build_graph(self):
        from langgraph.graph import END, START, StateGraph

        def extract_node(state: AgentState) -> AgentState:
            question = state["question"]
            cached = self.cache.get(question)
            if cached is not None:
                try:
                    return {"extraction": Extraction(**cached), "cached": True}
                except Exception:
                    pass  # an entry written by an older schema is a miss, never an error
            if self.extractor is None:
                self.extractor = build_default_extractor(self.ledger)
            try:
                extraction = self.extractor(question)
            except Exception as e:  # timeout, parse failure, API error -> structured fallback
                return {"error": f"llm_error: {e}"}
            # Cache AFTER a successful parse, refusals included: an unanswerable question asked
            # twice should cost one call, not two.
            self.cache.put(question, extraction.model_dump())
            return {"extraction": extraction}

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
                # Recorded by the caller, never acted on here — see the module docstring.
                "intent": ex.intent,
                "cached": bool(state.get("cached")),
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
        # The cap exists to bound SPEND, and a cached question spends nothing — so it is still
        # answered over the cap. The check stays before the graph for everything else.
        if self.ledger.over_cap and self.cache.get(question) is None:
            return {"error": "cap_exceeded",
                    "detail": f"agent spend cap reached (${self.ledger.cap_usd:.2f})"}
        state = self._graph.invoke({"question": question})
        if state.get("error"):
            out = {"error": state["error"]}
            ex = state.get("extraction")
            if ex is not None:
                # The intent classification survives even when the question can't be answered — an
                # unanswerable question was still routed AND labeled (usually out_of_scope), which
                # is exactly the label the feedback loop wants. Surface it so /ask logs the real
                # label rather than "unknown". Still log-only, never routed on: the unanswerable
                # decision is ex.unanswerable, not ex.intent, so this adds no routing dependency.
                out["intent"] = ex.intent
            return out
        return state["payload"]
