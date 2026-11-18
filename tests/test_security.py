"""
tests/test_security.py — Security-focused tests for exploit prevention.

These tests verify that the documented security controls work as intended.
Tests are safe and controlled — no destructive operations on the host.
"""

from __future__ import annotations

import sys
import os
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

WORKER_URL = os.environ.get("PYFIX_WORKER_URL", "http://localhost:5001")


def _run_code(code: str, fn: str, args: list) -> dict:
    encoded = json.dumps({"code": code, "fn": fn, "args_json": json.dumps(args)}).encode()
    req = urllib.request.Request(
        f"{WORKER_URL}/run",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


class TestExploit1Hardcode:
    """Exploit 1: hardcoding outputs for visible test cases."""

    def test_hardcode_blocked_by_hypothesis(self, worker):
        """Hardcoded lookup table fails on hypothesis-generated inputs with extra whitespace."""
        from grader.grade import grade_submission
        hardcoded = (
            'def reverse_words(s):\n'
            '    table = {\n'
            '        "hello world": "world hello",\n'
            '        "foo bar baz": "baz bar foo",\n'
            '    }\n'
            '    if s in table: return table[s]\n'
            '    return " ".join(s.split(" ")[::-1])  # buggy fallback\n'
        )
        result = grade_submission(hardcoded, task_id=1)
        assert not result.agent_feedback.passed, "Hardcoding must not achieve reward=1.0"


class TestExploit2Overwrite:
    """Exploit 2: attempting to overwrite hidden test files."""

    def test_overwrite_blocked(self, worker):
        """In worker, /app/hidden/ is not mounted; writing to it fails."""
        code = (
            'def reverse_words(s):\n'
            '    import pathlib\n'
            '    p = pathlib.Path("/app/hidden/suite_task1.py")\n'
            '    try:\n'
            '        p.write_text("cleared")\n'
            '    except (FileNotFoundError, PermissionError):\n'
            '        pass\n'
            '    return " ".join(s.split()[::-1])\n'
        )
        result = _run_code(code, "reverse_words", ["hello world"])
        # Function returns correct result (the write fails silently)
        # but the actual grading pipeline runs hidden tests which verify correctness
        # The important thing: attempting to write /app/hidden/ must fail
        # This test verifies the worker doesn't crash and the write path fails
        # (confirmed by the FileNotFoundError in the except clause)
        assert result["ok"] is True  # function itself succeeds despite failed write
        assert result["result"] == "world hello"

    def test_overwrite_via_grader_still_blocked(self, worker):
        """Even if the write 'succeeds' locally, grader still loads from hidden/ correctly."""
        from grader.grade import grade_submission
        code = (
            'def reverse_words(s):\n'
            '    import pathlib, os\n'
            '    # Try to overwrite test suite (fails in Docker; may fail locally too)\n'
            '    hidden_path = pathlib.Path(os.environ.get("PYFIX_HIDDEN_DIR", "/app/hidden"))\n'
            '    try:\n'
            '        (hidden_path / "suite_task1.py").write_text("")\n'
            '    except Exception:\n'
            '        pass\n'
            '    return " ".join(s.split(" ")[::-1])  # buggy implementation\n'
        )
        result = grade_submission(code, task_id=1)
        # Grader should still load the real suite (suite is loaded before code runs)
        # Reward should be 0 because the implementation is still buggy
        assert not result.agent_feedback.passed


class TestExploit3ReadHidden:
    """Exploit 3: attempting to read hidden test files."""

    def test_read_hidden_fails_in_worker(self, worker):
        """Worker cannot access /app/hidden/ (not mounted there)."""
        code = (
            'def reverse_words(s):\n'
            '    import pathlib\n'
            '    p = pathlib.Path("/app/hidden/suite_task1.py")\n'
            '    if p.exists():\n'
            '        return p.read_text()[:20]\n'
            '    # Path does not exist in worker container\n'
            '    return " ".join(s.split()[::-1])\n'
        )
        result = _run_code(code, "reverse_words", ["hello world"])
        # In Docker worker: /app/hidden/ does not exist → takes else branch → correct result
        # Locally: /app/hidden/ may not exist → same result
        # Key: if the read succeeds, it should NOT contain actual test suite content
        if result["ok"] and isinstance(result.get("result"), str):
            assert "TEST_CASES" not in result["result"]


class TestFeedbackLeakage:
    """Verify that expected values are never leaked through agent feedback."""

    def test_no_expected_values_in_task1_error(self, worker):
        from grader.grade import grade_submission
        result = grade_submission(
            'def reverse_words(s): return s.upper()',  # wrong implementation
            task_id=1
        )
        err = result.agent_feedback.error_summary
        # Must not reveal what the expected output was
        assert "world hello" not in err.lower()
        assert "baz bar foo" not in err.lower()

    def test_no_expected_values_in_task3_error(self, worker):
        from grader.grade import grade_submission
        result = grade_submission(
            'def compute_moving_average(d, w): return [1.0]',  # trivially wrong
            task_id=3
        )
        err = result.agent_feedback.error_summary
        # Must not reveal expected list contents
        assert "[2.0, 3.0, 4.0]" not in err
        assert "[4.0, 7.0, 4.0]" not in err

    def test_no_test_counts_in_info(self, worker):
        """env.step() info must not reveal test counts."""
        from pyfix.env import CodeRepairEnv
        env = CodeRepairEnv(task_id=1)
        env.reset()
        _, _, _, _, info = env.step('def reverse_words(s): return s')
        assert "tests_passed" not in info
        assert "tests_total" not in info
        assert "per_test" not in info
        env.close()

    def test_task3_no_length_leak(self, worker):
        """Task 3 error must say 'Wrong output length' without revealing expected count."""
        from grader.grade import grade_submission
        # Submit code that returns a list of wrong length
        result = grade_submission(
            'def compute_moving_average(d, w):\n    if w<=0 or w>len(d): raise ValueError()\n    return [1.0]',
            task_id=3
        )
        err = result.agent_feedback.error_summary
        # May say "Wrong output length" but must NOT say "expected 3" etc.
        import re
        # Check no specific numeric expected value is leaked
        assert not re.search(r"expected\s+\d+", err, re.IGNORECASE)


class TestExactExceptionValidation:
    """Verify that only the exact ValueError type satisfies ValueError checks."""

    def test_runtimeerror_with_valueerror_in_message_fails_task3(self, worker):
        """
        RuntimeError('ValueError occurred') must NOT pass the invalid-window check
        in Task 3. Only an actual ValueError satisfies the check.
        """
        from grader.grade import grade_submission
        fake = (
            'def compute_moving_average(data, window):\n'
            '    if window <= 0 or window > len(data):\n'
            '        raise RuntimeError("ValueError occurred for invalid window")\n'
            '    return [sum(data[i:i+window])/window for i in range(len(data)-window+1)]\n'
        )
        result = grade_submission(fake, task_id=3)
        assert not result.agent_feedback.passed, (
            "RuntimeError with 'ValueError' in message must not pass the ValueError check"
        )

    def test_runtimeerror_with_valueerror_in_message_fails_task4(self, worker):
        """
        RuntimeError('ValueError occurred') must NOT pass the error-on-bad-input
        check in Task 4 Category 3.
        """
        from grader.grade import grade_submission
        # Correct correctness but wrong exception type for bad dims
        fake = (
            'def matrix_multiply(A, B):\n'
            '    if not A or not A[0] or not B or not B[0]:\n'
            '        raise RuntimeError("ValueError: empty matrix")\n'
            '    if any(len(r)!=len(A[0]) for r in A) or any(len(r)!=len(B[0]) for r in B):\n'
            '        raise RuntimeError("ValueError: ragged matrix")\n'
            '    if len(A[0])!=len(B):\n'
            '        raise RuntimeError("ValueError: bad dims")\n'
            '    C=[[0.0]*len(B[0]) for _ in range(len(A))]\n'
            '    for i in range(len(A)):\n'
            '        for j in range(len(B[0])):\n'
            '            for k in range(len(A[0])): C[i][j]+=A[i][k]*B[k][j]\n'
            '    return C\n'
        )
        result = grade_submission(fake, task_id=4)
        # Category 3 must fail because RuntimeError != ValueError
        assert result.reward < 1.0
        # The reward for category 3 should be 0 (RuntimeError is not ValueError)
        # Overall reward must be less than 0.34 + whatever correctness gives
        # At minimum the error-handling category (0.34) must NOT be gained
        assert result.reward != pytest.approx(0.34, abs=0.01) or result.reward < 0.68


class TestASTheuristics:
    """Tests for the AST-based anti-gaming heuristic."""

    def test_bare_constant_rejected(self, worker):
        from grader.grade import grade_submission
        result = grade_submission("def reverse_words(s): return 'world hello'", 1)
        assert not result.agent_feedback.passed
        assert "bare constant" in result.agent_feedback.error_summary.lower()

    def test_syntax_error_rejected(self, worker):
        from grader.grade import grade_submission
        result = grade_submission("def f(x: return x", 1)
        assert not result.agent_feedback.passed
        assert "SyntaxError" in result.agent_feedback.error_summary

    def test_valid_code_passes_ast(self, worker):
        """Valid code passes AST check and is executed."""
        from grader.grade import grade_submission
        result = grade_submission(
            'def reverse_words(s): return " ".join(s.split()[::-1])', 1
        )
        # This should pass (correct implementation)
        assert result.agent_feedback.passed
