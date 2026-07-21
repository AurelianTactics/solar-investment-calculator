# Options integration notes

Running log of what each capital option's research landed in the calculator, what firmed up, and
what's still open — mirroring `docs/plans/2026-05-25-phase-4-research-integration.md` (community
solar). Newest option last. Source of truth: the per-option Python module + its tests.

---

## Balcony / plug-in solar (2026-05-25)

**Research pulled:** `../solar-investment-research/wiki/calculator-brief/balcony-answers.md`
(all exit booleans `true`) and `wiki/options/balcony-plug-in-solar.md`.

**What landed in the code** — `src/balcony.py` + `balcony_assumptions()`/`capital_assumptions()`
in `src/assumptions.py`, exercised by `tests/test_balcony.py` and the `--option balcony` CLI path:

| Assumption | Default | Tag | Basis |
|---|---|---|---|
| `capacity_kw` | 1.2 | sourced | LD 1730 max (1,200 W) |
| `specific_yield_kwh_per_kw` | 1200 | sourced | Maine PV yield, implied by the OPA anchor |
| `self_consumption_fraction` | 1.0 | modeling choice | OPA anchor implies ~full self-consumption |
| `volumetric_rate_per_kwh` | 0.27 | sourced | CMP per-kWh charge a self-consumed kWh avoids |
| `kit_cost` | 1200 | sourced | U.S. kits ~$1,000-1,500 |
| `electrician_cost` | 300 | **unsourced — pending research** | no sourced figure yet |

Default estimate: a 1.2 kW kit saves **$388.80/yr** on **$1,500** upfront → **~3.9 yr** simple
payback, **NPV +$4,180** at a 7% opportunity rate over 25 yr (solar wins).

**What firmed up.** The model reproduces the OPA's independently-stated **~$388/yr** anchor
(`1,440 kWh × $0.27 ≈ $389`) — the formula-correctness cross-check, same pattern community solar
used against the OPA's "10–15%" range.

**What surprised us (worth surfacing to users).**

1. **Plug-in solar is NOT net-energy-billing-eligible** (LD 1730). Unlike community/rooftop, it
   earns nothing for exported surplus — it only saves on real-time self-consumption. That makes
   `self_consumption_fraction` load-bearing, and it's the one number with no published constant.
2. **It avoids the volumetric rate (~$0.27), not the all-in rate (~$0.306).** Reducing usage never
   touches the fixed monthly charge — the same offset logic as community solar, reached a different
   way (reduced consumption vs. a bill credit).
3. **The capital engine finally bites.** Community solar was $0 capital; balcony is the first option
   with a real payback/NPV. A fast payback on a *small* base — big % return, small dollar return.
4. **A genuinely unsourced shipped default exists** (`electrician_cost`). Good: it exercises the
   `unsourced — pending research` tag in production, not just in a test.

**What's still open (does not block the option).** Self-consumption fraction for a real Maine home;
electrician install cost; mounting derate for railing/vertical placement; product availability and
real price once UL 3700 kits arrive (~fall 2026). All tracked in `balcony-answers.md`.

**Web mirror:** deferred to the single multi-option `web/app.js` pass after rooftop + battery, so
the UI is rewritten once. Until then the website covers community solar; CLI/Python cover all
options. (No JS runtime here — the Python suite is the metric.)

---

## Rooftop solar (2026-05-25)

**Research pulled:** `../solar-investment-research/wiki/calculator-brief/rooftop-answers.md` (all
exit booleans `true`) and `wiki/options/rooftop-solar.md`.

**What landed** — `src/rooftop.py` + `rooftop_assumptions()`, exercised by `tests/test_rooftop.py`
and `--option rooftop`. Defaults: a 5.5 kW system sized to a typical CMP home at **$2.95/W** →
**$16,225** upfront (no federal credit), offsetting 6,600 kWh × $0.27 = **$1,782/yr**, **~9.1 yr**
simple payback, **NPV +$9,811** at 7% over 25 yr.

**What surprised us (the headline).**

1. **The 30% federal credit is GONE for 2026 buyers.** The 25D residential credit **expired Dec 31,
   2025**, so the shipped `federal_itc_pct` default is **0**, not 0.30. This is the most
   counterintuitive number in the whole calculator — every installer quote and online calculator
   still assumes "30% off." Setting it back to 0.30 (e.g. if you beat the deadline) drops payback
   from ~9.1 to ~6.4 yr.
2. **Maine's high electricity price rescues the economics.** Even with $0 federal credit, a
   sized-to-usage system pays back in ~9 yr and clears the 7% opportunity hurdle (NPV > 0) — because
   each offset kWh is worth ~$0.27.
3. **Oversizing is a real penalty.** NEB credits beyond annual usage expire at 12 months, so the
   model caps `effective_kwh` at usage. EnergySage's longer 16.5-yr payback reflects an oversized
   11.26 kW average system; sizing to usage is materially better.

**What's still open.** Third-party-ownership (lease/PPA) economics now that 25D is gone; Maine-
specific rebates; tariff-level NEB export valuation; Versant defaults. Tracked in
`rooftop-answers.md`.

---

## Home battery storage (2026-05-25)

**Research pulled:** `../solar-investment-research/wiki/calculator-brief/battery-answers.md` (all
exit booleans `true`) and `wiki/options/battery-storage.md`.

**What landed** — `src/battery.py` + `battery_assumptions()`, exercised by `tests/test_battery.py`
and `--option battery`. Defaults: a 13.5 kWh Powerwall at **$998/kWh** → **$13,473** upfront (no
federal credit), ~$0 bill savings + a **$200/yr** resilience placeholder → **67-yr** payback,
**NPV −$12,068** over a 10-yr horizon (the market wins).

**What surprised us / what we deliberately modeled honestly.**

1. **This option is supposed to lose on economics — and the calculator says so.** Negative NPV is
   the *correct* output, not a bug. A battery is an insurance/resilience purchase.
2. **Resilience is kept separate from bill savings.** `resilience_value_per_year` is a user-set,
   `unsourced` number; `annual_bill_savings` defaults to ~$0. So the pure-economics picture never
   hides behind a subjective number — the user sees both and decides.
3. **Different horizon.** Battery uses a **10-yr** warranty horizon (overriding the 25-yr PV
   default from `capital_assumptions()`), so the CLI builder order is capital-then-battery.
4. **The 25D credit took batteries down with it** — same Dec-31-2025 expiry, so `federal_itc_pct`
   defaults to 0 here too.

**What's still open.** A defensible dollar value for resilience (Maine outage frequency/duration);
real Maine arbitrage/TOU potential; battery+rooftop pairing economics; in-horizon degradation.
Tracked in `battery-answers.md`.

---

## Combined options: battery+rooftop and battery+balcony (2026-07-09)

**Research pulled:** none new — the combos deliberately ship on the *components'* landed research.
The one genuinely new economic quantity (pairing interaction) has **no** landed research, and the
model says so out loud.

**What landed** — `capital.combine()` (stream-summing engine helper), `src/combo.py` (one
mechanism), `src/battery_rooftop.py` + `src/battery_balcony.py` (thin configs),
`battery_rooftop_assumptions()`/`battery_balcony_assumptions()`, exercised by
`tests/test_combo.py` and `--option battery+rooftop` / `--option battery+balcony`. Defaults:
battery+rooftop = **$29,698** upfront, **$1,982/yr** year 1, **~15.0 yr** payback, NPV **−$2,258**
at 7% (the battery drags a winning rooftop under water); battery+balcony = **$14,973** upfront,
**$588.80/yr**, NPV **−$7,888**.

**Design decisions that held.**

1. **Stream-wise additive, not parameter-merged.** Each component keeps its own
   escalation/degradation/horizon; `combine()` sums per-year cashflows over the longer horizon and
   derives NPV/payback/verdict from the summed stream. NPV is additive at one rate; **payback is
   not** — the combined 15.0 yr matches neither rooftop's 9.1 nor battery's 67.4, which is exactly
   why payback must come from the combined stream.
2. **Horizon honesty.** Battery cashflows stop contributing after year 10 while PV runs to 25 —
   asserted per-year in the tests (year 11 combined == PV-only).
3. **Key collisions resolved per-component.** Battery keys are `battery_`-prefixed in combo
   assumption dicts (`battery_federal_itc_pct`, `battery_horizon_years`), so the two federal
   credits and two horizons never share a knob.
4. **The interaction slot is honest.** `battery_pv_interaction_value_per_year` defaults to 0,
   tagged `unsourced — pending research`, and rides the battery stream (flat $/yr over battery
   years only). Until research lands pairing economics, the combo is exactly additive.

**What surprised us.**

1. **The combo verdict is a teaching moment.** Rooftop alone wins (+$9,811); adding the battery
   flips the pairing negative. The step chain shows *why* — the battery's −$12,068 stream swamps
   the PV's gain — which is precisely the transparent answer a "should I add a battery?" shopper
   needs.
2. **Windows console encoding bit the CLI.** Rendering a combo's assumptions (with a `≥` in a
   source note) crashed under cp1252; `cli.py` now degrades to replacement characters instead of
   crashing.

**What's still open (does not block the combos).** Real pairing-interaction economics
(battery uplift to PV self-consumption under NEB) — the research repo owns that; the assumption
slot is ready. In-horizon battery degradation remains open from the battery option.

---

## Battery refresh + plug-in DER option (2026-07-19)

**Research pulled:** `../solar-investment-research/wiki/calculator-brief/handoff-2026-07-16.md`,
the refreshed `battery-answers.md` (last_updated 2026-07-16), and the new
`plugin-battery-answers.md`.

**What landed.**

1. **Stale-claim fix.** `annual_bill_savings`' note no longer says "No strong residential TOU
   arbitrage" — one exists (CMP Rate TOU, eff. 2026-07-01), conditional and delivery-only, and
   now lives behind the off-by-default `tou_enrolled` mode instead of being denied.
2. **`tou_arbitrage` mode** (`src/tou.py`, shared by battery and plugin-battery): the master
   equation `U×0.058120 − R×0.367366` with the three-case branch — Case 1 threshold (TOU beats
   flat iff on-peak share < 0.1582 = discount/penalty), Case 2 gravy (baseline TOU-alone; battery
   earns only shifted×penalty, never the enrollment discount — the double-count the handoff warns
   about), Case 3 rescue (baseline flat; net vs. flat, floored at 0). District-aware by editing:
   the rate assumptions' notes carry the Versant Home Eco values (BHD ≈$0.101 / MPD ≈$0.099 thin
   spread, near-zero enrollment risk).
3. **Horizon 10 → 13 + 3%/yr degradation.** `horizon_years` is now the expected LFP service life
   (13), `warranty_years = 10` kept as a separate, display-only risk-window assumption, and
   `annual_degradation = 0.03` flows into `capital.compare`. Verdict unchanged (longer horizon
   adds years of ≈$0); the combo NPV moved from −$2,258 to **−$2,221** (battery+rooftop).
4. **48E two-path federal credit.** `federal_itc_pct` is reframed as a financing-structure
   switch: owner-bought = 0 (25D expired); lease/PPA = 48E survives via the installer (Form
   3468), pass-through % to a Maine homeowner deliberately NOT hardcoded (unsourced).
5. **NEW option `plugin-battery`** (`src/plugin_battery.py` + `plugin_battery_assumptions()` +
   `tests/test_plugin_battery.py` + `--option plugin-battery` + web state): three-case model with
   the battery **sized to the shifted load** (`usable_kwh = coverage×on_peak/250 cycles`), which
   reproduces the brief's Case-3 depth table exactly ($908/kWh break-even at 16% on-peak → $581
   at 25% → $363 at 40%; Case-2 break-even ~$901/kWh from the sourced $90.13/usable-kWh/yr).
   Defaults (6,600 kWh, 25% on-peak, 70% coverage, $600/kWh station): Case 3, 4.62 kWh needed,
   $2,772 upfront, $201.75/yr arbitrage + $200 resilience, NPV **+$50** — the arbitrage alone
   does NOT clear a $600/kWh station (break-even $437/kWh ≈ cheap DIY only); the resilience
   placeholder is what tips it. `installed_cost_per_kwh` and `residual_coverage` ship
   `unsourced — pending research` (deliberately: they exercise the tag in production, like
   balcony's `electrician_cost`).
6. **Web widget.** The plugin-battery page IS the "which TOU case are you in?" widget: shared
   usage box + editable `on_peak_share`, the case named in the headline context line, threshold +
   enrollment-only savings + break-even as steps, and the "a plug-in can't cover winter heat"
   caveat in the Case-3 verdict text.

**What surprised us.** The brief's Case-2 $901/kWh and Case-3 $908-at-16% break-evens rest on
slightly different algebra (Case 2 nets out the 0.90 round-trip loss via `value_per_usable_kwh_yr`;
the Case-3 table and master equation don't) — the calculator follows the brief literally and says
so in the assumption note rather than silently reconciling them.

**What's still open (tracked in the research repo's open-questions).** Plug-in/DIY `$/kWh` and
realistic winter `residual_coverage` (the two unsourced tags); 48E pass-through %; a defensible
resilience dollar value; Versant's fixed-charge delta vs. flat needs a clean apples-to-apples calc.

---

## Plug-in battery scoped to one case (2026-07-20)

**Why.** The option shipped (2026-07-19) modeling all three TOU cases through one set of outputs,
and it read as jargon: the headline named "Case 2 (gravy)" or "Case 3 (rescue)", the step labels
changed formula *and* meaning depending on which case you landed in, and the break-even number
meant two different things ($901/kWh from the sourced per-kWh value in one case; a derived
`arb × horizon ÷ size` in the other). A reader could not tell which situation they were in or why
the numbers on screen had shifted. That's a transparency failure, not a formula bug.

**What changed.** `plugin-battery` now models exactly **one** situation: the home already under
the 15.8% on-peak line, where switching to CMP Rate TOU lowers the bill on its own and the
battery adds arbitrage on top (`shifted_kwh × penalty`, the incremental penalty avoided). One
baseline, one formula per step, one break-even definition.

- `src/plugin_battery.py`: the case branch is gone. Over the line, `compute` raises
  `OutOfScope(ValueError)` with a plain-English explanation naming the line, where the user
  actually is, and where the missing case lives — rather than returning numbers from a model the
  caller didn't ask for. It's a `ValueError` subclass so every existing surface already handles
  it: the CLI prints `cli.py: error: …`, the web mirror renders it as an inline notice, and the
  service returns `compute_error: …` (which the page falls back from).
- `on_peak_share` default **0.25 → 0.12** *for this option only* (`plugin_battery_assumptions()`
  overrides the shared `_tou_shared_assumptions()` value; battery's `tou_enrolled` keeps 0.25, so
  no battery numbers moved). The shipped defaults now describe a home the option actually models.
- Step 2 became a threshold *confirmation* (the on-peak kWh ceiling: `usage × discount ÷ penalty`
  = 1,044 kWh/yr against your 792) instead of a case selector. It reports kWh because the CLI
  step formatter renders non-`$` units at `,.0f` — a fraction-valued step would have printed "0".
- `web/app.js` mirrors all of it, including the refusal; the parity self-check now asserts both
  the new worked example and that over-the-line **throws**.

**New worked example (shipped defaults):** 6,600 kWh, 12% on-peak, 70% coverage, $600/kWh station
→ on-peak 792 kWh, shifted 554.4, enrolling alone $92.64/yr, arbitrage $203.67/yr, 2.2176 kWh
needed, **$1,330.56 upfront**, $403.67/yr with resilience, payback **3.3 yr**, NPV **+$1,505**,
break-even **$901.30/kWh** (a $600 station clears it; a $998 Powerwall doesn't).

**What surprised us.** The verdict got *better*, not worse. The old default (25% on-peak) was a
rescue case whose arbitrage barely cleared the hardware — NPV +$50, carried entirely by the $200
resilience placeholder. The under-the-line default stands on its own economics: NPV is positive
before resilience matters. Modeling the situation the option is actually good at made the option
look good, which is a reminder that a default is a claim about who you're talking to.

**What's open.** The rescue case is backlogged with its UI problem stated (`docs/BACKLOG.md`), and
`src/tou.py` still carries case 3 for battery's `tou_enrolled` mode, so nothing was deleted. The
two unsourced dials (`installed_cost_per_kwh`, `residual_coverage`) are unchanged.

---

## Status

All seven roadmap option states are modeled (community, balcony, rooftop, battery, plugin-battery,
battery+rooftop, battery+balcony), each on the shared assumption model + (for capital options) the
capital engine, each with a hand-verified worked example in the test suite, a `--option` CLI path,
and a mirrored `web/app.js` entry in the on-load parity self-check. Every assumption carries a
newcomer-grade `explain`, and every sourced default's source carries `what_is_it`.
