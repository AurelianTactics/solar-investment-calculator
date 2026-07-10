---
description: Agent perception loop over the calculator page — navigate, a11y snapshot, screenshot, console check, judge against intent, record the verdict as gate-respected evidence.
---

# /verify-web-page $ARGUMENTS

Give the agent eyes on the page. This is the **build-loop** half of the two-layer verification
model: it proves a page state *looks and reads* right — layout, density, explanations legible,
nothing overlapping — not just that markers exist in the DOM. The deterministic render loop
(`/verify-web`) is the other half and remains the hard floor.

Usage: `/verify-web-page <state> [intent notes]`
e.g. `/verify-web-page battery+rooftop "8 combo steps + verdict, statement names both components"`

States: `community` · `balcony` · `rooftop` · `battery` · `battery+rooftop` · `battery+balcony`,
plus the cross-state surfaces: the **question box** (default question + sample chips) and the
**fallback notice** (submit with the service down → form flow + notice).

Drives the browser through the **`playwright` Claude Code plugin** MCP tools. First use may
need browser binaries: `npx playwright install`.

## Steps

1. **Pick the target.** The page is static: `browser_navigate` to the repo's
   `web/index.html` as a `file://` URL. To land on a specific option state, evaluate
   `selectOption('<state>')` in the page (it's a global — the same driver contract the
   deterministic loop uses).

2. **Read the accessibility snapshot** — `browser_snapshot`. The token-cheap primary signal:
   headings, the steps list, assumption rows, tag pills, expanders — reason about structure here.

3. **Screenshot** — `browser_take_screenshot` (save it under `.verify/screenshots/`, it is the
   evidence the verdict points at). Use it for what the a11y tree can't carry: layout, overlap,
   density, the almanac identity holding together.

4. **Check the console** — `browser_console_messages`. **Any console error is a finding**, even
   if the page looks fine.

5. **Judge against intent.** Per-state intent notes (supplement with `$ARGUMENTS`):
   - every state: question box present with sample chips; statement sentence names the scenario;
     headline figure; numbered steps; assumption rows with tag pills; expanding a row reveals the
     plain-English explanation *and* what the source is; unsourced rows keep their warning.
   - combos: 8 combination steps + capital verdict; statement names both components.
   - fallback: with the service unreachable, submitting the question shows the notice and the
     form flow still answers.

6. **Record the verdict — findings first.** A finding is recorded as a **fail before** you fix
   it (the fail record is history, not embarrassment):

   ```sh
   python tools/verify_web.py record <state> --result fail --screenshot .verify/screenshots/<state>.png --note "<finding>"
   # fix -> re-run steps 2-5 -> then:
   python tools/verify_web.py record <state> --result pass --screenshot .verify/screenshots/<state>.png
   ```

   A **fresh failing verdict blocks the Stop gate** exactly like failing render evidence.
   Verdicts go stale (and stop counting) when `web/` changes — same content-hash rule as the
   render evidence. The gate itself stays deterministic and token-free: it only reads what you
   record here; it never drives a browser or calls a model.

## The two layers

| | `/verify-web-page` (this) | `/verify-web` |
|---|---|---|
| Layer | Agent perception, **build loop** | Deterministic render **gate** |
| Sees | Layout, a11y tree, console, visual judgment vs intent | DOM markers, parity banner, JS errors |
| Verdict | Judged punch list → `record` | Hard pass/fail in `evidence.json` |
| When | While building UI; before ending web turns | Every `web/` change (Stop hook enforced) |
