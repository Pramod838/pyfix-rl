"""
tests/conftest.py — Shared pytest fixtures for pyfix-rl tests.

The `worker` session fixture starts the pyfix worker HTTP server if it is not
already running. Tests that require an active worker should declare it as a
dependency via `def test_foo(worker): ...`
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
TEST_WORKER_PORT = int(os.environ.get("PYFIX_TEST_WORKER_PORT", "5001"))
TEST_HIDDEN_DIR  = str(PROJECT_ROOT / "hidden")


def _worker_alive(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://localhost:{port}/health", timeout=1)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def worker():
    """
    Ensure the worker HTTP server is running for the test session.
    If it is already running (e.g. from a previous shell session), reuse it.
    Otherwise start a new one and tear it down after the session.
    """
    # Set environment variables for all tests in the session
    os.environ["PYFIX_WORKER_URL"] = f"http://localhost:{TEST_WORKER_PORT}"
    os.environ["PYFIX_HIDDEN_DIR"] = TEST_HIDDEN_DIR

    already_running = _worker_alive(TEST_WORKER_PORT)
    proc = None

    if not already_running:
        env = {
            **os.environ,
            "WORKER_PORT": str(TEST_WORKER_PORT),
            "PYFIX_STRICT_LIMITS": "0",  # relax limits for local testing
        }
        proc = subprocess.Popen(
            [sys.executable, "-m", "pyfix.worker"],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for the server to start (up to 5 seconds)
        for _ in range(25):
            if _worker_alive(TEST_WORKER_PORT):
                break
            time.sleep(0.2)
        else:
            proc.terminate()
            pytest.fail(f"Worker did not start on port {TEST_WORKER_PORT} within 5 seconds")

    yield

    if proc is not None:
        proc.terminate()
        proc.wait(timeout=5)
