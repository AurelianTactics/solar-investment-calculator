# How to use and verify this calculator

A human-facing guide to *driving* the calculator and *trusting* its numbers. (Agents: the same
surfaces work for you — see "Agent-native parity" at the bottom.)

## Use it

The core and CLI are stdlib-only Python 3. From the repo root:

```sh
# CLI — community solar is the default option; with no --bill it uses the sourced Maine average
python src/cli.py
python src/cli.py --bill 150
python src/cli.py --bill 150 --json                 # machine-readable

# Any of the six option states; --set overrides any assumption (re-tags it "user-provided")
python src/cli.py --option rooftop --set capacity_kw=8
python src/cli.py --option battery+rooftop          # combos: battery+rooftop, battery+balcony

# Website — same formulas, in a browser
python -m http.server --directory web 8000          # then open http://localhost:8000
```

In the web UI: **ask the question box** (or click a sample prompt). If the local agent service is
running, it routes your question and answers with the same numbers the CLI produces; if it isn't —
or its budget is spent — the page falls back to the classic form flow with a notice, fully
client-side. "Refine this estimate" opens the option toggles (community stands alone; battery
pairs with rooftop or the balcony kit) and the input boxes; the headline statement rewrites into a
plain sentence describing your scenario. Expand any assumption row for a newcomer-grade
explanation of what the number means and what the source actually is.

Running the agent service (optional; needs an `ANTHROPIC_API_KEY` and the uv venv):
see [`../service/README.md`](../service/README.md).

> `docs/human_to_do.md` is your private notebook — agents are told not to read it.

## Verify it (why you can trust the number)

The product **is** the audit trail. Four independent checks back every result:

1. **The formula-correctness test suite — the active metric.** Every option's hand-verified worked
   example is encoded as a test; any change that breaks a known case is a regression.
   ```sh
   pytest tests                    # core (runs anywhere)
   pytest tests service/tests     # + agent service (needs the venv; the LLM is always stubbed)
   ```

2. **The web/Python parity self-check.** `web/app.js` is a *mirror* of the Python core (the source
   of truth). On page load it re-runs every option's worked example — including both combos — in
   JS; if anything diverges, a red banner tells you not to trust the page.

3. **Two-layer browser verification.** "The website works" is observed, never claimed:
   - *Deterministic loop* — `python tools/verify_web.py run` drives all six option states in a
     headless browser (Chrome/Chromium/Edge, any OS), asserts each renders with parity intact and
     that asking with the service unreachable degrades to the form flow, and writes screenshots +
     a hashed evidence record to `.verify/`.
   - *Agent perception loop* — `/verify-web-page <state>` has an agent look at the real page
     (a11y snapshot, screenshot, console), judge it against intent, and **record** the verdict
     (`python tools/verify_web.py record ...`). A fresh failing verdict blocks the gate exactly
     like failing render evidence; verdicts go stale when `web/` changes.
   The end-of-turn Stop gate (`python tools/verify_web.py check`) reads artifacts only — it is
   deterministic and token-free.

4. **Every number is labeled, tagged, sourced — and explained.** In the CLI, `--json`, and the web
   UI each assumption shows its value, a tag, a plain-English `explain` (what it means, why it
   matters to your savings, what moves it), and for sourced defaults a citation plus
   `what_is_it` — what kind of document the source is and why it's credible:
   - `default (sourced)` — a researched number citing a `wiki/` article in
     `../solar-investment-research`. Follow the link to the primary source.
   - `user-provided` — you edited it (or the agent extracted it from your question); the source is
     cleared, because *your statement* is now the source.
   - `unsourced — pending research` — a placeholder. **Do not treat it as established fact** until
     research lands it.

### Spot-check the headline by hand

The community-solar dollar result reduces to one identity:

```
percent_off_bill  =  bill_offset_fraction  ×  subscription_discount_pct
annual_savings    =  monthly_bill × 12 × percent_off_bill
```

With the shipped CMP defaults: `0.82 × 0.15 ≈ 12.3%`, and a $150/mo bill → `150 × 12 × 0.123 ≈
$221/yr`. That ~12% lands inside Maine OPA's independently-stated "10–15% savings" range.

For a combo, additivity is the spot-check: with escalation and degradation zeroed, battery+rooftop
upfront is `16,225 + 13,473 = $29,698`, year-1 savings `1,782 + 200 = $1,982`, and NPV is the sum
of the component NPVs — while payback (`29,698 / 1,982 ≈ 15.0 yr`) matches *neither* component's,
because payback must come from the combined stream.

### The agent path can't invent numbers

The question-box agent does **only routing and extraction** — it picks the option and pulls out
numbers you stated, tagging them `user-provided`. The arithmetic always runs in the same Python
core the tests verify, and the service's payload is byte-shaped like `cli.py --json`. Its spending
is capped by a persisted ledger; over cap, the page falls back to the form.

## How research feeds the numbers

Sourced defaults come from the companion repo `../solar-investment-research`. The loop: research
ingests verbatim sources → compiles cited `wiki/` articles → lands answers in
`wiki/calculator-brief/` → this calculator pulls those numbers and tags them `default (sourced)`.
The research repo never edits the calculator; the calculator pulls. To verify a default is
current, check that the cited article's numbers (and their effective dates — utility rates reset
every Jan 1) still match.

## Agent-native parity

Anything above, an agent can do headlessly: import the option modules directly, call
`python src/cli.py --json` for a structured result that includes every step and every assumption
(value, tag, source, `explain`, `what_is_it`, `is_unsourced`), or POST the same question a human
would type to the local service's `/ask`. The formula suite plus `verify_web.py check` are the
automated verification arms.
