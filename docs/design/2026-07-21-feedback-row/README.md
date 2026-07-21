# The feedback row (S4) — what looking at it caught

Screenshots that decided the shape of the feedback row, from
`docs/plans/2026-07-20-001-feat-minimal-user-feedback.md` slice S4. Driven at 127.0.0.1:8790 with
the real service running, so the events in these shots actually reached the log.

## The finding

| | |
|---|---|
| `01-note-box-open-on-load-FAIL.png` | **The bug.** The optional note textarea and SEND button rendered on page load. |
| `02-row-at-rest-PASS.png` | **Fixed.** One quiet line: the question and two thumbs, nothing else. |
| `03-row-after-thumb-click.png` | After clicking 👎 — thumb inverts, the box appears, focus lands in it. |

The cause was one CSS line. `#fb-note` carries the `hidden` attribute, but `.fb-note {
display:flex }` is a class rule and beats the user-agent's `[hidden] { display:none }`, so the
element stayed visible. The fix is an explicit `.fb-note[hidden], .fb-thanks[hidden] {
display:none }` in `web/index.html`.

**Why this mattered enough to record.** It isn't a cosmetic slip — it inverts the design. The whole
point of the row is *click first, text second*: nobody types into a box they weren't invited to,
and the thumb's real job is to be the visible signal that feedback is wanted here. A note box that
is already open on landing is a form sitting on the estimate, which is precisely the "separate
feedback box" the plan ruled out. Every test passed while this was broken — the deterministic
verifier checks that states render and parity holds, not that an element which should be hidden
is. Only looking caught it.

## Why the row looks the way it does

The page's design system (the comment at the top of `web/index.html`) spends its entire hue budget
on the NPV sign and the three provenance tags, and names density as the constraint. So this row
introduces no accent, no card, and no third font — it borrows the `.sample`/`.linkbtn` idiom
exactly, sits flush under `#result` with `border-top:none`, and reads as a continuation of the
statement rather than a widget parked beside it. Pressed state is inversion (ink background), the
same affordance the rest of the page uses.

It also lives *outside* `#result` in the markup, which is a correctness constraint rather than a
style one: `render()` rewrites that card's `innerHTML` on every recompute, and a note box inside it
would lose a half-typed sentence the moment anything changed.
