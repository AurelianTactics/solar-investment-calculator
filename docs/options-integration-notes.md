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

## Status

All six roadmap option states are modeled (community, balcony, rooftop, battery, battery+rooftop,
battery+balcony), each on the shared assumption model + (for capital options) the capital engine,
each with a hand-verified worked example in the test suite, a `--option` CLI path, and a mirrored
`web/app.js` entry in the on-load parity self-check. Every assumption now carries a newcomer-grade
`explain`, and every sourced default's source carries `what_is_it`.
