---
description: Verify the static web mirror works — drive every option in a real browser, capture evidence, and clear the Stop gate.
---

# /verify-web

The one action that makes "the website works" an **observed, evidenced** fact, not a claim. Run this
after any change to `web/` (and any time you want to reproduce a rendering bug). This is the
**deterministic gate** half of the two-layer verification model; the judged, agent-driven half is
`/verify-web-page`.

## Steps

1. **Run the loop:**

   ```sh
   python tools/verify_web.py run
   ```

   This drives all seven option states (community, balcony, rooftop, battery, plugin-battery,
   battery+rooftop, battery+balcony) in a headless chromium-family browser (Chrome, Chromium, or Edge — discovered
   on any OS), asserts each renders a result **and** that the on-load parity self-check did not
   fire, exercises the agent-fallback path (fetch disabled → notice + form flow), captures a
   screenshot per state under `.verify/screenshots/`, and writes a hashed evidence record to
   `.verify/evidence.json`. It exits non-zero if any state has a problem.

2. **Look at the evidence.** Open the screenshots and confirm the page looks right — layout, the
   headline figure, the statement sentence, the assumption ledger with its expanders. The gate
   proves the loop *ran*; your eyes confirm it ran *well*. For a judged, recorded version of that
   looking, run `/verify-web-page <state>`.

3. **If a problem was reported:** fix it in `web/` (remember `web/app.js` mirrors the Python source
   of truth — a parity failure means the JS formula diverged from `src/`), then re-run step 1. Only a
   clean `run` writes `result: pass`.

4. **Confirm the gate is clear** (optional — the Stop hook runs this for you at end of turn):

   ```sh
   python tools/verify_web.py check   # exit 0 == verified & fresh
   ```

## How it relates to the rest

- `pytest tests` — the **formula** metric (Python source of truth + the parity/gate logic).
  `/verify-web` is the **rendering** metric (the page actually works in a browser).
  `/verify-web-page` is the **perception** metric (the page reads right, judged and recorded).
- The **Stop gate** (`.claude/hooks/verify_web_gate.py`) blocks end-of-turn if `web/` changed without
  fresh passing evidence — and also on any *fresh failing perception verdict* recorded via
  `python tools/verify_web.py record`. Freshness is by content hash, so editing `web/` after
  verifying re-arms the gate until you verify again. Definition of done for web work: a passing
  `.verify/evidence.json` whose hashes match the current `web/` files, with no fresh failing
  perception verdicts in `.verify/perception.json`.
- Evidence lives in gitignored `.verify/` — it's session proof for review, not history.
