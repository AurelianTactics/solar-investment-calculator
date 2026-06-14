---
description: Verify the static web mirror works — drive every option in a real browser, capture evidence, and clear the Stop gate.
---

# /verify-web

The one action that makes "the website works" an **observed, evidenced** fact, not a claim. Run this
after any change to `web/` (and any time you want to reproduce a rendering bug).

## Steps

1. **Run the loop:**

   ```sh
   python3 tools/verify_web.py run
   ```

   This drives all four options (community, balcony, rooftop, battery) in headless chromium, asserts
   each one renders a result **and** that the on-load parity self-check did not fire, captures a
   screenshot per option under `.verify/screenshots/`, and writes a hashed evidence record to
   `.verify/evidence.json`. It exits non-zero if any option has a problem.

2. **Look at the evidence.** Open the screenshots and confirm the page looks right — layout,
   the headline figure, the assumption ledger, the sources. The gate proves the loop *ran*; your eyes
   confirm it ran *well*.

   ```sh
   # screenshots: .verify/screenshots/{community,balcony,rooftop,battery}.png
   ```

3. **If a problem was reported:** fix it in `web/` (remember `web/app.js` mirrors the Python source
   of truth — a parity failure means the JS formula diverged from `src/`), then re-run step 1. Only a
   clean `run` writes `result: pass`.

4. **Confirm the gate is clear** (optional — the Stop hook runs this for you at end of turn):

   ```sh
   python3 tools/verify_web.py check   # exit 0 == verified & fresh
   ```

## How it relates to the rest

- `python3 -m unittest discover -s tests` — the **formula** metric (Python source of truth + the
  parity/gate logic). `/verify-web` is the **rendering** metric (the page actually works in a browser).
- The **Stop gate** (`.claude/hooks/verify_web_gate.py`) blocks end-of-turn if `web/` changed without
  fresh passing evidence. Freshness is by content hash, so editing `web/` after verifying re-arms the
  gate until you verify again. Definition of done for web work: a passing `.verify/evidence.json` whose
  hashes match the current `web/` files.
- Evidence lives in gitignored `.verify/` — it's session proof for review, not history.
