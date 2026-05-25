# Solar Investment Calculator

Turn a Maine homeowner's monthly electricity bill into a trustworthy, fact-checkable estimate of
what a solar move would save — with **every number shown as a labeled, editable, sourced
assumption**, never a black box. See [`STRATEGY.md`](STRATEGY.md).

The first proof of concept covers **community solar** (zero upfront capital). Rooftop, balcony, and
battery are later iterations ([`docs/BACKLOG.md`](docs/BACKLOG.md)).

New here? See [`docs/how-to-use-and-verify.md`](docs/how-to-use-and-verify.md) for how to drive the
calculator and how to trust its numbers.

## Run it

No dependencies — Python 3 standard library only.

```sh
# Formula-correctness tests (the active metric)
python3 -m unittest discover -s tests

# CLI: estimate from a bill
python3 src/cli.py --bill 150
python3 src/cli.py --bill 150 --discount 0.15 --offset-fraction 0.82 --price-per-kwh 0.306
python3 src/cli.py --bill 150 --json        # machine-readable (agent-native)

# Website: open web/index.html in a browser, or serve it
python3 -m http.server --directory web 8000   # then visit http://localhost:8000
```

## Layout

```
src/
  assumptions.py   # the assumption data model (label, value, unit, tag, source) + defaults
  solar_calc.py    # pure calculation core (bill → usage → credits → savings) — SOURCE OF TRUTH
  cli.py           # human + agent-native CLI surface
tests/
  test_solar_calc.py   # worked-example + cancellation + tagging tests (python3 -m unittest)
web/
  index.html, app.js   # static guided-walkthrough UI; JS formula mirrors the Python core
docs/
  brainstorms/, plans/ # Phase 1 spec and the build plan
```

## How the estimate works

Community solar pays through Net Energy Billing: your usage generates kWh bill credits, and you buy
those credits from the provider at a discount. Net savings = the discount on the credits your
subscription generates.

`annual_savings = monthly_bill × 12 × bill_offset_fraction × subscription_discount_pct`

In the bill-first flow `price_per_kwh` cancels out of the dollar result (it only sets the displayed
usage); the load-bearing numbers are the **offset fraction** and the **discount**. Each assumption
is tagged `default (sourced)`, `user-provided`, or `unsourced — pending research`, and sourced
defaults cite the research repo ([`../solar-investment-research`](../solar-investment-research)).
