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

- CMP vs Versant billing mechanics, side by side.
- Time-of-use rates and base-load-based billing options (e.g., CMP TOU discount).
- How each utility bills the customer (supply vs delivery split, net-energy-billing credit rules).

## Input & ingestion

- Advanced input: line-item bill breakdown, monthly history, zip, $/kWh, past X months.
- Bill ingestion: photo or PDF upload, auto-scan line items, user confirms or edits the parsed boxes.

## Research & automation

- Automated research bot — the eventual automated form of the `solar-investment-research` repo. Build only once the manual research path has been walked enough to know its shape.
- MCP server exposing the calculator and/or research as tools.

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
