---
title: LLM-Extracted Inputs Must Be Applied or Surfaced — Never Silently Dropped
date: 2026-07-10
category: design-patterns
module: service
problem_type: design_pattern
component: assistant
severity: high
applies_when:
  - "An LLM extraction schema feeds values into code keyed by identifiers (assumption keys, config fields, API params)"
  - "The same quantity has different key names in different contexts (e.g. bare vs namespaced keys across option variants)"
  - "The product's promise includes transparency about which user inputs shaped the answer"
tags: [llm-extraction, structured-output, key-namespacing, transparency, agent-service]
---

# LLM-Extracted Inputs Must Be Applied or Surfaced — Never Silently Dropped

## Context

The agent service routes a question with one structured-output call producing
`{option, inputs: {key: value}}`, then applies each extracted input onto the routed option's
assumption dict via `with_user_value()`. The first implementation applied only keys that matched
(`if key in merged`) and threw the rest away.

The trap: the extraction schema's key vocabulary and the per-option assumption namespaces had
quietly diverged. The schema told the model to key battery size as `battery_usable_kwh` (the
combo namespacing), but the plain battery option uses the bare `usable_kwh`. So "is a 20 kWh
battery worth it?" extracted `{battery_usable_kwh: 20}`, matched nothing, computed at the
13.5 kWh default — while `agent.extracted` still displayed the 20, claiming the user's number was
used. A dishonest answer on a transparency-first product, invisible in every test that used
well-formed keys. Caught in code review, not by the suite.

## Guidance

At any LLM-extraction → keyed-application boundary, enforce two rules
(`_apply_inputs` in `service/agent.py`):

1. **Normalize before giving up.** Try the key, then its known aliases — here, the
   `battery_`-prefix-flipped twin, covering both directions (schema emits prefixed for a bare
   option, or bare for a combo).
2. **Return what you couldn't map; put it in the payload.** Anything still unmapped goes into the
   response as `agent.ignored_inputs` — the consumer (and the tests) can see exactly which stated
   numbers did *not* shape the answer.

```python
def _apply_inputs(assumptions: dict, inputs: dict) -> dict:
    ignored: dict = {}
    for key, val in inputs.items():
        target = key
        if target not in assumptions:
            flipped = key[len("battery_"):] if key.startswith("battery_") else "battery_" + key
            target = flipped if flipped in assumptions else None
        if target is None:
            ignored[key] = val
        else:
            assumptions[target] = assumptions[target].with_user_value(val)
    return ignored
```

Pin it with tests from both directions plus a genuinely unmappable key
(`TestInputKeyNormalization` in `service/tests/test_agent.py`): prefixed key onto the bare option,
bare key onto the combo, and `ignored_inputs` carrying what didn't map.

## Why This Matters

The failure is *silent and self-contradicting*: the answer body computes on defaults while the
provenance section claims the user's value was applied. No exception, no failing test (stubs emit
well-formed keys), no visible artifact — only a wrong number presented confidently. For a product
whose entire premise is "every number is a labeled, honest assumption," this is the worst kind of
bug. The general form: **an extraction schema is a second copy of your key vocabulary**, and two
copies drift; code must absorb the drift (normalize) and confess the remainder (surface), because
you cannot prompt-engineer the drift away.

## When to Apply

- Wiring any structured-output/tool-call result into dicts, configs, or builders keyed by name
- Whenever the same quantity has context-dependent key names (namespaced combos, per-variant
  schemas, versioned APIs)
- Reviewing agent endpoints: grep for `if key in` followed by a bare loop — the silent-drop shape

## Examples

Before: `for key, val in inputs.items(): if key in merged: merged[key] = ...` — unmatched keys
vanish; `agent.extracted` still shows them.

After: `ignored = _apply_inputs(merged, inputs)` and the response carries
`"agent": {"extracted": ..., "ignored_inputs": ignored, ...}` — either the value shaped the
answer, or the answer says it didn't.

## Related

- `docs/solutions/best-practices/judge-as-evidence-gate-stays-deterministic.md` — the other
  honesty mechanism from the same build: verdicts recorded as artifacts, never claimed
- `docs/options-integration-notes.md` — the combos entry documenting the `battery_` prefix
  namespacing that created the two key vocabularies
