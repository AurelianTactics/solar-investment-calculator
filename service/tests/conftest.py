"""Shared test setup for the service suite.

The one thing that has to be global: **no test may write the real event log.** ``app.py`` and
``mcp_server.py`` each build a ``FeedbackLog`` at import time from the environment, so without
this the suite appends every test request to ``service/.feedback.jsonl`` in the working tree —
a gitignored file, but still real state produced by running tests, and it would grow forever.

Pointing the env var at a temp directory before those modules are imported redirects both.
"""

import os
import sys
import tempfile

import pytest

# Set BEFORE any service module is imported: FeedbackLog.from_env() runs at import time.
_LOG_DIR = tempfile.mkdtemp(prefix="solar-test-log-")
os.environ["SOLAR_FEEDBACK_PATH"] = os.path.join(_LOG_DIR, "feedback.jsonl")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SOLAR_MCP_ALLOWED_HOSTS", "testserver")


@pytest.fixture(scope="session")
def client():
    """One lifespan-entered client for the WHOLE suite, shared by every module that needs one.

    Entering the app's lifespan starts the MCP session manager, and that can only happen once per
    process — the SDK enforces it, and a deploy only ever does it once. So this cannot be a
    per-module fixture: the second module to enter its own lifespan fails at setup. Tests that
    don't need the MCP route can build a bare ``TestClient`` themselves (no ``with``, no lifespan).
    """
    import app as app_module
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as c:
        yield c
