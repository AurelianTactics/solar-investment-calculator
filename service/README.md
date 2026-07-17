# Agent service — natural-language questions → calculator answers

A small local service that turns "What savings would I get with community solar when my bill is
$150 a month?" into the same structured payload `python src/cli.py --json` emits. One
LangGraph graph: **extract** (a single `claude-opus-4-8` structured-output call that picks the
option and pulls out stated numbers) → **compute** (direct `src/` imports — the LLM never does
arithmetic). Local-only by decision; deployment is out of scope.

## Setup (one time)

Dependencies live in a uv venv created **outside the repo** (central location so it's shared
across git worktrees), from the checked-in `requirements.txt` at the repo root:

```powershell
uv venv $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc
uv pip install -r requirements.txt --python $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe
```

The service needs an Anthropic API key (Claude Code's own login does **not** provide one — get a
key at console.anthropic.com). Put it in a **`.env` file at the repo root** — the service loads it
automatically on startup via `python-dotenv`, so you never type the key into the shell:

```dotenv
# .env  (repo root; gitignored)
ANTHROPIC_API_KEY=<your key>
```

A real environment variable, if already set in the shell, wins over the `.env` value. So the
old shell-var approach still works if you prefer it:

```powershell
$env:ANTHROPIC_API_KEY = "<your key>"        # PowerShell, this session only — overrides .env
```

## Run

```powershell
& $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe service\app.py
# -> http://127.0.0.1:8765   (port: SOLAR_AGENT_PORT)
```

Smoke test:

```powershell
curl.exe -s -X POST http://127.0.0.1:8765/ask -H "Content-Type: application/json" `
  -d '{"question": "What savings would I get with community solar when my bill is $150 a month?"}'
```

The numbers must match `python src/cli.py --bill 150 --json` exactly — the service imports the
same core.

## Spending cap

Every response's token usage is priced ($5/$25 per MTok for opus) and accumulated in the
gitignored `service/.spend.json`, so the cap survives restarts. The cap is checked **before**
each LLM call; once reached, `/ask` returns `{"error": "cap_exceeded"}` and the frontend falls
back to the form flow. Configure:

| env var | default | meaning |
|---|---|---|
| `SOLAR_AGENT_SPEND_CAP_USD` | `5.0` | total spend ceiling |
| `SOLAR_AGENT_LEDGER_PATH` | `service/.spend.json` | ledger location |
| `SOLAR_AGENT_PORT` | `8765` | HTTP port |
| `SOLAR_AGENT_ENV_FILE` | repo-root `.env` | which `.env` to auto-load on startup (missing file = no-op) |

Reset the budget by deleting the ledger file (a deliberate act, on purpose).

## Error contract (what the frontend keys on)

| condition | response |
|---|---|
| routable question | CLI-shaped payload + `agent` + `followup` fields |
| off-topic question | `{"error": "unanswerable"}` |
| cap reached | `{"error": "cap_exceeded", "detail": ...}` |
| LLM timeout/failure | `{"error": "llm_error: ..."}` |
| service not running | (no response — the frontend's 4s fetch timeout handles it) |

## Tests

```powershell
& $env:USERPROFILE\claude_code_repos\my-uv-envs\solar-calc\Scripts\python.exe -m pytest service\tests
```

Every test stubs the LLM (the `Agent(extractor=...)` seam) — no network, no key, no spend.
