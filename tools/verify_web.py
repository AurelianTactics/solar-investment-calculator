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

VERIFY_DIR = ".verify"
EVIDENCE_PATH = os.path.join(VERIFY_DIR, "evidence.json")

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


def build_driver(index_src: str, option: str) -> str:
    """index.html with an injected shim that selects `option` after load and records JS errors.

    Relies on web/app.js being a classic script, so selectOption() is a global. The shim writes a
    `#__probe` element whose data-err carries any window error or selectOption throw, so the headless
    DOM dump alone tells us whether the page ran cleanly.
    """
    shim = (
        "<script>\n"
        "window.__err='';\n"
        "window.addEventListener('error',function(e){window.__err=String((e&&(e.message||e.error))||'error');});\n"
        "window.addEventListener('load',function(){\n"
        "  try{ selectOption(%r); }catch(e){ window.__err='select:'+(e&&e.message||e); }\n"
        "  var s=document.createElement('div'); s.id='__probe'; s.setAttribute('data-err',window.__err);\n"
        "  s.setAttribute('data-opt',%r); document.body.appendChild(s);\n"
        "});\n"
        "</script>\n"
    ) % (option, option)
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


def assert_render(option: str, dom: str) -> list[str]:
    """Return a list of problems found in the dumped DOM for `option` ([] == clean)."""
    problems: list[str] = []
    if "self-check FAILED" in dom:
        problems.append("parity self-check FAILED (web formula diverged from the Python worked example)")
    err = probe_error(dom)
    if err:
        problems.append(f"JS error: {err}")
    if 'class="big"' not in dom:
        problems.append("no headline figure rendered (.big missing) — result did not compute")
    if 'class="step-label"' not in dom:
        problems.append("no calculation steps rendered (.step-label missing)")
    # option-specific marker that the right branch of render() ran
    if option == "community":
        if "saved" not in dom:
            problems.append("community headline missing '/yr saved' suffix")
    else:
        if "upfront" not in dom:
            problems.append(f"{option} headline missing 'upfront' / NPV verdict line")
    # question-first layout markers (R1): the question box must exist in every state
    if 'id="question"' not in dom:
        problems.append("question box missing (#question) — question-first layout broken")
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

    print(f"verify_web: driving {len(OPTIONS)} options in {os.path.basename(chromium)} (headless)\n")
    results: dict[str, dict] = {}
    overall_ok = True
    for opt in OPTIONS:
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


def cmd_check(root: str) -> int:
    path = os.path.join(root, EVIDENCE_PATH)
    evidence = None
    if os.path.exists(path):
        try:
            evidence = json.load(open(path))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[infra] could not read {EVIDENCE_PATH}: {e}", file=sys.stderr)
            return EXIT_INFRA

    passed, reasons = evaluate_gate(evidence, file_hashes(root))
    if passed:
        return EXIT_OK

    print("BLOCKED: the web mirror is not verified.", file=sys.stderr)
    for r in reasons:
        print(f"  - {r}", file=sys.stderr)
    print("\n  Run the verification loop, then review the screenshots:", file=sys.stderr)
    print("      python3 tools/verify_web.py run      (or /verify-web)", file=sys.stderr)
    print("      open .verify/screenshots/*.png", file=sys.stderr)
    return EXIT_BLOCK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-backed verification for the web mirror.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="drive every option in chromium and record evidence")
    sub.add_parser("check", help="deterministic gate: pass only on fresh, passing evidence")
    args = parser.parse_args(argv)

    root = repo_root()
    if args.cmd == "run":
        return cmd_run(root)
    if args.cmd == "check":
        return cmd_check(root)
    return EXIT_INFRA


if __name__ == "__main__":
    raise SystemExit(main())
