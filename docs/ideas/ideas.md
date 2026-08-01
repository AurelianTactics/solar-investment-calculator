# Working


# Fixes



# To do


* minimal user feedback plan: something just to store reactions and stats and data from this

# Backlog
* review the formulas better
* oh no, teh claude.md and related cruff keeps growing. Uh oh
* more user testing / planning on it
* leasing / non purchase for batteries and rooftop solar and what that means return wise
* power purchase agreements
* add more states
* be able to validate with mroe power bill examples
* commercial
* regular updates of sources
    * like https://www.maine.gov/energy/electricity-prices was updated on 7/1 . how to periodically check for key things?
* regular tidying up of repo
* need to thing through how I present the financial argument
    * for sure non interest and discount payback return
    * maybe "if I had invested this money, what percent return would I need for equivalent savings"
    * thinking maybe a click through and show all the financial parts to it, NPV, IRR etc.
    * first one
* links to learning about / resources for understanding
* agent native
* ug, this website is stil way too fucking busy
    * still ugly after many iterations ah well
* many more example queries
    * caching / building on existing queries to routes so LLM doesn't have to infer
* can enter zip code or location and get power company and rates maybe
* more interaction and feedback with the agent or the agent soliciting human feedback
    * seems like this should be part of the cacheing fo the LLM
    * some ideas in a plan from uly 2026 but this needs to be fleshed out a bit
* calculation fix
    * What the brief's master equation uses instead. U×0.058120 − R×0.367366 values each shifted kWh at on-peak minus off-peak = $0.367366 — as if charging were lossless. That's about 1.9% too generous.
        * fix in research, then fix in the app
* TOU and plug in battery: only doing one option, this could be expanded
* glossary, terms, and terminology understanding. maybe links to the wiki
* a health check on MCP and other things has been suggested
    * there's still no post-deploy smoke check — /health returned 200 through all three production failures. The tests are good; nothing yet runs them against the deployed URL automatically.
* better testing of the MCP
* MCP and better fat / thin calls and the options
    * defaults to returnign a lot which may or may make sense. like how many times is the prevenance needed
* better testing and usage of feedback stuff
* this is back solved and not sourced. Needs an actual source:
    ❯ 0.27
  $/kWh
  default (sourced)
  What this means
  What each avoided kWh is actually worth to you: the per-unit charges (supply plus delivery) that disappear when your
  panels power the house instead of the grid. It's lower than the all-in price because the fixed monthly charge never
  changes no matter how little you draw.

  source: Maine DOE — CMP per-kWh (volumetric) charges — Self-consumption avoids per-kWh charges, not the fixed
  charge.

  what the source is: The Maine Governor's Energy Office's published electricity-price page — the state government's
  own summary of each utility's current approved rates. The rates are set in public filings with the Maine PUC, so
  this is the authoritative statement of what CMP customers actually pay.
* too much location and source specific notes in the explanations:
    * example of one fixed: "Rates reset every January 1, and Versant territory differs from CMP
* battery has weird stuff in it like this
    Enrolled in the optional time-of-use delivery rate? (0 = no, 1 = yes)
* plug in battery way to specific to facts and not geenral

# Done
