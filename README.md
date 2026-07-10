# Solar Investment Calculator

Turn a Maine homeowner's plain question — *"What savings would I get with community solar when my
bill is $150 a month?"* — into a trustworthy, fact-checkable estimate, with **every number shown as
a labeled, editable, sourced assumption**, never a black box. See [`STRATEGY.md`](STRATEGY.md).

Six option states are modeled: **community solar** (zero capital), **balcony/plug-in**,
**rooftop**, **battery**, and the pairings **battery+rooftop** and **battery+balcony**. Capital
options get payback and an NPV verdict against investing the same cash elsewhere.

New here? See [`docs/how-to-use-and-verify.md`](docs/how-to-use-and-verify.md) for how to drive the
calculator and how to trust its numbers.

## Run it

The calculation core and CLI are stdlib-only Python 3 — no setup needed:

```sh
# Formula-correctness tests (the active metric)
pytest tests

# CLI: any option, any assumption editable
python src/cli.py                              # community solar at the sourced average Maine bill
python src/cli.py --bill 150                   # your bill
python src/cli.py --option rooftop --set capacity_kw=8
python src/cli.py --option battery+rooftop --json    # combos; machine-readable (agent-native)

# Website: open web/index.html in a browser, or serve it
python -m http.server --directory web 8000     # then visit http://localhost:8000
```

The **agent service** (question box backend) needs deps — a uv venv created *outside* the repo
from the checked-in `requirements.txt`, plus an `ANTHROPIC_API_KEY`. Setup and the error
contract: [`service/README.md`](service/README.md). The website is fully functional without it
(it falls back to the classic form flow, with a notice).

## Layout

```
src/
  assumptions.py       # assumption data model (label, value, unit, tag, source, explain) + defaults
  solar_calc.py        # community solar core (bill → usage → credits → savings) — SOURCE OF TRUTH
  capital.py           # capital-allocation engine: compare() one stream, combine() summed streams
  balcony.py, rooftop.py, battery.py   # per-option pure modules
  combo.py, battery_rooftop.py, battery_balcony.py   # additive combos (one mechanism, two configs)
  cli.py               # human + agent-native CLI surface (--json)
service/
  app.py, agent.py, spend.py   # LangGraph agent: question → routed, computed, capped answer
tests/, service/tests/ # worked-example, tagging, parity, ledger, and gate tests (pytest)
web/
  index.html, app.js   # question-first static UI; JS formulas mirror the Python core (self-checked)
tools/
  verify_web.py        # evidence-backed browser verification: run / check / record
docs/                  # strategy, plans, per-option integration notes, lessons learned
```

## How the estimates work

Community solar pays through Net Energy Billing: your usage generates kWh bill credits, and you buy
those credits from the provider at a discount — the discount is the savings
(`annual_savings = monthly_bill × 12 × bill_offset_fraction × subscription_discount_pct`).

Capital options compute year-1 savings and upfront cost, then the capital engine asks the
`STRATEGY.md` question: **are you better off buying solar, or investing that cash at the
opportunity rate?** (NPV > 0 → solar wins.) Combos are stream-wise additive: the battery keeps its
10-year flat stream, the PV keeps its 25-year escalating/degrading stream, and the verdict comes
from the summed per-year cashflows.

Each assumption is tagged `default (sourced)`, `user-provided`, or `unsourced — pending research`,
carries a plain-English explanation of what it means and what moves it, and sourced defaults cite
the research repo ([`../solar-investment-research`](../solar-investment-research)) plus a note on
what the source *is* and why it's credible.
