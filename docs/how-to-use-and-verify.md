# How to use and verify this calculator

A human-facing guide to *driving* the calculator and *trusting* its numbers. (Agents: the same
surfaces work for you — see "Agent-native parity" at the bottom.)

## Use it

No dependencies — Python 3 standard library only. From the repo root:

```sh
# CLI — estimate from a monthly bill (community solar is the default option)
python3 src/cli.py --bill 150
python3 src/cli.py --bill 150 --json                # machine-readable

# Override any assumption (it re-tags that number "user-provided")
python3 src/cli.py --bill 150 --discount 0.15 --offset-fraction 0.82 --price-per-kwh 0.306

# Website — same formula, in a browser
python3 -m http.server --directory web 8000         # then open http://localhost:8000
```

In the web UI: type your bill, optionally open "refine the inputs," and edit any assumption inline —
it recomputes instantly and the edited number turns from *sourced* to *user-provided*.

> `docs/human_to_do.md` is your private notebook — agents are told not to read it.

## Verify it (why you can trust the number)

The product **is** the audit trail. Three independent checks back every result:

1. **The formula-correctness test suite — the active metric.** A hand-verified worked example is
   encoded as a test; any change that breaks a known case is a regression.
   ```sh
   python3 -m unittest discover -s tests
   ```
   Green means the calculation core matches the numbers worked out by hand in the plan.

2. **The web/Python parity self-check.** `web/app.js` is a *mirror* of the Python core
   (`src/solar_calc.py`, the source of truth). On page load it re-runs the worked example in JS; if
   the JS ever diverges from the verified result, a red banner appears and tells you not to trust
   the page. (No JS runtime ships here, so the Python suite remains authoritative.)

3. **Every number is labeled, tagged, and sourced.** In both the CLI and the web UI each assumption
   shows its value, a tag, and (when sourced) a citation:
   - `default (sourced)` — a researched number citing a `wiki/` article in
     `../solar-investment-research`. Follow the link to the primary source.
   - `user-provided` — you edited it; the source is cleared.
   - `unsourced — pending research` — a placeholder. **Do not treat it as established fact** until
     research lands it.

   To re-trace a sourced default, open the cited research article and follow it to the verbatim
   `raw/` source (utility tariff, Maine PUC/OPA/DOE page, provider terms).

### Spot-check the headline by hand

The community-solar dollar result reduces to one identity:

```
percent_off_bill  =  bill_offset_fraction  ×  subscription_discount_pct
annual_savings    =  monthly_bill × 12 × percent_off_bill
```

With the shipped CMP defaults: `0.82 × 0.15 ≈ 12.3%`, and a $150/mo bill → `150 × 12 × 0.123 ≈
$221/yr`. That ~12% lands inside Maine OPA's independently-stated "10–15% savings" range — the model
and the sourced inputs agree. (`price_per_kwh` only sets the *displayed* usage; it cancels out of
the dollar result in the bill-first flow.)

## How research feeds the numbers

Sourced defaults come from the companion repo `../solar-investment-research`. The loop: research
ingests verbatim sources → compiles cited `wiki/` articles → lands answers in
`wiki/calculator-brief/answers.md` with an exit checklist → this calculator pulls those numbers and
re-tags its defaults `default (sourced)`. The research repo never edits the calculator; the
calculator pulls. To verify a default is current, check that the cited article's numbers (and their
effective dates — utility rates reset every Jan 1) still match.

## Agent-native parity

Anything above, an agent can do headlessly: import `src/solar_calc.py` directly, or call
`python3 src/cli.py --json` for a structured result that includes every step and every assumption
(value, tag, source, `is_unsourced`). The formula-correctness suite is the automated verification
arm — an agent re-runs it to confirm a change is safe.
