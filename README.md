# Solar Options

App for calculating renewable energy options for Maine residents. Proof of concept deployed at: https://solar-options.up.railway.app/

Arose from a community meeting where community solar, rooftop solar, and plug-in solar were discussed. I wondered what was best for me and my budget?
What would have the highest return on investment? Would I be able to save money with these options?

The tool compares solar and battery options. Key components:
* Cascades from high level question with simple text box interface "Compare Community Solar vs Balcony / Plug-In Solar vs Rooftop Solar on a $168.41 monthly bill" to granular detail where user can optionally input details like annual kWh usage, opportunity cost, size of system, and local billing information. Example: "What would I save using Community Solar, given that I had 3000 kWh of usage, I am a CMP customer, and the offer is a 15% subscription discount?"
* All assumptions and information should be fact checked and contain a trusted source. Rather than estimate the kWh cost, get the actual number from the utility and provide a link. Formulas and process are verified with trusted information and links so users can fact check.
*  Use AI, LLMs, and agentic systems to silently enhance the user experience. User enters what information they feel like specifying, and the agentic system returns requested response. Allows user to avoid time-consuming configs and clicks (though the user still can) and avoid potentially grating AI interactions.
*  Deployed MCP and agent native software design so agentic systems may interact with the app and access all tools.

# Technical Information
## Run the website locally

```sh
python -m http.server --directory web 8000     # then open http://localhost:8000
```

**The "Ask" question box can use an LLM to route options** — turns a typed
question into an answer. Without it the page still works fully: it falls back to the classic form
flow (option toggles + editable assumptions) with a notice. To power the question box, do the
one-time setup in [`service/README.md`](service/README.md) (uv venv outside the repo +
`ANTHROPIC_API_KEY`), then:

```sh
%USERPROFILE%\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe service\app.py    # serves http://127.0.0.1:8765
```

## CLI

The CLI is stdlib-only Python 3 — no setup:

```sh
python src/cli.py --bill 150
```

## Test Suite and Verification
[`docs/how-to-use-and-verify.md`](docs/how-to-use-and-verify.md).
