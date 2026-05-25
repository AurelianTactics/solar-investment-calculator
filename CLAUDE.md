# Solar Investment Calculator

A transparency-first tool that turns a Maine homeowner's monthly electricity bill into a
trustworthy, fact-checkable estimate of what a solar move would save. Every number is a
labeled, editable, sourced assumption — never a black-box output. See `STRATEGY.md`.

## Canonical docs (read these before non-trivial work)

| Doc | What it holds |
|---|---|
| `STRATEGY.md` | Target problem, approach (transparency), audience, active metric, tracks |
| `docs/brainstorms/community-solar-poc-requirements.md` | Phase 1 spec: the community-solar POC requirements, flows, acceptance examples |
| `docs/plans/` | Build-ready plans derived from the brainstorms (e.g. the community-solar POC plan) |
| `docs/BACKLOG.md` | Ideas captured, not scheduled — don't pull one into work without a deliberate decision |

`docs/human_to_do.md` is human-only — do not read or reference it.

## Phase roadmap

- **Phase 0 — Setup** *(done)*: `git init`, `CLAUDE.md`, `BACKLOG.md`, `STRATEGY.md`, scaffolding.
- **Phase 1 — Plan** *(done)*: frame the problem, spec the community-solar POC, hand off open assumptions to research.
- **Phase 2 — Research** *(separate repo)*: `../solar-investment-research` answers the open/unsourced assumptions. Owned there, not here.
- **Phase 3 — Build**: implement the POC.
- **Phase 4+ — Integrate**: fold research findings into the POC's defaults; decide how options come together.

## Active metric

**Formula correctness** — calculation outputs must match hand-verified worked examples. A change
that breaks a known case is a regression. The worked example lives in the POC plan and is encoded
as a test. Run it before reporting any calculation change done:

```sh
python3 -m unittest discover -s tests   # the metric
python3 src/cli.py --bill 150           # human + agent-native surface (add --json for agents)
```

The source of truth is `src/solar_calc.py` (pure) + `src/assumptions.py` (the data model). The
website (`web/`) is a JS **mirror** of the same formula with an on-load self-check; keep the two in
sync when the formula changes. No JS runtime in this environment — the Python suite is the metric.

## Conventions

- **Assumptions are first-class.** Every number in a calculation carries a label, a value+unit, a
  tag (`default (sourced)` | `user-provided` | `unsourced — pending research`), and a source.
  Never present an unsourced default as established fact.
- **Show the steps, not just the answer.** bill → usage → credits → savings must be inspectable.
- **Agent-native parity.** Anything a human can do (enter inputs, edit assumptions, read result +
  steps) an agent can do too, and the calculation is verifiable by the formula-correctness check.
- **Sourced defaults trace to research.** A `default (sourced)` value cites a `wiki/` article in
  `../solar-investment-research`. If research hasn't landed the number yet, tag it
  `unsourced — pending research` rather than guessing.
