---
title: "feat: make a broken deploy impossible to miss"
type: feat
status: ready
date: 2026-07-29
---

# feat: make a broken deploy impossible to miss

## Summary

Four small slices so that the next time the deploy breaks, something says so: a smoke check that
exercises the surfaces the healthcheck doesn't (S1), cache-busted static assets so a deploy
actually reaches returning visitors (S2), a `version` field on `/health` (S3), and a favicon (S4).

Each slice is independently shippable. S1 and S2 are the two that matter.

## Problem Frame

On 2026-07-29, the first verification pass against the live Railway deploy found three failures
that had been true for a week and that nothing had reported:

1. **`/mcp` returned 421 to every request.** `configure_http()` read `RAILWAY_PUBLIC_DOMAIN`, which
   the dashboard lists but the runtime does not inject, so the DNS-rebinding allow-list stayed
   localhost-only. The MCP server — half the point of the project — was unreachable the entire time
   it was "deployed."
2. **The deploy was one rebuild away from death.** `requirements.txt` had floors and no ceilings.
   The first rebuild since 2026-07-21 resolved `mcp>=1.2` to the day-old 2.0.0, which moved
   `mcp.server.fastmcp`; the app failed to import and the site went down. Nothing in the repo had
   changed. The local venv (mcp 1.28.1) could not have caught it, and neither could the tests.
3. **A deployed `web/app.js` did not reach a returning browser.** Verified live: the new file was
   served, the browser used its cached copy. The change being deployed was *instrumentation*, so
   the failure mode is silent — events don't fire and the log looks like nobody edits anything.

The common thread is not "we had bugs." It is that **`/health` returned 200 through all three.**
The healthcheck proves a process is listening. It says nothing about whether the thing that
process exists to do still works.

Both root causes from (1) and (2) are fixed (commit `4bbd568`). This plan is about the detection
gap they exposed.

## Requirements

- **R1 — One command answers "is the deploy actually working."** Not "is it up." It must exercise
  `/`, `/health`, `/ask`, `/events`, and `/mcp`, and fail loudly on any surface that is degraded.
- **R2 — It must be runnable against any origin**, so it works for the live deploy and for a local
  service on `127.0.0.1:8765` with no edits.
- **R3 — It must not cost money by default.** `/ask` is the only paid path. Exercising it is
  valuable and should be opt-in (`--paid`), not the default.
- **R4 — A deploy reaches returning visitors.** A new `web/app.js` must be loaded by a browser
  that has the old one cached, without asking anyone to hard-refresh.
- **R5 — `/health` says which commit it is running.** Diagnosing the 2026-07-29 outage required
  SSH to answer a question the service should volunteer.
- **R6 — Nothing here may become a way for the deploy to fail.** Same posture as `feedback.py`:
  a smoke check is a *reader*. It must never write to the volume or hold a lock.

## S1 — The smoke check (do this first)

`tools/smoke_deploy.py <base-url> [--paid]`, stdlib-only like the rest of `tools/`.

| Check | Passes when | Catches |
|---|---|---|
| `GET /` | 200, body contains the page title | Static mount shadowed or missing |
| `GET /health` | 200, `ok: true`, `log.path` starts `/data` | **The volume not mounted** — the silent killer for instrumentation |
| `POST /mcp` `tools/list` | 200, exactly the four tool names | **The 421 that shipped for a week** |
| `POST /mcp` `tools/call` `calculate` | 200, payload has `steps` + `assumptions` | Tools registered but broken |
| `POST /events` | `{"ok":true,"written":1}` | Event intake dead |
| `POST /events` oversized | `ok:false`, `error:"too_large"` | Caps not enforced |
| `POST /ask` *(only with `--paid`)* | payload has an `option` and non-empty `steps` | Key missing, cap tripped, model unreachable |

Exit non-zero listing every failed check — not the first. The 2026-07-29 pass found three distinct
problems in one run; a check that stops at the first would have hidden two of them.

**Note the `/health` volume assertion.** `log.path` not starting with `/data` means telemetry is
writing to a disk that vanishes on the next deploy, which is indistinguishable from nobody visiting
and is the single most expensive silent failure in the system.

## S2 — Cache-busting static assets

The page loads `app.js` and `styles.css` at fixed paths, and the browser reasonably caches them.

**Approach: a build-time query string, not content hashing.** `?v=<short git sha>` appended in
`web/index.html`, rewritten at deploy time. Content hashing is the better answer for a real asset
pipeline and this project doesn't have one — a sha is one substitution and no new tooling.

The wrinkle worth stating: `web/index.html` must stay directly openable from `file://`, because
the deterministic verifier drives it that way and that is not negotiable. So the substitution has
to degrade to a working relative path when it hasn't been performed — `app.js?v=dev` loads fine.

Alternative if that proves fiddly: send `Cache-Control: no-cache` for `app.js`/`index.html` from
the StaticFiles mount. Weaker (a revalidation round-trip per load) but three lines and no build
step. **Prefer this if S2 threatens to grow past an afternoon** — at this traffic the round-trip
costs nothing and correctness beats efficiency.

## S3 — `/health` reports its commit

Add `version` to the `/health` payload, read once at import from `RAILWAY_GIT_COMMIT_SHA` (which
*is* injected — verified 2026-07-29) with a `git rev-parse` fallback for local runs and `"unknown"`
if both fail. Never let this raise; `/health` failing would trip the Railway healthcheck and
restart the container, which is a spectacular way for a diagnostic to cause an outage.

S1 should print it, so every smoke run records what it tested.

## S4 — Favicon

A 404 on every page load. Add `web/favicon.ico` (or an inline SVG `<link>`). Ten minutes.

## Sequencing

```
S1 smoke check  ──►  S2 cache-busting  ──►  S3 version  ──►  S4 favicon
   (~half a day)      (~half a day)         (~1 hour)        (~10 min)
```

S1 first because it is the one that would have caught all three of the 2026-07-29 failures, and
because S2 and S3 are easier to trust once something checks them.

## Definition of done

- `pytest tests service/tests` passes; `python tools/verify_web.py check` exits 0.
- `python tools/smoke_deploy.py https://solar-options.up.railway.app` exits 0, and exits non-zero
  with a named failure when `SOLAR_MCP_ALLOWED_HOSTS` is unset on the service.
- Deploying a changed `web/app.js` and reloading **without** clearing the cache runs the new code.
- `/health` reports a `version` matching the deployed commit.
- No new 404s in the browser console on load.

## Out of scope

Alerting, uptime monitoring, a status page, CI. This plan makes failure *detectable by running one
command*. Making it detectable without a human is a different decision, and at this traffic the
honest answer is that running the command after each deploy is enough.
