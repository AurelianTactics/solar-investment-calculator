# Live deploy, seen with our own eyes — 2026-07-29

`live-page-4way-compare.png` is the deployed page at `https://solar-options.up.railway.app/`,
driven through the agent perception loop during the first real verification pass. It is the state
after: a thumbs-down with a typed note, the monthly bill edited 168.41 → 220, and Home Battery
Storage added to the default three-way comparison — i.e. a four-way compare with a user-provided
bill.

Kept because looking is what found the things the tests didn't:

- The feedback note box is **closed on load and opens only on a thumb click** — the S4 design, and
  the same regression a previous pass caught by looking (`docs/design/2026-07-21-feedback-row/`).
- The scenario URL accumulated the edited bill and then the added option, which is what makes a
  thumbs-down reproducible rather than noise.
- `assumption_edited` did **not** fire for that bill edit. That is what this session found: the two
  shared inputs recomputed and retagged without ever being tracked, so the sharpest signal in S3 was
  missing exactly where edits are densest. Fixed in `16c1c47`.
- A returning browser kept a **cached `app.js`** after the deploy, so the fix above did not reach
  this page until the HTTP cache was bypassed. Backlogged as Tier 1 — it is the reason an
  instrumentation deploy can silently do nothing at all.

The console shows one error on every load: a 404 for `/favicon.ico`.
