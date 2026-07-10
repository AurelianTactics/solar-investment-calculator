---
title: Judgment Belongs in Evidence Production; the Gate Stays Deterministic
date: 2026-07-09
category: best-practices
problem_type: best_practice
component: verification
severity: medium
applies_when:
  - A quality bar needs an LLM's (or human's) judgment — "does this page read right?"
  - A hard gate (Stop hook, CI check) must decide pass/fail cheaply and reproducibly
  - There's a temptation to have the gate itself call a model or drive a browser
tags:
  - verification
  - llm-judge
  - stop-hook
  - evidence
  - avird
---

# Judgment Belongs in Evidence Production; the Gate Stays Deterministic

## Context

The web UI needed verification beyond DOM markers: does the page *read* right — layout, density,
explanations legible? That's judgment, which means an agent with eyes (or a model). But the
end-of-turn Stop gate must be cheap, reproducible, and must never spend tokens or depend on a
browser being installed.

## The pattern (ported from avird_2026)

Split verification into two layers with a strict ownership rule:

1. **Evidence production is where judgment lives.** The agent perception loop
   (`/verify-web-page`) drives a real browser, looks at the a11y tree + screenshot + console,
   judges against stated intent, and **records** its verdict as an artifact:
   `python tools/verify_web.py record <state> --result pass|fail --screenshot ... --note ...`.
   The record refuses screenshots that don't exist (no verdicts about evidence never captured)
   and is stamped with the current content hashes of the files it judged.

2. **The gate only reads artifacts.** `verify_web.py check` (wrapped by the Stop hook) is pure
   file-reading: render evidence must be fresh and passing, and no *fresh* failing perception
   verdict may exist. Stale verdicts (hashes changed) are ignored, not trusted. The gate never
   drives a browser, never calls a model, exits 0/3 deterministically.

Two conventions make it honest:

- **Findings are recorded as `fail` first**, then fixed, re-run, and re-recorded as `pass`. The
  fail record is history, not embarrassment — it proves the loop actually looked. (Exercised for
  real on first use: a clipped placeholder went in as a recorded fail, blocked the gate, then
  cleared.)
- **Freshness is content hash, not timestamp.** Editing the judged files silently invalidates old
  verdicts in both directions — old passes can't vouch for a changed page, and old fails can't
  block a fixed one.

## Why not put the judge in the gate?

A gate that calls a model is nondeterministic (same page, different verdicts), costs tokens on
every end-of-turn, fails when the network/key/browser is missing, and can be argued with. A gate
that reads recorded artifacts is none of those things — while still transmitting the judge's
verdict with full force, because a fresh recorded `fail` blocks exactly like a failed render.

## How to reuse

Any "LLM as judge" quality bar can follow this shape: **judge → record artifact with content
hashes → deterministic gate reads artifacts**. The judge can be as smart, slow, and expensive as
needed, because it runs once per change during production, not once per gate check.
