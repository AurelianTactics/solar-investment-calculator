# Layout bake-off — 2026-07-20

**Decision: candidate B ("Ledger") is the live page.** Promoted into `web/index.html`; the
`web/layouts/` staging directory is gone. This is the W3 workstream of
`docs/plans/2026-07-15-001-feat-poc-closeout-plan.md`.

Three layouts were built as live, working pages sharing one **unmodified** `web/app.js` — the
constraint that makes the comparison honest, because a layout needing JS changes isn't a layout.
Each was driven through all eight page states in headless Chrome, then judged in a real browser in
the three states the plan named.

## Why this file exists

The first version of this decision was reported from screenshots that were then deleted as scratch
files. The verdict held up, but one of the numbers in it was wrong (see the correction below) and
nobody could check it. On a project whose rule is *observed, not claimed*, a design judgement needs
the same evidence trail as a calculation. So the artifacts live here, in the repo, and the losing
candidates are re-drivable rather than described.

## The three theses

| | Thesis | Type | Hue beyond ink/paper |
|---|---|---|---|
| **A — Editorial** | The old page was *right*, just over-dressed: keep the ambition, delete the competing systems | Fraunces (headings only) + Public Sans, no mono | one accent (sun ochre) |
| **B — Ledger** | This page is a financial statement, so set it as one; austerity is the transparency argument | IBM Plex Mono (numbers) + Public Sans (labels), no serif | **none** — hue only on NPV sign + the 3 provenance tags |
| **C — Product** | "Trustworthy" reads as professional and unremarkable rather than crafted | system stack only, one family | one blue accent |

## The states that decided it

Judging only the community default would have meant meeting the combo and compare views for the
first time *after* the losers were deleted. So all three were driven at:

- **`community`** — sparse: 4 steps, 4 assumptions. **All three looked fine here.** This state
  discriminates nothing; do not judge a layout change by it.
- **`battery+rooftop`** — dense: 9 steps, **25 assumptions** (every `battery_`-prefixed key).
- **`compare`** — the six-way 6×5 table, at 1280px where wide layouts engage.

## Measured result — assumption row pitch at 1280×1100

| Candidate | Row pitch | Rows per screen |
|---|---|---|
| **B — Ledger** | **87px** | **~13** |
| C — Product | 130px | ~8 |
| A — Editorial | 136px | ~8 |

B's row puts the label and its value on **one** line (a fixed three-track grid: value, unit,
provenance tag). A and C both stack label → value → disclosure, costing a line per row. Over 25
assumptions that is roughly two extra screens of scrolling.

## Verdicts

**C — Product: a genuine structural failure.** Its one structural idea, the ask and the estimate
side by side, backfires in compare: the table inherits the narrow right column, so "Balcony /
Plug-In Solar" and "Home Battery Storage" each wrap to three lines while ~640px of page sits empty
to the table's left. See `shots/c-compare.png`. This is the thesis colliding with the content, not
a tuning problem.

**A — Editorial: no fatal flaw. The legitimate runner-up.** It is the best-looking single screen of
the three, its compare view is fine, and its only defect was one CSS line (the focused row's
`inset` box-shadow painting on every cell instead of the first, drawing stray dividers). It lost on
density and thesis fit, *not* on being broken.

**B — Ledger: won on the two states that stress the page.** Highest density by a factor of 1.6, the
entire six-way comparison above the fold with one line per option name, and hue that means
something because it appears in only two places.

### Correction to the first report

The original write-up claimed A fit "~7" rows and implied C did better at 8. Measured properly, A
is 136px and C is 130px — **effectively identical**. "A failed on density" was not a claim that
separated A from C; that weakness was shared, and presenting it as decisive overstated the case
against A. The real differentiators are C's compare failure and B's 1.6× density lead over both.

## Artifacts

```
shots/{a,b,c}-dense.png      battery+rooftop, refine drawer open, scrolled to the assumptions head
shots/{a,b,c}-compare.png    six-way compare at 1280x1100
candidates/{a,c}.html        the losing candidates, still drivable (see below)
```

All six shots are viewport captures at 1280×1100, same scroll anchor, so they are directly
comparable. One caveat: the B shots are of the **promoted** page, which by then carried two small
fixes A and C never got (the toggle strip hugging its buttons, and a wider usage input). Neither
touches the ledger geometry the density numbers come from.

### Re-driving a losing candidate

```sh
python tools/verify_web.py run --page docs/design/2026-07-20-layout-bakeoff/candidates/a.html
```

`--page` writes its own `.verify/evidence-<slug>.json` and screenshot subdirectory and **never
feeds the Stop gate** — the gate hashes `web/index.html` + `web/app.js` only, so an archived
candidate can neither block a turn nor falsely certify the live page. The candidates carry
`<script src="app.js">` because the driver copies `app.js` beside the generated page; they are not
openable directly from disk. Verified working on 2026-07-20 (candidate A, 8/8 states pass).

## What carries forward

**Density is the constraint, not decoration.** The live page's design system is documented at the
top of `web/index.html`. Judge any change to it against `battery+rooftop` and the six-way compare —
never against the four-row community default, which is precisely where three very different
layouts all looked fine.
