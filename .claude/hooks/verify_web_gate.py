#!/usr/bin/env python3
"""Stop-hook gate: block end-of-turn while the web mirror has unverified changes.

Thin wrapper around `tools/verify_web.py check` (the deterministic, browser-free gate). Posture
mirrors the avird verification pipeline:

  - respects `stop_hook_active` so it can never cause an infinite block loop;
  - fails CLOSED on stale/missing/failed evidence (exit 2 -> Claude Code blocks the stop and feeds
    the reason back to the model);
  - fails OPEN on any infrastructure error (a broken gate must not brick the session) -> exit 0.

The gate only reads artifacts; it never launches a browser. Verifying (running the browser loop and
reviewing screenshots) is the model's job via `/verify-web`.
"""

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXIT_BLOCK = 3  # tools/verify_web.py check's "gate blocks" code


def main() -> int:
    # Read the Stop payload; never crash on a malformed/empty one.
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Loop prevention: if this stop was already triggered by a Stop hook, allow it.
    if payload.get("stop_hook_active"):
        return 0

    check = os.path.join(REPO_ROOT, "tools", "verify_web.py")
    if not os.path.exists(check):
        return 0  # nothing to enforce -> fail open

    try:
        proc = subprocess.run(
            [sys.executable, check, "check"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
    except Exception as e:  # noqa: BLE001 — infra error must fail open, loudly
        print(f"[verify_web_gate] gate skipped (infrastructure error: {e})", file=sys.stderr)
        return 0

    if proc.returncode == EXIT_BLOCK:
        # Block the stop: exit 2 + reason on stderr is the Claude Code Stop-hook block contract.
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return 2

    # Pass (0) or an infra code from check -> allow the stop.
    return 0


if __name__ == "__main__":
    sys.exit(main())
