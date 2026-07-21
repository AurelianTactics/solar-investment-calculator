# Backlog

Ideas captured, not committed. Pulled from the original concept, `STRATEGY.md`, and the Phase 1 brainstorm (`docs/brainstorms/community-solar-poc-requirements.md`). Nothing here is scheduled — don't pull an item into work without a deliberate decision.

## Solar options to model (beyond community solar)

- **Rooftop solar** — brings the capital-allocation / NPV / payback / opportunity-cost engine that is the `STRATEGY.md` centerpiece. Needs generation, system sizing, and net-metering rules.
- **Balcony / plug-in solar** — small upfront cost, modest bill offset.
- **Battery storage** — adds energy-security / backup value beyond pure ROI; pairs with rooftop or balcony.
- ~~**Combinations** — community + rooftop + battery, etc., compared side by side.~~ **Done
  (2026-07-09):** battery+rooftop and battery+balcony shipped as additive stream combos
  (`src/combo.py`; see `docs/options-integration-notes.md`). Still open here: side-by-side
  *comparison views* and community-inclusive combinations.

## Utility / billing depth

- **Plug-in battery: the over-the-line ("rescue") case.** *Deferred 2026-07-20.* The plug-in
  battery option now models exactly one situation — a home whose on-peak share is already under
  the 15.8% TOU line, where enrolling lowers the bill on its own and the battery adds arbitrage on
  top. Over the line the whole calculation changes: the baseline is the flat rate, not TOU, so the
  battery must first claw back the enrollment penalty before TOU wins at all, and the break-even
  installed cost *falls* as the on-peak share worsens ($908/kWh at 16% → $581 at 25% → $363 at
  40%, from `plugin-battery-answers.md`). Presenting both through one set of outputs is what made
  the option unreadable ("Case 1/2/3" meant nothing to a reader), so the code now refuses over the
  line rather than half-answering. Reviving it needs a UI answer first — probably a separate
  question ("your evenings are expensive; can a battery rescue you?") rather than a branch inside
  one result — plus the honest caveat that winter electric heat is the on-peak load a small
  plug-in usually *can't* reach. The math itself is preserved in `src/tou.py` (case 3) and in git
  history at `071b18b`.
- **Installed battery's `tou_enrolled` mode still speaks in cases.** `src/battery.py` keeps the
  three-case branch and names "Case 2 / Case 3" in its step labels. It's off by default and a
  secondary mode, so it wasn't touched by the 2026-07-20 plug-in simplification — but the same
  readability complaint applies if that mode ever becomes prominent.
- CMP vs Versant billing mechanics, side by side.
- Time-of-use rates and base-load-based billing options (e.g., CMP TOU discount).
- How each utility bills the customer (supply vs delivery split, net-energy-billing credit rules).

## Input & ingestion

- Advanced input: line-item bill breakdown, monthly history, zip, $/kWh, past X months.
- Bill ingestion: photo or PDF upload, auto-scan line items, user confirms or edits the parsed boxes.

## Research & automation

- Automated research bot — the eventual automated form of the `solar-investment-research` repo. Build only once the manual research path has been walked enough to know its shape.
- ~~MCP server exposing the calculator and/or research as tools.~~ **Done (2026-07-20):** the
  calculator half shipped — `list_options` / `get_assumptions` / `calculate` / `compare` over
  `service/tools_core.py`, stdio locally and streamable HTTP at `/mcp` on the deploy, with no LLM
  on the path (`service/mcp_server.py`; W5 of `docs/plans/2026-07-15-001-feat-poc-closeout-plan.md`).
  Still open here: exposing the **research** repo as tools.

## Reach & adjacency

- Other ways to reduce the bill: Efficiency Maine programs, heat-pump payback calculator.
- Other states beyond Maine.
- Commercial / business use cases.
- Native mobile app (beyond the website).

## Agent-native & self-improvement

- Full agent-native parity across all UI and tooling.
- Harness + context for the agent to extend and improve the project more efficiently.

## Misc

- ROI and alternative investments
- inflation
- other reasons for investment: energy security, disaster resiliance etc
- how accurate other pats can be: gather bills and see, projections versus reality
- keeping up with legislation chagnes
- other states
- not just residential
- Not just a website but an app
- Complementary repo that researches key things and this repo can read findings. Ie how the bill is calculated, various projects, other tools out there
- Other ways to reduce the electricity bill (efficiency maine ideas and back back calculator)
- harness and context so agent can self improve itself in a more efficient way
- Full agent native https://every.to/guides/agent-native
