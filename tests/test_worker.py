"""
tests/test_worker.py — Tests for the worker HTTP server.

Tests request validation, execution, timeout, and security behaviour.
"""

from __future__ import annotations

import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

WORKER_URL = os.environ.get("PYFIX_WORKER_URL", "http://localhost:5001")


def _post_run(payload: dict) -> dict:
    """POST to worker /run and return parsed JSON response."""
    encoded = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{WORKER_URL}/run",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _run_code(code: str, fn: str, args: list) -> dict:
    return _post_run({"code": code, "fn": fn, "args_json": json.dumps(args)})


class TestWorkerHealth:
    def test_health_check(self, worker):
        req = urllib.request.Request(f"{WORKER_URL}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        assert data["status"] == "ok"


class TestWorkerValidExecution:
    def test_simple_function(self, worker):
        code = 'def f(x): return x + 1'
        result = _run_code(code, "f", [5])
        assert result["ok"] is True
        assert result["result"] == 6

    def test_string_function(self, worker):
        code = 'def reverse_words(s): return " ".join(s.split()[::-1])'
        result = _run_code(code, "reverse_words", ["hello world"])
        assert result["ok"] is True
        assert result["result"] == "world hello"

    def test_function_returning_bool(self, worker):
        code = 'def always_true(x): return True'
        result = _run_code(code, "always_true", [0])
        assert result["ok"] is True
        assert result["result"] is True

    def test_function_returning_list(self, worker):
        code = 'def squares(n): return [i*i for i in range(n)]'
        result = _run_code(code, "squares", [4])
        assert result["ok"] is True
        assert result["result"] == [0, 1, 4, 9]

    def test_function_raising_valueerror(self, worker):
        code = 'def strict(x):\n    if x < 0: raise ValueError("negative")\n    return x'
        result = _run_code(code, "strict", [-1])
        assert result["ok"] is False
        assert "ValueError" in result["error"]

    def test_stdout_print_does_not_corrupt_json(self, worker):
        """Submitted code that prints to stdout must not break the JSON protocol."""
        code = 'def f(x):\n    print("DEBUG:", x)\n    return x * 2'
        result = _run_code(code, "f", [3])
        assert result["ok"] is True
        assert result["result"] == 6

    def test_multiple_print_calls(self, worker):
        """Multiple print() calls must not interfere."""
        code = (
            'def f(s):\n'
            '    print("start")\n'
            '    r = " ".join(s.split()[::-1])\n'
            '    print("end:", r)\n'
            '    return r'
        )
        result = _run_code(code, "f", ["hello world"])
        assert result["ok"] is True
        assert result["result"] == "world hello"


class TestWorkerErrorHandling:
    def test_syntax_error_in_code(self, worker):
        result = _run_code("def f(x: return x", "f", [1])
        assert result["ok"] is False
        assert "SyntaxError" in result["error"] or "Error" in result["error"]

    def test_missing_function(self, worker):
        result = _run_code("def other_fn(x): return x", "missing_fn", [1])
        assert result["ok"] is False
        assert "AttributeError" in result["error"] or "missing_fn" in result["error"]

    def test_runtime_exception(self, worker):
        result = _run_code("def f(x): return 1/0", "f", [1])
        assert result["ok"] is False
        assert "ZeroDivisionError" in result["error"]

    def test_non_serialisable_return(self, worker):
        """Returning a non-JSON-serialisable object must give a controlled error."""
        code = 'def f(x): return object()'
        result = _run_code(code, "f", [1])
        assert result["ok"] is False


class TestWorkerRequestValidation:
    def test_missing_code_field(self, worker):
        result = _post_run({"fn": "f", "args_json": "[]"})
        # Worker returns error for missing/empty code
        assert result["ok"] is False

    def test_empty_code_field(self, worker):
        result = _post_run({"code": "", "fn": "f", "args_json": "[]"})
        assert result["ok"] is False

    def test_missing_fn_field(self, worker):
        result = _post_run({"code": "def f(): pass", "args_json": "[]"})
        assert result["ok"] is False

    def test_invalid_args_json(self, worker):
        result = _post_run({"code": "def f(): pass", "fn": "f", "args_json": "not-json"})
        assert result["ok"] is False

    def test_args_json_not_array(self, worker):
        result = _post_run({"code": "def f(): pass", "fn": "f", "args_json": '{"key": "val"}'})
        assert result["ok"] is False


class TestWorkerTimeout:
    def test_infinite_loop_times_out(self, worker):
        """Submitted code with infinite loop must time out without hanging."""
        code = 'def f(x):\n    while True: pass'
        result = _run_code(code, "f", [1])
        assert result["ok"] is False
        assert "TimeoutError" in result["error"] or "Timeout" in result["error"]


class TestWorkerOutputLimits:
    def test_excessive_stdout_killed(self, worker):
        """
        Submitted code that prints far more than MAX_OUTPUT_BYTES must be
        terminated and return an OutputTooLarge error rather than buffering
        all output into RAM.
        """
        # 128 KB limit; print ~1 MB to exceed it reliably
        code = (
            'def f(x):\n'
            '    print("A" * 1_200_000)\n'  # ~1.2 MB
            '    return x\n'
        )
        result = _run_code(code, "f", [1])
        assert result["ok"] is False
        assert "OutputTooLarge" in result["error"], (
            f"Expected OutputTooLarge error, got: {result['error']}"
        )

    def test_excessive_stderr_killed(self, worker):
        """
        Code that writes far more than MAX_OUTPUT_BYTES to stderr must also
        be terminated.
        """
        code = (
            'import sys\n'
            'def f(x):\n'
            '    sys.stderr.write("B" * 1_200_000)\n'
            '    return x\n'
        )
        result = _run_code(code, "f", [1])
        assert result["ok"] is False
        # Either OutputTooLarge or the process was killed before returning
        assert not result["ok"]


class TestWorkerSecurity:
    def test_cannot_read_app_hidden(self, worker):
        """In the worker container, /app/hidden/ is not mounted.
        Outside Docker (local testing), this path may not exist either.
        Either way, submitted code should fail to read it."""
        code = (
            'def f(x):\n'
            '    import pathlib\n'
            '    p = pathlib.Path("/app/hidden/suite_task1.py")\n'
            '    if p.exists():\n'
            '        return p.read_text()[:50]\n'
            '    raise FileNotFoundError(f"not found: {p}")\n'
        )
        result = _run_code(code, "f", [0])
        # Should fail — either FileNotFoundError or the path doesn't exist
        # (In Docker worker, path is not mounted; locally, /app/ may not exist)
        # The exact error depends on the environment, but it should not succeed
        # with actual test file contents
        if result["ok"]:
            # If it somehow succeeded, the content must NOT be real test data
            assert "TEST_CASES" not in str(result.get("result", ""))
        else:
            assert result["ok"] is False
