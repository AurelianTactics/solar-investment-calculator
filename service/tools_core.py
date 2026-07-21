"""The calculator as callable tools — one definition, three callers.

This module is the single place where "run the calculator and hand back the CLI ``--json`` payload"
is implemented. Three surfaces call it:

  * ``POST /ask``      — via ``agent.compute_payload`` (an LLM routes; this computes)
  * the MCP server     — via ``mcp_server.py``, with **no** LLM anywhere on the path
  * the tests          — asserting these payloads equal ``python src/cli.py ... --json``

A second payload builder alongside the first is precisely the drift this repo's parity machinery
exists to prevent, so ``calculate()`` below **is** the old ``agent.compute_payload`` body, moved
rather than copied. ``agent.py`` imports it back.

Stdlib-only by construction (it wraps ``src/``); the MCP and FastAPI layers above it own their
dependencies.

**The input clamp lives here, and that is the point.** ``inputs`` is the ``--set`` mechanism, so an
untrusted caller can set any assumption — including ones that drive loops. ``capital.compare()``
builds one ``YearRow`` per year with no ceiling on ``horizon_years``, so
``{"horizon_years": 1e9}`` is a single-request memory blowup that a *rate* limit cannot stop:
bounding request frequency does nothing about one bad request. Bounding the input does. Because
both the public MCP server and ``/ask`` route through here, both inherit the bound — which is what
makes exposing this publicly with no auth an honest claim rather than an optimistic one.

Out-of-range values are **rejected, not silently clamped**: an agent must never receive an answer
to a question it didn't ask.
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import solar_calc  # noqa: E402
from assumptions import default_assumptions  # noqa: E402
from cli import (  # noqa: E402
    ALL_OPTION_KEYS,
    CAPITAL_OPTIONS,
    asm_dict,
    capital_payload,
    capital_spec,
    render_community_json,
)

# --- the clamp (R20) -------------------------------------------------------

# Every year of horizon materializes a YearRow. 100 is far past any real analysis (the longest
# shipped default is rooftop's 25) and far short of anything that hurts.
MAX_HORIZON_YEARS = 100
LOOP_DRIVING_KEYS = ("horizon_years", "battery_horizon_years")

OPTIONS_NEEDING_BILL = ("community",)

# Short, agent-facing descriptions. The web page's blurbs (web/app.js) are longer prose aimed at a
# homeowner reading them; these are aimed at a model choosing between options.
BLURBS = {
    "community": "Subscribe to a shared solar farm. Zero capital, a percentage off the bill; no "
                 "payback or NPV because nothing is invested.",
    "balcony": "A small plug-in panel kit. Low upfront cost, savings limited to what you consume "
               "in real time.",
    "rooftop": "Owned rooftop panels. The full capital case: install cost, generation, net-energy "
               "billing credits, payback and NPV against investing the same cash.",
    "battery": "Installed home storage. Backup value plus optional time-of-use arbitrage; the "
               "hardware rarely pays for itself on economics alone.",
    "plugin-battery": "A buy-and-plug or DIY battery arbitraging CMP's optional time-of-use rate. "
                      "Models only homes already under the 15.8% on-peak line (see "
                      "docs/BACKLOG.md); over it, calculate() returns an error explaining why.",
    "battery+rooftop": "Rooftop solar and an installed battery together, as additive cashflow "
                       "streams with their own horizons.",
    "battery+balcony": "A balcony kit and an installed battery together, as additive cashflow "
                       "streams with their own horizons.",
}


class ToolError(ValueError):
    """A caller-fixable problem: unknown option, out-of-range input, an option that can't answer.

    A ``ValueError`` so ``agent.compute_node`` already catches it into ``compute_error: …``.
    """


def check_inputs(inputs: dict) -> dict:
    """Validate an override dict before any of it reaches ``src/``. Returns it unchanged.

    Rejects rather than clamps, and rejects NaN/inf everywhere (they propagate silently through
    float arithmetic and come back out as ``null`` in JSON, which is worse than an error).
    """
    for key, val in (inputs or {}).items():
        try:
            val = float(val)
        except (TypeError, ValueError):
            raise ToolError(f"input {key!r} must be a number, got {val!r}")
        if not math.isfinite(val):
            raise ToolError(f"input {key!r} must be a finite number, got {val!r}")
        if key in LOOP_DRIVING_KEYS and not (1 <= val <= MAX_HORIZON_YEARS):
            raise ToolError(
                f"input {key!r} must be between 1 and {MAX_HORIZON_YEARS} years, got {val:g}. "
                f"Each year materializes a row of cashflow, so this bound is what keeps one "
                f"request from consuming the whole service."
            )
    return inputs


def check_option(option: str) -> str:
    if option not in ALL_OPTION_KEYS:
        raise ToolError(f"unknown option {option!r}. Known: {', '.join(ALL_OPTION_KEYS)}")
    return option


# --- tools -----------------------------------------------------------------

def list_options() -> list[dict]:
    """Every option state the calculator models."""
    return [
        {
            "key": key,
            "label": ("Community Solar (Maine)" if key == "community"
                      else CAPITAL_OPTIONS[key]["label"]),
            "blurb": BLURBS[key],
            "needs_bill": key in OPTIONS_NEEDING_BILL,
        }
        for key in ALL_OPTION_KEYS
    ]


def get_assumptions(option: str) -> dict:
    """The full assumption ledger for one option: value, unit, tag, source, explain.

    This is the transparency payload — an agent that calls it can cite the calculator's inputs and
    tell a user which ones are placeholders (``tag == "unsourced — pending research"``).
    """
    check_option(option)
    if option == "community":
        a = default_assumptions()
        shown = ["default_monthly_bill", "price_per_kwh", "bill_offset_fraction",
                 "subscription_discount_pct", "allocation_pct"]
    else:
        _, a = capital_spec(option)
        shown = CAPITAL_OPTIONS[option]["shown"]
    return {"option": option, "assumptions": {k: asm_dict(a[k]) for k in shown}}


def _apply_inputs(assumptions: dict, inputs: dict) -> dict:
    """Apply override values onto assumption records, tolerating battery_-prefix mismatches.

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


def calculate(option: str, inputs: dict | None = None) -> tuple[dict, dict]:
    """Run the Python core for one option.

    Returns ``(payload, ignored_inputs)`` — the CLI ``--json`` payload shape, plus any inputs that
    mapped to no assumption of this option (surfaced for honesty, never silently dropped).
    """
    check_option(option)
    inputs = dict(check_inputs(inputs or {}))

    if option == "community":
        a = default_assumptions()
        bill = inputs.pop("monthly_bill", None)
        if bill is not None:
            a["default_monthly_bill"] = a["default_monthly_bill"].with_user_value(bill)
        else:
            bill = a["default_monthly_bill"].value
        annual_usage = inputs.pop("annual_usage_kwh", None)
        ignored = _apply_inputs(a, inputs)  # any other community assumption
        result = solar_calc.compute(
            monthly_bill=bill,
            price_per_kwh=a["price_per_kwh"].value,
            bill_offset_fraction=a["bill_offset_fraction"].value,
            subscription_discount_pct=a["subscription_discount_pct"].value,
            allocation_pct=a["allocation_pct"].value,
            annual_usage_kwh=annual_usage,
        )
        return json.loads(render_community_json(bill, a, result)), ignored

    module, merged = capital_spec(option)
    ignored = _apply_inputs(merged, inputs)
    result = module.compute_from_assumptions(merged)
    shown = CAPITAL_OPTIONS[option]["shown"]
    return json.loads(json.dumps(capital_payload(option, merged, result, shown))), ignored


def compare(options: list[str], inputs: dict | None = None) -> dict:
    """Two or more options side by side, tabulated — never recomputed.

    Each row is that option's OWN ``calculate()`` payload, so every number here equals what
    ``calculate(option)`` says alone (the parity the CLI's ``--compare`` holds, stated the same way
    for agents). ``inputs`` are SHARED: each is applied to every compared option that carries the
    key, mirroring the CLI's bare ``--set`` and the web's "Shared inputs" block. ``opportunity_rate``
    is the one that matters — NPVs at different discount rates are not comparable.
    """
    keys = [k.strip() for k in (options or []) if str(k).strip()]
    for key in keys:
        check_option(key)
    if len(set(keys)) != len(keys):
        raise ToolError("compare lists the same option twice")
    if len(keys) < 2:
        raise ToolError("compare needs at least two options (one option isn't a comparison) — "
                        "use calculate for a single estimate")
    check_inputs(inputs or {})

    rows, ignored_per_option = {}, {}
    for key in keys:
        payload, ignored = calculate(key, dict(inputs or {}))
        rows[key] = payload
        if ignored:
            ignored_per_option[key] = ignored

    # A shared input that reached NO compared option is a silent no-op otherwise — the caller
    # believes it moved the numbers and it didn't.
    unused = set(inputs or {})
    for ignored in ignored_per_option.values():
        unused &= set(ignored)
    if len(ignored_per_option) == len(keys) and unused:
        raise ToolError(f"no compared option carries: {', '.join(sorted(unused))}. "
                        f"Call get_assumptions(option) for the keys an option accepts.")

    # Community solar puts no capital at stake, so payback and NPV don't apply to it — null here
    # means "not applicable", not "zero", and the CLI's text view prints an em-dash for the same
    # reason.
    summary = []
    for key in keys:
        res = rows[key]["result"]
        summary.append({
            "option": key,
            "upfront_cost": res["capital"] if key == "community" else res["upfront_cost"],
            "annual_savings_year1": (res["annual_savings"] if key == "community"
                                     else res["annual_savings_year1"]),
            "simple_payback_years": None if key == "community" else res["simple_payback_years"],
            "npv": None if key == "community" else res["npv"],
        })

    shared = {}
    for key in ("annual_usage_kwh", "opportunity_rate"):
        for row in rows.values():
            if key in row["assumptions"]:
                shared[key] = row["assumptions"][key]
                break
    if "community" in rows:
        shared["monthly_bill"] = rows["community"]["inputs"]["monthly_bill"]

    return {
        "comparison": keys,
        "shared_inputs": shared,
        "summary": summary,          # the side-by-side table
        "options": rows,             # each option's full ledger, identical to calculate()
        "ignored_inputs": ignored_per_option,
    }
