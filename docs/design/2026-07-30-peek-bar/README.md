# The peek bar — the estimate follows you into the drawer (2026-07-30)

## The problem

`web/app.js` had said for months that the headline "renders into the **sticky** `#result` card, so
the number stays in view while refining below." It was never sticky — no `position` rule existed
for `#result`. The comment described an intent nobody had implemented, and a user reported the gap
directly: they expected the savings to float while they scrolled down to change options.

It matters most exactly where this page is densest. With the refine drawer open, the document is
~3,100 px tall against an ~880 px viewport; the option picker and all 25 `battery+rooftop`
assumptions sit far below the fold. You change the number, and the figure you changed it to move is
off-screen at the moment you move it.

## What shipped

A fixed one-row bar (`#peek`), revealed only once `#result` has scrolled entirely above the
viewport, carrying the same figures as the card it shadows.

- **Tabulated, never recomputed.** `renderPeek()` reads the same result object `render()` /
  `renderCompare()` just rendered from. Verified in-browser: the peek's `$1,782 / $29,698 /
  $-3,662` are string-identical to the card's. A peek that could disagree with the card would be a
  second answer, which is the one thing this page must not have.
- **Reveal rule.** `IntersectionObserver` on `#result`, hidden unless
  `!isIntersecting && boundingClientRect.top < 0`. The `top` check is load-bearing: a card still
  *below* the fold on first paint is also "not intersecting", and without it the bar would flash on
  at the top of the page, duplicating a card in full view two inches beneath it.
- **`aria-hidden`.** Every figure is already in `#result`; a screen reader should hear them once.

## Two judgements made by looking

Both screenshots here are at scroll ≈1,500 px with the drawer open — the state the bar exists for.

1. **NPV is labelled, not just coloured** (`three-way-compare.png` was shot before this change and
   shows the rejected version). The design system puts hue only on NPV sign, so the first build let
   colour carry the whole meaning in compare rows. Read back, a bare green `$4,181` beside a
   labelled `$389 /YR` parses as a second savings figure — colour tells you the sign, not what the
   number *is*. The `npv` label costs ~30 px per option and removes the ambiguity.
2. **One scrolling row, never a wrapping block.** The six-way compare overflows the bar's own
   `overflow-x` container (measured: `scrollWidth > clientWidth`) while `document.body` does **not**
   scroll sideways. Letting it wrap instead would grow a fixed bar into a block that eats the
   viewport it exists to stay out of — so `.peek-in` keeps `white-space:nowrap` on phones too.

## Density check

Judged against `battery+rooftop` (25 assumptions, 9 steps) and the six-way compare, per the
standard in `CLAUDE.md` — not the 4-row community default. The bar is 39 px tall, ~4% of an 880 px
viewport.
