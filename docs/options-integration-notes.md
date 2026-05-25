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
