#!/usr/bin/env python3
"""Evidence-backed verification loop for the static web mirror (web/).

The site is a static `file://` page whose JS (web/app.js) is a faithful mirror of the Python
source of truth and runs an on-load *parity self-check* over every option's worked example. This
tool makes "the website works" an **observed, evidenced** fact rather than a claim: it drives each
option in a real headless browser (chromium), asserts the page renders and the parity self-check
did NOT fire, and writes checkable artifacts (screenshots + a hashed evidence record) under a
gitignored `.verify/`.

Two subcommands, mirroring the avird local-verification pipeline (right-sized for a static site —
no DB, no dev server):

  run     drive every option in chromium, capture evidence, write .verify/evidence.json
  check   deterministic, browser-free gate: pass only if evidence exists, passed, and its file
          hashes still match the current web/ files (freshness = content hash, not timestamp)

Design posture (borrowed from the avird plan): the gate is deterministic and token-free; it reads
artifacts, it never drives the browser. It fails CLOSED on missing/stale/failed evidence and is
meant to be wrapped by a Stop hook. `run` fails on the first genuine render problem so "done" can't
be claimed over a broken page.

Stdlib only — no third-party deps, consistent with the project.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

# Files whose content defines "the website". A change to any of these invalidates prior evidence.
WEB_FILES = ["web/index.html", "web/app.js"]

# Options the page exposes (mirror of the OPTIONS registry in web/app.js) — all six R4 states.
OPTIONS = ["community", "balcony", "rooftop", "battery", "battery+rooftop", "battery+balcony"]
# Page states the browser loop drives: every option, plus the side-by-side comparison view
# (entered via the global selectCompare(); every compared option renders its own ledger section).
STATES = OPTIONS + ["compare"]
# The options the "compare" state drives. Two is enough to prove the shared-inputs/per-option
# split renders; the six-way case is the same code path with more rows.
COMPARE_STATE_KEYS = ["balcony", "community"]

VERIFY_DIR = ".verify"
EVIDENCE_PATH = os.path.join(VERIFY_DIR, "evidence.json")
# Judged verdicts from the agent perception loop (/verify-web-page). Judgment happens during
# evidence PRODUCTION; this file is only read (never produced) by the deterministic gate.
PERCEPTION_PATH = os.path.join(VERIFY_DIR, "perception.json")

# Exit codes (shared contract with the Stop-hook wrapper).
EXIT_OK = 0
EXIT_RUN_FAIL = 1     # run: a render/parity problem was observed
EXIT_INFRA = 2        # tooling problem (e.g. chromium missing / unreadable evidence)
EXIT_BLOCK = 3        # check: evidence missing, failed, or stale -> the gate blocks


# --------------------------------------------------------------------------- pure helpers

def repo_root() -> str:
    """Repo root = the parent of this tools/ directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blob_hash(data: bytes) -> str:
    """git's blob object id for `data` (sha1 of 'blob <len>\\0<content>').

    Matches `git hash-object` exactly, but needs no git — so the gate works in a bare checkout.
    """
    header = b"blob %d\0" % len(data)
    return hashlib.sha1(header + data).hexdigest()


def file_hashes(root: str) -> dict[str, str]:
    """{relpath: blob_hash} for every WEB_FILE that exists under `root`."""
    out: dict[str, str] = {}
    for rel in WEB_FILES:
        p = os.path.join(root, rel)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                out[rel] = blob_hash(fh.read())
    return out


def build_driver(index_src: str, state: str) -> str:
    """index.html with an injected shim that drives `state` after load and records JS errors.

    Relies on web/app.js being a classic script, so selectOption()/selectCompare() are globals.
    The shim disables fetch and clicks Ask, so the agent-fallback path is exercised
    DETERMINISTICALLY — evidence never depends on whether the local service happens to be up.
    ORDER MATTERS: the fallback now locally ANSWERS the asked question (it re-routes the view to
    whatever the default question says), so Ask fires first and the state under test is selected
    on a later timer, after the fetch rejection's microtask fallback has rendered. The notice
    stays visible across selection, so both the fallback and the state are asserted from one DOM.
    The probe's data-err carries any window error or shim throw, so the headless DOM dump alone
    tells us whether the page ran cleanly.
    """
    select_js = ("selectCompare([%s]);" % ",".join(repr(k) for k in COMPARE_STATE_KEYS)
                 if state == "compare" else "selectOption(%r);" % state)
    shim = (
        "<script>\n"
        "window.__err='';\n"
        "window.addEventListener('error',function(e){window.__err=String((e&&(e.message||e.error))||'error');});\n"
        "window.addEventListener('load',function(){\n"
        "  try{ window.fetch=function(){ return Promise.reject(new TypeError('verifier: service disabled')); };\n"
        "       document.getElementById('ask').click(); }catch(e){ window.__err='ask:'+(e&&e.message||e); }\n"
        "  setTimeout(function(){\n"
        "    try{ %s }catch(e){ window.__err='select:'+(e&&e.message||e); }\n"
        "  }, 60);\n"
        "  setTimeout(function(){\n"
        "    var s=document.createElement('div'); s.id='__probe'; s.setAttribute('data-err',window.__err);\n"
        "    s.setAttribute('data-opt',%r); document.body.appendChild(s);\n"
        "  }, 160);\n"
        "});\n"
        "</script>\n"
    ) % (select_js, state)
    if "</body>" in index_src:
        return index_src.replace("</body>", shim + "</body>", 1)
    return index_src + shim


def probe_error(dom: str) -> str:
    """Extract the data-err value the shim wrote, or '' if absent/empty."""
    marker = 'id="__probe"'
    i = dom.find(marker)
    if i == -1:
        return "__probe element missing (page JS never reached load)"
    key = 'data-err="'
    j = dom.find(key, i)
    if j == -1:
        return ""
    j += len(key)
    k = dom.find('"', j)
    return dom[j:k] if k != -1 else ""


def assert_render(state: str, dom: str) -> list[str]:
    """Return a list of problems found in the dumped DOM for `state` ([] == clean)."""
    problems: list[str] = []
    if "self-check FAILED" in dom:
        problems.append("parity self-check FAILED (web formula diverged from the Python worked example)")
    err = probe_error(dom)
    if err:
        problems.append(f"JS error: {err}")
    if state == "compare":
        # comparison view: the table renders, both rows are present, and EVERY compared option has
        # its own ledger section — a comparison you can only refine one half of isn't one.
        if 'class="cmp-table"' not in dom:
            problems.append("comparison table missing (.cmp-table) — selectCompare did not render")
        for label in ("Balcony", "Community"):
            if label not in dom:
                problems.append(f"comparison row missing: {label}")
        for key in COMPARE_STATE_KEYS:
            if f'data-sec="{key}"' not in dom:
                problems.append(f"no refine section for the {key} row (details.opt-sec[data-sec="
                                f"{key}]) — that row can't be refined without leaving the comparison")
        if 'class="step-label"' not in dom:
            problems.append("compared options' ledgers missing (.step-label) — compare detail did not render")
    else:
        if 'class="big"' not in dom:
            problems.append("no headline figure rendered (.big missing) — result did not compute")
        if 'class="step-label"' not in dom:
            problems.append("no calculation steps rendered (.step-label missing)")
        # option-specific marker that the right branch of render() ran
        if state == "community":
            if "saved" not in dom:
                problems.append("community headline missing '/yr saved' suffix")
        else:
            if "upfront" not in dom:
                problems.append(f"{state} headline missing 'upfront' / NPV verdict line")
    # question-first layout markers (R1): the question box must exist in every state
    if 'id="question"' not in dom:
        problems.append("question box missing (#question) — question-first layout broken")
    # R7: the shim asked with fetch disabled, so the no-agent fallback must have fired
    # (every fallback notice — parsed local answer or classic form — contains this marker)
    if "without the agent" not in dom:
        problems.append("fallback notice missing — ask-with-no-service did not degrade to the no-agent flow")
    return problems


def evaluate_gate(evidence: dict | None, current: dict[str, str]) -> tuple[bool, list[str]]:
    """Deterministic gate decision. Returns (passed, reasons-to-block)."""
    if not evidence:
        return False, ["no web verification evidence found"]
    reasons: list[str] = []
    if evidence.get("result") != "pass":
        bad = [o for o, r in (evidence.get("options") or {}).items() if r.get("problems")]
        reasons.append("last verification did not pass" + (f" (options: {', '.join(bad)})" if bad else ""))
    recorded = evidence.get("file_hashes") or {}
    changed = [f for f in WEB_FILES if current.get(f) != recorded.get(f)]
    if changed:
        reasons.append("web files changed since last verification (stale): " + ", ".join(changed))
    return (not reasons), reasons


def evaluate_perception(perception: dict | None, current: dict[str, str]) -> list[str]:
    """Reasons the perception record blocks the gate.

    A FRESH failing verdict (its recorded hashes match the current web/ files) blocks like any
    failing evidence: record fail -> fix -> re-run -> record pass (the fail record is history,
    not embarrassment). Stale verdicts — pass or fail — are ignored: web/ changed since they
    were judged, so they say nothing about the current page. No perception record at all is
    fine; the deterministic render loop remains the hard floor.
    """
    if not perception:
        return []
    reasons: list[str] = []
    for state, rec in sorted((perception.get("states") or {}).items()):
        if rec.get("file_hashes") == current and rec.get("result") == "fail":
            note = rec.get("note") or ""
            reasons.append(f"perception verdict FAIL for '{state}'"
                           + (f": {note}" if note else "")
                           + " — fix, re-run the loop, then record a pass")
    return reasons


# --------------------------------------------------------------------------- chromium

def _well_known_browsers() -> list[str]:
    """Chromium-family binaries in their per-OS default locations (Linux, Windows, macOS).

    Order encodes preference: Chrome/Chromium first, Edge (chromium-based, ships with Windows)
    as the fallback that makes the loop runnable on a stock Windows machine.
    """
    paths = [
        # Linux
        "/snap/bin/chromium", "/usr/bin/chromium", "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    # Windows: Chrome then Edge, under every root they install to.
    win_roots = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    for root in [r for r in win_roots if r]:
        paths.append(os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"))
    for root in [r for r in win_roots if r]:
        paths.append(os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"))
    return paths


def find_chromium() -> str | None:
    """Find a chromium-family browser on any OS: PATH names first, then well-known locations."""
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
                 "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    for p in _well_known_browsers():
        if os.path.exists(p):
            return p
    return None


def _chromium_base(chromium: str) -> list[str]:
    return [chromium, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars"]


def dump_dom(chromium: str, file_url: str, timeout: int = 60) -> str:
    cmd = _chromium_base(chromium) + ["--virtual-time-budget=5000", "--dump-dom", file_url]
    # The DOM is UTF-8 regardless of the console codepage (Windows defaults to cp1252).
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                         encoding="utf-8", errors="replace")
    return res.stdout


def screenshot(chromium: str, file_url: str, out_path: str, timeout: int = 60) -> bool:
    cmd = _chromium_base(chromium) + [
        "--force-device-scale-factor=1", "--virtual-time-budget=5000",
        "--window-size=820,2200", f"--screenshot={out_path}", file_url,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


# --------------------------------------------------------------------------- subcommands

def cmd_run(root: str) -> int:
    chromium = find_chromium()
    if not chromium:
        print("[infra] no chromium-family browser found (looked for chromium/chrome/msedge on "
              "PATH and in the default Linux/Windows/macOS locations).", file=sys.stderr)
        print("        Install Chrome, Chromium, or Edge to run the browser verification loop.",
              file=sys.stderr)
        return EXIT_INFRA

    vdir = os.path.join(root, VERIFY_DIR)
    shots = os.path.join(vdir, "screenshots")
    drivers = os.path.join(vdir, "_drivers")
    os.makedirs(shots, exist_ok=True)
    os.makedirs(drivers, exist_ok=True)

    # app.js must sit next to each driver so `<script src="app.js">` resolves.
    shutil.copy2(os.path.join(root, "web", "app.js"), os.path.join(drivers, "app.js"))
    with open(os.path.join(root, "web", "index.html"), encoding="utf-8") as fh:
        index_src = fh.read()

    print(f"verify_web: driving {len(STATES)} states in {os.path.basename(chromium)} (headless)\n")
    results: dict[str, dict] = {}
    overall_ok = True
    for opt in STATES:
        driver_path = os.path.join(drivers, f"render-{opt}.html")
        with open(driver_path, "w", encoding="utf-8") as fh:
            fh.write(build_driver(index_src, opt))
        url = pathlib.Path(driver_path).as_uri()  # correct file:// form on every OS

        try:
            dom = dump_dom(chromium, url)
        except subprocess.TimeoutExpired:
            results[opt] = {"rendered": False, "problems": ["chromium timed out"], "screenshot": None}
            print(f"  [fail] {opt:<10} chromium timed out"); overall_ok = False
            continue

        problems = assert_render(opt, dom)
        shot_rel = os.path.join(VERIFY_DIR, "screenshots", f"{opt}.png")
        shot_abs = os.path.join(root, shot_rel)
        try:
            shot_ok = screenshot(chromium, url, shot_abs)
        except subprocess.TimeoutExpired:
            shot_ok = False
        if not shot_ok:
            problems.append("screenshot not produced")

        results[opt] = {
            "rendered": not problems,
            "problems": problems,
            "screenshot": shot_rel if shot_ok else None,
        }
        if problems:
            overall_ok = False
            print(f"  [fail] {opt:<10} " + "; ".join(problems))
        else:
            print(f"  [ok]   {opt:<10} rendered, parity ok, screenshot -> {shot_rel}")

    evidence = {
        "verified_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "result": "pass" if overall_ok else "fail",
        "chromium": chromium,
        "options": results,
        "file_hashes": file_hashes(root),
    }
    with open(os.path.join(root, EVIDENCE_PATH), "w") as fh:
        json.dump(evidence, fh, indent=2)
    print(f"\nevidence -> {EVIDENCE_PATH}  (result: {evidence['result']})")
    return EXIT_OK if overall_ok else EXIT_RUN_FAIL


def _load_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_record(root: str, state: str, result: str, screenshot: str,
               console_errors: int, note: str) -> int:
    """Record one judged perception verdict (the avird `record` convention).

    Honesty guards: the screenshot must actually exist (no verdicts about evidence that was
    never captured), and the verdict is stamped with the current web/ hashes so it goes stale
    the moment the page changes.
    """
    shot = screenshot if os.path.isabs(screenshot) else os.path.join(root, screenshot)
    if not os.path.exists(shot) or os.path.getsize(shot) == 0:
        print(f"[infra] refusing to record: screenshot not found or empty: {screenshot}",
              file=sys.stderr)
        return EXIT_INFRA

    path = os.path.join(root, PERCEPTION_PATH)
    try:
        perception = _load_json(path) or {"states": {}}
    except (json.JSONDecodeError, OSError):
        perception = {"states": {}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    perception.setdefault("states", {})[state] = {
        "result": result,
        "screenshot": os.path.relpath(shot, root),
        "console_errors": console_errors,
        "note": note,
        "file_hashes": file_hashes(root),
        "recorded_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(perception, fh, indent=2)
    print(f"recorded: {state} -> {result}" + (f" ({note})" if note else ""))
    return EXIT_OK


def cmd_check(root: str) -> int:
    try:
        evidence = _load_json(os.path.join(root, EVIDENCE_PATH))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[infra] could not read {EVIDENCE_PATH}: {e}", file=sys.stderr)
        return EXIT_INFRA
    try:
        perception = _load_json(os.path.join(root, PERCEPTION_PATH))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[infra] could not read {PERCEPTION_PATH}: {e}", file=sys.stderr)
        return EXIT_INFRA

    current = file_hashes(root)
    passed, reasons = evaluate_gate(evidence, current)
    reasons += evaluate_perception(perception, current)
    if passed and not reasons:
        return EXIT_OK

    print("BLOCKED: the web mirror is not verified.", file=sys.stderr)
    for r in reasons:
        print(f"  - {r}", file=sys.stderr)
    print("\n  Run the verification loop, then review the screenshots:", file=sys.stderr)
    print("      python tools/verify_web.py run      (or /verify-web)", file=sys.stderr)
    print("      open .verify/screenshots/*.png", file=sys.stderr)
    print("  For judged perception verdicts (/verify-web-page):", file=sys.stderr)
    print("      python tools/verify_web.py record <state> --result pass|fail --screenshot PATH",
          file=sys.stderr)
    return EXIT_BLOCK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-backed verification for the web mirror.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="drive every option in chromium and record evidence")
    sub.add_parser("check", help="deterministic gate: pass only on fresh, passing evidence")
    rec = sub.add_parser("record", help="record a judged perception verdict (agent loop)")
    rec.add_argument("state", help="which page state was judged (e.g. community, battery+rooftop)")
    rec.add_argument("--result", choices=["pass", "fail"], required=True)
    rec.add_argument("--screenshot", required=True, help="path to the screenshot judged")
    rec.add_argument("--console-errors", type=int, default=0)
    rec.add_argument("--note", default="", help="finding summary (required reading on a fail)")
    args = parser.parse_args(argv)

    root = repo_root()
    if args.cmd == "run":
        return cmd_run(root)
    if args.cmd == "check":
        return cmd_check(root)
    if args.cmd == "record":
        return cmd_record(root, args.state, args.result, args.screenshot,
                          args.console_errors, args.note)
    return EXIT_INFRA


if __name__ == "__main__":
    raise SystemExit(main())
