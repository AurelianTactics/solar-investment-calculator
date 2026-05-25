"""Community-solar POC — command-line surface.

Agent-native parity (R10): everything a human can do here, an agent can do by importing
``solar_calc`` directly or by calling this CLI with ``--json``. Shows the result, the labeled
calculation steps (R9), and every assumption with its tag and source (R6-R8).

    python3 src/cli.py --bill 150
    python3 src/cli.py --bill 150 --price-per-kwh 0.306 --discount 0.15 --offset-fraction 0.82
    python3 src/cli.py --bill 150 --json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from assumptions import Assumption, default_assumptions  # noqa: E402
from solar_calc import compute  # noqa: E402


def build_assumptions(args) -> dict[str, Assumption]:
    """Start from shipped defaults; override with any user-provided values (re-tagging them)."""
    a = default_assumptions()
    overrides = {
        "price_per_kwh": args.price_per_kwh,
        "bill_offset_fraction": args.offset_fraction,
        "subscription_discount_pct": args.discount,
        "allocation_pct": args.allocation,
    }
    for key, val in overrides.items():
        if val is not None:
            a[key] = a[key].with_user_value(val)
    return a


def money(x: float) -> str:
    return f"${x:,.2f}"


def render_text(bill: float, a: dict, result, annual_usage_override) -> str:
    out: list[str] = []
    out.append("=" * 64)
    out.append("  Community-Solar Savings Estimate (Maine POC)")
    out.append("=" * 64)
    out.append(f"  Your monthly bill (do-nothing baseline): {money(bill)}")
    out.append("")
    out.append("  ESTIMATE")
    out.append(f"    Annual savings : {money(result.annual_savings)}")
    out.append(f"    Monthly savings: {money(result.monthly_savings)}")
    out.append(f"    Percent off    : {result.pct_off * 100:.1f}%")
    out.append(f"    Upfront capital: {money(result.capital)}  (community solar requires none)")
    out.append("")
    out.append("  STEPS (bill -> usage -> credits -> savings)")
    for s in result.steps:
        unit = s.unit
        val = f"{s.value:,.2f}" if unit.startswith("$") else f"{s.value:,.0f}"
        out.append(f"    {s.n}. {s.label}")
        out.append(f"       {s.formula}")
        out.append(f"       = {val} {unit}")
    out.append("")
    out.append("  ASSUMPTIONS (edit any to refine the estimate)")
    shown = ["price_per_kwh", "bill_offset_fraction", "subscription_discount_pct", "allocation_pct"]
    for key in shown:
        asm = a[key]
        out.append(f"    - {asm.label}")
        out.append(f"        value: {asm.value}  ({asm.unit})   [{asm.tag}]")
        if asm.source:
            src = asm.source
            cite = src.title + (f" <{src.url}>" if src.url else "")
            out.append(f"        source: {cite}")
            if src.note:
                out.append(f"        note: {src.note}")
        elif asm.is_unsourced:
            out.append("        source: (none yet — do not treat this number as established fact)")
    if annual_usage_override is not None:
        out.append(f"    - Annual usage (user-provided): {annual_usage_override:,.0f} kWh")
    out.append("=" * 64)
    return "\n".join(out)


def render_json(bill: float, a: dict, result) -> str:
    def asm_dict(asm: Assumption) -> dict:
        d = dataclasses.asdict(asm)
        d["is_unsourced"] = asm.is_unsourced
        return d

    payload = {
        "inputs": {"monthly_bill": bill},
        "result": {
            "annual_savings": result.annual_savings,
            "monthly_savings": result.monthly_savings,
            "pct_off": result.pct_off,
            "capital": result.capital,
            "annual_spend": result.annual_spend,
            "annual_usage_kwh": result.annual_usage_kwh,
            "credits_generated": result.credits_generated,
        },
        "steps": [dataclasses.asdict(s) for s in result.steps],
        "assumptions": {k: asm_dict(v) for k, v in a.items()},
    }
    return json.dumps(payload, indent=2)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Estimate Maine community-solar savings from a bill.")
    p.add_argument("--bill", type=float, required=True, help="approximate monthly electricity bill ($)")
    p.add_argument("--price-per-kwh", type=float, default=None, help="all-in $/kWh (else default)")
    p.add_argument("--offset-fraction", type=float, default=None, help="portion of bill the credit offsets")
    p.add_argument("--discount", type=float, default=None, help="subscription discount (fraction, e.g. 0.15)")
    p.add_argument("--allocation", type=float, default=None, help="share of usage the subscription covers")
    p.add_argument("--annual-usage", type=float, default=None, help="annual usage in kWh (overrides bill->usage)")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = p.parse_args(argv)

    a = build_assumptions(args)
    result = compute(
        monthly_bill=args.bill,
        price_per_kwh=a["price_per_kwh"].value,
        bill_offset_fraction=a["bill_offset_fraction"].value,
        subscription_discount_pct=a["subscription_discount_pct"].value,
        allocation_pct=a["allocation_pct"].value,
        annual_usage_kwh=args.annual_usage,
    )
    print(render_json(args.bill, a, result) if args.json else render_text(args.bill, a, result, args.annual_usage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
