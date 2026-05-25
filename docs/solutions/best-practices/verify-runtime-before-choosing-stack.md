---
title: Verify the Runtime Exists Before Committing a Stack to It
date: 2026-05-25
category: best-practices
problem_type: best_practice
component: build_setup
severity: medium
applies_when:
  - A plan names a specific runtime/toolchain for a deliverable whose acceptance is "tests pass"
  - The build environment was not the same environment the plan was written in
  - The active success metric is an executable check (a test suite, a lint, a benchmark)
tags:
  - planning
  - environment
  - testability
  - active-metric
---

# Verify the Runtime Exists Before Committing a Stack to It

## Context

The community-solar POC plan specified a JavaScript core tested with `node --test`. At build time
the environment had **no JS runtime** (no node/deno/bun) — only Python 3.12. The project's *active
metric* is formula correctness via an executable test suite (`STRATEGY.md`). A test suite that
can't run can't be the metric, so the stack was pivoted to Python (source-of-truth core + tests)
with the website kept as a JS mirror guarded by an on-load self-check.

## Guidance

When a plan names a toolchain for a deliverable whose acceptance is "the check passes," confirm the
runtime for that check exists **in the environment the work will run in** before writing code
against it. The plan's prose ("use `node --test`") is an assumption, not a guarantee — the same way
a tool's described behavior is an assumption until verified (cf. the `llm_knowledge_base` WebFetch
incident, where a tool "described as" HTML→markdown actually summarized).

Cheap check, done first:

```sh
for c in node deno bun python3; do command -v "$c" && "$c" --version; done
```

If the named runtime is missing:

1. **Don't silently install heavy/networked toolchains** in an unattended run — that's a large,
   possibly-unpermitted side effect.
2. **Pivot the tested core to an available runtime** so the active metric stays executable. Keep
   any secondary surface (a browser UI) as a faithful *mirror*, and add a cheap parity guard (e.g.
   a self-check of the canonical worked example on load) so the two can't silently diverge.
3. **Record the pivot in the plan** with the reason, so the divergence from the original plan is
   legible rather than mysterious.

## Why it matters

The failure mode is writing an entire core + test suite in a language you then can't execute —
discovering at "run the tests" time that the metric is dead. For a project whose whole thesis is
*verifiable* transparency, a non-runnable test suite is worse than no plan: it looks done and isn't.

## When to apply

- Any time a plan's load-bearing acceptance check depends on a specific runtime/tool.
- Especially when the planning session and the execution session are different environments.

## Related

- `docs/plans/2026-05-25-feat-community-solar-poc-plan.md` §Stack (the recorded pivot).
- Sibling project lesson: `../llm_knowledge_base/docs/solutions/best-practices/validate-ai-tool-semantics-and-output.md`
  (a tool's described behavior is not a contract — verify before scaling).
