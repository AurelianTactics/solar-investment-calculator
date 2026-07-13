# Solar Investment Calculator

Turn a Maine homeowner's plain question — *"What savings would I get with community solar when my
bill is $150 a month?"* — into a trustworthy, fact-checkable estimate, with **every number shown as
a labeled, editable, sourced assumption**, never a black box. Six options are modeled: community
solar, balcony/plug-in, rooftop, battery, battery+rooftop, and battery+balcony. Why this exists:
[`STRATEGY.md`](STRATEGY.md).

## Run the website

```sh
python -m http.server --directory web 8000     # then open http://localhost:8000
```

**The "Ask" question box can use an LLM to route options** — that's what turns a typed
question into an answer. Without it the page still works fully: it falls back to the classic form
flow (option toggles + editable assumptions) with a notice. To power the question box, do the
one-time setup in [`service/README.md`](service/README.md) (uv venv outside the repo +
`ANTHROPIC_API_KEY`), then:

```sh
%USERPROFILE%\.venvs\solar-calc\Scripts\python.exe service\app.py    # serves http://127.0.0.1:8765
```

## CLI

The CLI is stdlib-only Python 3 — no setup:

```sh
python src/cli.py --bill 150
```

Everything else — all six options, overriding any assumption, `--json` for agents, the test
suite, and how to *verify* the numbers — is in
[`docs/how-to-use-and-verify.md`](docs/how-to-use-and-verify.md).
