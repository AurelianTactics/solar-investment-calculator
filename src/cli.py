"""Solar investment calculator — command-line surface (all options).

Agent-native parity (R10): everything a human can do here, an agent can do by importing the option
modules directly or by calling this CLI with ``--json``. Shows the result, the labeled calculation
steps (R9), and every assumption with its tag and source (R6-R8).

    # Community solar (default option) — bill-first
    python3 src/cli.py --bill 150
    python3 src/cli.py --bill 150 --discount 0.15 --offset-fraction 0.82 --price-per-kwh 0.306

    # Capital options — defaults, or override any assumption by key with --set (repeatable)
    python3 src/cli.py --option balcony
    python3 src/cli.py --option rooftop --set capacity_kw=8 --set installed_cost_per_w=3.5
    python3 src/cli.py --option battery --set resilience_value_per_year=400

    # Machine-readable
    python3 src/cli.py --option balcony --json
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from assumptions import Assumption, default_assumptions  # noqa: E402
from solar_calc import compute as compute_community  # noqa: E402

# Capital options. Modules + assumption builders are imported lazily (see capital_spec) so the
# community path never depends on the others.
CAPITAL_OPTIONS = {
    "balcony": {
        "label": "Balcony / Plug-In Solar (Maine)",
        "assumption_builders": ("balcony_assumptions", "capital_assumptions"),
        "shown": [
            "capacity_kw", "specific_yield_kwh_per_kw", "self_consumption_fraction",
            "volumetric_rate_per_kwh", "kit_cost", "electrician_cost",
            "opportunity_rate", "electricity_escalation", "panel_degradation", "horizon_years",
        ],
    },
    "rooftop": {
        "label": "Rooftop Solar (Maine)",
        "assumption_builders": ("rooftop_assumptions", "capital_assumptions"),
        "shown": [
            "capacity_kw", "specific_yield_kwh_per_kw", "installed_cost_per_w", "federal_itc_pct",
            "credit_value_per_kwh", "annual_usage_kwh", "offset_cap_fraction",
            "opportunity_rate", "electricity_escalation", "panel_degradation", "horizon_years",
        ],
    },
    "battery": {
        "label": "Home Battery Storage (Maine)",
        # capital first so battery_assumptions() can override horizon_years (10 vs the 25-yr PV default)
        "assumption_builders": ("capital_assumptions", "battery_assumptions"),
        "shown": [
            "usable_kwh", "installed_cost_per_kwh", "federal_itc_pct", "annual_bill_savings",
            "resilience_value_per_year", "opportunity_rate", "horizon_years",
        ],
    },
    # Combined options: one additive mechanism (combo.py), two thin modules. Battery keys are
    # battery_-prefixed so collisions (federal_itc_pct, horizon_years) stay per-component.
    "battery+rooftop": {
        "label": "Battery + Rooftop Solar (Maine)",
        "module": "battery_rooftop",
        "assumption_builders": ("battery_rooftop_assumptions",),
        "shown": [
            "capacity_kw", "specific_yield_kwh_per_kw", "installed_cost_per_w", "federal_itc_pct",
            "credit_value_per_kwh", "annual_usage_kwh", "offset_cap_fraction",
            "battery_usable_kwh", "battery_installed_cost_per_kwh", "battery_federal_itc_pct",
            "battery_annual_bill_savings", "battery_resilience_value_per_year",
            "battery_horizon_years", "battery_pv_interaction_value_per_year",
            "opportunity_rate", "electricity_escalation", "panel_degradation", "horizon_years",
        ],
    },
    "battery+balcony": {
        "label": "Battery + Balcony / Plug-In Solar (Maine)",
        "module": "battery_balcony",
        "assumption_builders": ("battery_balcony_assumptions",),
        "shown": [
            "capacity_kw", "specific_yield_kwh_per_kw", "self_consumption_fraction",
            "volumetric_rate_per_kwh", "kit_cost", "electrician_cost",
            "battery_usable_kwh", "battery_installed_cost_per_kwh", "battery_federal_itc_pct",
            "battery_annual_bill_savings", "battery_resilience_value_per_year",
            "battery_horizon_years", "battery_pv_interaction_value_per_year",
            "opportunity_rate", "electricity_escalation", "panel_degradation", "horizon_years",
        ],
    },
}


def capital_spec(option_key):
    """Lazily resolve (module, merged-assumptions) for a capital option."""
    import assumptions as asm_mod

    module = importlib.import_module(CAPITAL_OPTIONS[option_key].get("module", option_key))
    merged: dict = {}
    for builder in CAPITAL_OPTIONS[option_key]["assumption_builders"]:
        merged.update(getattr(asm_mod, builder)())
    return module, merged


def money(x: float) -> str:
    return f"${x:,.2f}"


def apply_overrides(a: dict, sets: list[str]) -> dict:
    """Apply --set key=value overrides, re-tagging each touched assumption user-provided."""
    for item in sets or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got: {item!r}")
        key, raw = item.split("=", 1)
        key = key.strip()
        if key not in a:
            raise SystemExit(f"--set unknown assumption key: {key!r}. Known: {', '.join(sorted(a))}")
        try:
            val = float(raw)
        except ValueError:
            raise SystemExit(f"--set value must be numeric, got: {raw!r}")
        a[key] = a[key].with_user_value(val)
    return a


# --- community solar (bill-first) ------------------------------------------

def build_community_assumptions(args) -> dict:
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
    return apply_overrides(a, args.set)


def render_community_text(bill, a, result, annual_usage_override) -> str:
    out = ["=" * 64, "  Community-Solar Savings Estimate (Maine)", "=" * 64]
    out.append(f"  Your monthly bill (do-nothing baseline): {money(bill)}")
    out += ["", "  ESTIMATE",
            f"    Annual savings : {money(result.annual_savings)}",
            f"    Monthly savings: {money(result.monthly_savings)}",
            f"    Percent off    : {result.pct_off * 100:.1f}%",
            f"    Upfront capital: {money(result.capital)}  (community solar requires none)", ""]
    out.append("  STEPS (bill -> usage -> credits -> savings)")
    for s in result.steps:
        val = f"{s.value:,.2f}" if s.unit.startswith("$") else f"{s.value:,.0f}"
        out += [f"    {s.n}. {s.label}", f"       {s.formula}", f"       = {val} {s.unit}"]
    out.append("")
    out += render_assumptions_block(
        a, ["price_per_kwh", "bill_offset_fraction", "subscription_discount_pct", "allocation_pct"])
    if annual_usage_override is not None:
        out.append(f"    - Annual usage (user-provided): {annual_usage_override:,.0f} kWh")
    out.append("=" * 64)
    return "\n".join(out)


def render_community_json(bill, a, result) -> str:
    payload = {
        "option": "community",
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


# --- capital options (balcony / rooftop / battery) -------------------------

def render_capital_text(option_key, a, result, shown) -> str:
    label = CAPITAL_OPTIONS[option_key]["label"]
    cap = result.capital
    out = ["=" * 64, f"  {label}", "=" * 64, "", "  ESTIMATE",
           f"    Annual savings (year 1): {money(result.annual_savings)}",
           f"    Upfront capital        : {money(result.upfront_cost)}"]
    payback = cap.simple_payback_years
    out.append(f"    Simple payback         : {payback:.1f} yr" if payback is not None
               else "    Simple payback         : never (no annual savings)")
    out += [f"    Lifetime savings ({cap.horizon_years} yr): {money(cap.lifetime_savings_nominal)} nominal",
            f"    NPV vs. investing cash : {money(cap.npv)}   ({'solar wins' if cap.npv > 0 else 'the market wins'} at {cap.opportunity_rate * 100:.0f}%)",
            ""]
    out.append("  STEPS")
    for s in result.steps:
        val = f"{s.value:,.2f}" if s.unit.startswith("$") else f"{s.value:,.0f}"
        out += [f"    {s.n}. {s.label}", f"       {s.formula}", f"       = {val} {s.unit}"]
    verdict_n = len(result.steps) + 1
    out += ["", f"    {verdict_n}. Capital verdict (vs. {cap.opportunity_rate * 100:.0f}% opportunity cost)",
            f"       NPV = -upfront + sum_t savings_t / (1+r)^t  =  {money(cap.npv)}", ""]
    out += render_assumptions_block(a, shown)
    out.append("=" * 64)
    return "\n".join(out)


def render_capital_json(option_key, a, result, shown) -> str:
    cap = result.capital
    payload = {
        "option": option_key,
        "result": {
            "annual_savings_year1": result.annual_savings,
            "upfront_cost": result.upfront_cost,
            "simple_payback_years": cap.simple_payback_years,
            "lifetime_savings_nominal": cap.lifetime_savings_nominal,
            "lifetime_roi": cap.lifetime_roi,
            "npv": cap.npv,
            "net_advantage_fv": cap.net_advantage_fv,
            "horizon_years": cap.horizon_years,
            "opportunity_rate": cap.opportunity_rate,
        },
        "steps": [dataclasses.asdict(s) for s in result.steps],
        "yearly": [dataclasses.asdict(y) for y in cap.yearly],
        "assumptions": {k: asm_dict(a[k]) for k in shown},
    }
    return json.dumps(payload, indent=2)


# --- shared rendering helpers ----------------------------------------------

def asm_dict(asm: Assumption) -> dict:
    d = dataclasses.asdict(asm)
    d["is_unsourced"] = asm.is_unsourced
    return d


def render_assumptions_block(a: dict, shown: list[str]) -> list[str]:
    out = ["  ASSUMPTIONS (edit any with --set key=value to refine the estimate)"]
    for key in shown:
        asm = a[key]
        out.append(f"    - {asm.label}")
        out.append(f"        {key} = {asm.value}  ({asm.unit})   [{asm.tag}]")
        if asm.explain:
            out.append(f"        what it means: {asm.explain}")
        if asm.source:
            cite = asm.source.title + (f" <{asm.source.url}>" if asm.source.url else "")
            out.append(f"        source: {cite}")
            if asm.source.what_is_it:
                out.append(f"        what the source is: {asm.source.what_is_it}")
            if asm.source.note:
                out.append(f"        note: {asm.source.note}")
        elif asm.is_unsourced:
            out.append("        source: (none yet — do not treat this number as established fact)")
    return out


def main(argv=None) -> int:
    # Windows consoles often default to a legacy codepage (cp1252) that can't encode characters
    # appearing in source notes (e.g. '≥'); degrade to replacement chars instead of crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    p = argparse.ArgumentParser(description="Estimate Maine solar savings across options.")
    p.add_argument("--option",
                   choices=["community", "balcony", "rooftop", "battery",
                            "battery+rooftop", "battery+balcony"],
                   default="community", help="which solar option to model (default: community)")
    p.add_argument("--bill", type=float, default=None, help="monthly bill ($) — required for community")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VAL",
                   help="override any assumption by key (repeatable); re-tags it user-provided")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    # community-specific convenience flags (kept for backward compatibility)
    p.add_argument("--price-per-kwh", type=float, default=None)
    p.add_argument("--offset-fraction", type=float, default=None)
    p.add_argument("--discount", type=float, default=None)
    p.add_argument("--allocation", type=float, default=None)
    p.add_argument("--annual-usage", type=float, default=None, help="annual usage kWh (community/rooftop)")
    args = p.parse_args(argv)

    try:
        if args.option == "community":
            if args.bill is None:
                p.error("--bill is required for the community option")
            a = build_community_assumptions(args)
            result = compute_community(
                monthly_bill=args.bill,
                price_per_kwh=a["price_per_kwh"].value,
                bill_offset_fraction=a["bill_offset_fraction"].value,
                subscription_discount_pct=a["subscription_discount_pct"].value,
                allocation_pct=a["allocation_pct"].value,
                annual_usage_kwh=args.annual_usage,
            )
            print(render_community_json(args.bill, a, result) if args.json
                  else render_community_text(args.bill, a, result, args.annual_usage))
            return 0

        module, merged = capital_spec(args.option)
        a = apply_overrides(merged, args.set)
        result = module.compute_from_assumptions(a)
        shown = CAPITAL_OPTIONS[args.option]["shown"]
        print(render_capital_json(args.option, a, result, shown) if args.json
              else render_capital_text(args.option, a, result, shown))
        return 0
    except ValueError as e:
        p.error(str(e))  # clean "cli.py: error: <message>" instead of a traceback


if __name__ == "__main__":
    raise SystemExit(main())
