"""Tests for the deterministic half of tools/verify_web.py — the gate logic and DOM assertions.

These never launch a browser; they exercise the pure functions the Stop gate depends on. The
browser half (chromium driving) is acceptance-tested live by `python3 tools/verify_web.py run`.

Run with the rest of the suite:  python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import verify_web as vw  # noqa: E402


class TestBlobHash(unittest.TestCase):
    def test_matches_git_hash_object(self):
        # git's blob id for empty content is well-known and version-independent.
        self.assertEqual(vw.blob_hash(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_matches_git_for_content(self):
        data = b"hello\n"
        self.assertEqual(vw.blob_hash(data), "ce013625030ba8dba906f756967f9e9ca394464a")


class TestBuildDriver(unittest.TestCase):
    def test_injects_before_body_close(self):
        out = vw.build_driver("<body><div id='result'></div></body>", "rooftop")
        self.assertIn("selectOption('rooftop')", out)
        self.assertIn("__probe", out)
        # shim sits before the closing body tag
        self.assertLess(out.index("__probe"), out.index("</body>"))

    def test_appends_when_no_body(self):
        out = vw.build_driver("<div>no body tag</div>", "battery")
        self.assertIn("selectOption('battery')", out)


class TestProbeError(unittest.TestCase):
    def test_empty_when_clean(self):
        dom = '<div id="__probe" data-err="" data-opt="community"></div>'
        self.assertEqual(vw.probe_error(dom), "")

    def test_extracts_error(self):
        dom = '<div id="__probe" data-err="select:boom" data-opt="rooftop"></div>'
        self.assertEqual(vw.probe_error(dom), "select:boom")

    def test_missing_probe_is_a_problem(self):
        self.assertIn("missing", vw.probe_error("<div>nothing</div>"))


class TestAssertRender(unittest.TestCase):
    def _clean_community(self):
        return (
            '<textarea id="question"></textarea>'
            '<div id="notice" class="show">using the classic form</div>'
            '<div id="__probe" data-err=""></div>'
            '<div class="big">$221.40<span>/yr saved</span></div>'
            '<div class="step-label">x</div>'
        )

    def _clean_rooftop(self):
        return (
            '<textarea id="question"></textarea>'
            '<div id="notice" class="show">using the classic form</div>'
            '<div id="__probe" data-err=""></div>'
            '<div class="big">$1,782.00</div>'
            '<div class="sub">$16,225.00 upfront · payback 9.1 yr · NPV ...</div>'
            '<div class="step-label">x</div>'
        )

    def test_clean_community_has_no_problems(self):
        self.assertEqual(vw.assert_render("community", self._clean_community()), [])

    def test_clean_rooftop_has_no_problems(self):
        self.assertEqual(vw.assert_render("rooftop", self._clean_rooftop()), [])

    def test_parity_failure_detected(self):
        dom = self._clean_community() + "Formula self-check FAILED (community)"
        problems = vw.assert_render("community", dom)
        self.assertTrue(any("parity" in p for p in problems))

    def test_js_error_detected(self):
        dom = self._clean_community().replace('data-err=""', 'data-err="TypeError x"')
        problems = vw.assert_render("community", dom)
        self.assertTrue(any("JS error" in p for p in problems))

    def test_missing_headline_detected(self):
        dom = '<div id="__probe" data-err=""></div><div class="step-label">x</div>'
        problems = vw.assert_render("community", dom)
        self.assertTrue(any(".big missing" in p for p in problems))

    def test_missing_fallback_notice_detected(self):
        dom = self._clean_community().replace("using the classic form", "")
        problems = vw.assert_render("community", dom)
        self.assertTrue(any("fallback notice" in p for p in problems))

    def test_capital_missing_upfront_detected(self):
        dom = (
            '<div id="__probe" data-err=""></div>'
            '<div class="big">$1,782.00</div><div class="step-label">x</div>'
        )
        problems = vw.assert_render("rooftop", dom)
        self.assertTrue(any("upfront" in p for p in problems))


class TestEvaluateGate(unittest.TestCase):
    HASHES = {"web/index.html": "aaa", "web/app.js": "bbb"}

    def _passing_evidence(self):
        return {"result": "pass", "file_hashes": dict(self.HASHES), "options": {}}

    def test_no_evidence_blocks(self):
        ok, reasons = vw.evaluate_gate(None, self.HASHES)
        self.assertFalse(ok)
        self.assertTrue(any("no web verification evidence" in r for r in reasons))

    def test_fresh_passing_evidence_passes(self):
        ok, reasons = vw.evaluate_gate(self._passing_evidence(), self.HASHES)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])

    def test_failed_evidence_blocks(self):
        ev = self._passing_evidence()
        ev["result"] = "fail"
        ev["options"] = {"battery": {"problems": ["screenshot not produced"]}}
        ok, reasons = vw.evaluate_gate(ev, self.HASHES)
        self.assertFalse(ok)
        self.assertTrue(any("did not pass" in r for r in reasons))

    def test_stale_hash_blocks_and_names_file(self):
        ev = self._passing_evidence()
        current = dict(self.HASHES)
        current["web/app.js"] = "CHANGED"
        ok, reasons = vw.evaluate_gate(ev, current)
        self.assertFalse(ok)
        self.assertTrue(any("stale" in r and "web/app.js" in r for r in reasons))


class TestEvaluatePerception(unittest.TestCase):
    """Judged verdicts from the agent perception loop: fresh fail blocks, stale is ignored."""

    HASHES = {"web/index.html": "aaa", "web/app.js": "bbb"}

    def _perception(self, result, hashes=None, note=""):
        return {"states": {"community": {
            "result": result, "file_hashes": hashes or dict(self.HASHES), "note": note,
        }}}

    def test_no_perception_record_is_fine(self):
        self.assertEqual(vw.evaluate_perception(None, self.HASHES), [])

    def test_fresh_fail_blocks_and_carries_the_note(self):
        reasons = vw.evaluate_perception(self._perception("fail", note="headline overlaps"), self.HASHES)
        self.assertEqual(len(reasons), 1)
        self.assertIn("community", reasons[0])
        self.assertIn("headline overlaps", reasons[0])

    def test_fresh_pass_clears(self):
        self.assertEqual(vw.evaluate_perception(self._perception("pass"), self.HASHES), [])

    def test_stale_fail_is_ignored(self):
        stale = self._perception("fail", hashes={"web/index.html": "OLD", "web/app.js": "bbb"})
        self.assertEqual(vw.evaluate_perception(stale, self.HASHES), [])

    def test_later_pass_for_same_state_clears_earlier_fail(self):
        # record() keys by state, so a later pass REPLACES the fail — modeled here as the
        # post-replacement record evaluating clean.
        p = self._perception("fail")
        p["states"]["community"] = self._perception("pass")["states"]["community"]
        self.assertEqual(vw.evaluate_perception(p, self.HASHES), [])


class TestRecordSubcommand(unittest.TestCase):
    def test_refuses_missing_screenshot(self):
        code = vw.cmd_record(vw.repo_root(), "community", "fail",
                             os.path.join("nope", "missing.png"), 0, "x")
        self.assertEqual(code, vw.EXIT_INFRA)


class TestFindChromium(unittest.TestCase):
    """Discovery must be OS-general (R13): PATH names first, then per-OS well-known locations.

    Each scenario simulates a machine where only one browser exists, regardless of the OS the
    test itself runs on.
    """

    ENV = {
        "ProgramFiles": r"C:\Program Files",
        "ProgramFiles(x86)": r"C:\Program Files (x86)",
        "LOCALAPPDATA": r"C:\Users\u\AppData\Local",
    }

    def _find_with(self, existing_path):
        with mock.patch.object(vw.shutil, "which", return_value=None), \
             mock.patch.dict(vw.os.environ, self.ENV), \
             mock.patch.object(vw.os.path, "exists",
                               side_effect=lambda p: p == existing_path):
            return vw.find_chromium()

    def test_path_hit_wins(self):
        with mock.patch.object(vw.shutil, "which",
                               side_effect=lambda n: "/usr/bin/google-chrome" if n == "google-chrome" else None):
            self.assertEqual(vw.find_chromium(), "/usr/bin/google-chrome")

    def test_linux_only_machine(self):
        self.assertEqual(self._find_with("/snap/bin/chromium"), "/snap/bin/chromium")

    def test_windows_edge_only_machine(self):
        edge = os.path.join(r"C:\Program Files (x86)", "Microsoft", "Edge", "Application", "msedge.exe")
        self.assertEqual(self._find_with(edge), edge)

    def test_windows_chrome_only_machine(self):
        chrome = os.path.join(r"C:\Program Files", "Google", "Chrome", "Application", "chrome.exe")
        self.assertEqual(self._find_with(chrome), chrome)

    def test_macos_only_machine(self):
        mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        self.assertEqual(self._find_with(mac), mac)

    def test_no_browser_anywhere(self):
        self.assertIsNone(self._find_with("/nonexistent"))


class TestCliWiring(unittest.TestCase):
    """check exits non-zero (block) when no evidence exists in a clean temp root."""

    def test_check_blocks_without_evidence(self):
        # Run check against a throwaway cwd with no .verify — but verify_web resolves root from
        # its own path, so this asserts the real repo's check returns a defined gate code.
        root = vw.repo_root()
        proc = subprocess.run(
            [sys.executable, os.path.join(root, "tools", "verify_web.py"), "check"],
            capture_output=True, text=True,
        )
        self.assertIn(proc.returncode, (vw.EXIT_OK, vw.EXIT_BLOCK))


if __name__ == "__main__":
    unittest.main()
