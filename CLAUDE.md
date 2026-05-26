# Solar Investment Calculator

A transparency-first tool that turns a Maine homeowner's electricity situation into a trustworthy,
fact-checkable estimate of what each solar option would save. Every number is a labeled, editable,
sourced assumption — never a black-box output. **Why** this exists and who it's for: `STRATEGY.md`.

## What this is

Python 3 **standard library only** (no deps) + a static web mirror. Four options are modeled:

- **community solar** — zero capital; `src/solar_calc.py`.
- **balcony / plug-in, rooftop, battery** — capital options on the shared capital-allocation engine
  (`src/capital.py`): each is a small pure module (`src/balcony.py`, `src/rooftop.py`,
  `src/battery.py`) that produces upfront cost + annual savings, then asks the engine for
  payback/NPV vs. investing the cash.

`src/assumptions.py` is the shared assumption data model + per-option defaults. `src/cli.py` is the
human + agent surface. `web/` mirrors the Python formulas with an on-load self-check.

## Active metric — run before reporting any calculation change done

**Formula correctness:** outputs must match the hand-verified worked examples encoded as tests. A
change that breaks a known case is a regression.

```sh
python3 -m unittest discover -s tests        # the metric (all options)
python3 src/cli.py --bill 150                # community (default); --json for agents
python3 src/cli.py --option rooftop --set capacity_kw=8   # capital options; --set overrides any assumption
```

The Python core is the **source of truth**. `web/app.js` is a mirror with a per-option self-check
banner; keep it in sync when a formula changes (no JS runtime here — the Python suite is the metric).

## Canonical docs (read what's relevant before non-trivial work)

| Doc | What it holds |
|---|---|
| `STRATEGY.md` | Target problem, transparency approach, audience, active metric |
| `docs/how-to-use-and-verify.md` | How to drive the calculator and how to trust its numbers |
| `docs/options-integration-notes.md` | Per-option: what research landed, what firmed up, what surprised us, what's open |
| `docs/plans/` | Build-ready plans (community-solar POC; the options-expansion plan) |
| `docs/brainstorms/` | Phase 1 spec (community-solar requirements) |
| `docs/BACKLOG.md` | Ideas captured, not scheduled — don't pull one in without a deliberate decision |
| `docs/solutions/` | Lessons learned (e.g. verify the runtime before choosing a stack) |

`docs/human_to_do.md` is human-only — do not read or reference it.

## Conventions (universal)

- **Assumptions are first-class.** Every number carries a label, value+unit, a tag
  (`default (sourced)` | `user-provided` | `unsourced — pending research`), and a source. Never
  present an unsourced default as established fact.
- **Show the steps, not just the answer.** Every option returns its calculation chain for display.
- **Agent-native parity.** Anything a human can do, an agent can do via the module or `--json`.
- **Sourced defaults trace to research.** A `default (sourced)` value cites a `wiki/` article in
  `../solar-investment-research`. The calculator *pulls* sourced numbers; it never invents them. If
  research hasn't landed a number, tag it `unsourced — pending research`.
- **The capital engine is the centerpiece** for capital options: NPV > 0 means buying solar beats
  investing the same cash at the opportunity rate. Community solar is $0 capital and skips it.
