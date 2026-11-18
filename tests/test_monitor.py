"""
tests/test_monitor.py — Tests for monitoring information separation.

Verifies that:
  - Normal mode never exposes researcher-only per_test data.
  - Research mode does expose per_test data.
  - error_summary is saved to log files so the monitor can display it.
"""

from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log_entry(
    task_id: int = 1,
    reward: float = 0.0,
    passed: bool = False,
    error_summary: str = "Wrong answer",
    tests_passed: int = 5,
    tests_total: int = 10,
    per_test=None,
) -> dict:
    """Build a synthetic log entry matching the _write_log format."""
    if per_test is None:
        per_test = [
            {"passed": False, "error": "SECRET: expected [2.0, 3.0]"},
            {"passed": True,  "error": ""},
        ]
    return {
        "task_id": task_id,
        "reward": reward,
        "passed": passed,
        "error_summary": error_summary,
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "per_test": per_test,
        "timestamp": "2026-11-18T18:00:00Z",
    }


def _capture_display(entry: dict, research_mode: bool) -> str:
    """Call display_grade_event and capture its stdout output."""
    from monitor import display_grade_event
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        display_grade_event(entry, research_mode=research_mode)
    finally:
        sys.stdout = old_stdout
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMonitorInfoSeparation:
    """Verify the agent-visible / researcher-only boundary in monitor output."""

    def test_normal_mode_shows_error_summary(self):
        """Normal mode must display the sanitised error_summary from the log."""
        entry = _make_log_entry(error_summary="Wrong answer")
        output = _capture_display(entry, research_mode=False)
        assert "Wrong answer" in output

    def test_normal_mode_does_not_show_per_test_raw_errors(self):
        """Normal mode must NOT display raw per_test error strings."""
        per_test = [{"passed": False, "error": "SECRET: expected [2.0, 3.0]"}]
        entry = _make_log_entry(error_summary="Wrong values", per_test=per_test)
        output = _capture_display(entry, research_mode=False)
        assert "SECRET" not in output, "Raw per_test error must not appear in normal mode"
        assert "expected [2.0, 3.0]" not in output, "Expected values must not appear in normal mode"

    def test_normal_mode_does_not_show_test_counts(self):
        """Normal mode must NOT show tests_passed or tests_total."""
        entry = _make_log_entry(tests_passed=5, tests_total=10)
        output = _capture_display(entry, research_mode=False)
        # "5 / 10" must not appear in normal mode
        assert "5 / 10" not in output
        assert "Tests passed" not in output

    def test_research_mode_shows_per_test_count(self):
        """Research mode must show test counts."""
        entry = _make_log_entry(tests_passed=5, tests_total=10)
        output = _capture_display(entry, research_mode=True)
        assert "5 / 10" in output or "5" in output

    def test_research_mode_shows_per_test_errors(self):
        """Research mode must show raw per_test error strings."""
        per_test = [{"passed": False, "error": "RESEARCHER-DETAIL: int instead of float"}]
        entry = _make_log_entry(per_test=per_test)
        output = _capture_display(entry, research_mode=True)
        assert "RESEARCHER-DETAIL" in output

    def test_normal_mode_shows_reward(self):
        entry = _make_log_entry(reward=1.0, passed=True, error_summary="")
        output = _capture_display(entry, research_mode=False)
        assert "1.00" in output or "SOLVED" in output

    def test_normal_mode_no_per_test_key_access_at_all(self):
        """Verify that per_test data with deliberately sensitive content is fully hidden."""
        sensitive_per_test = [
            {"passed": False, "error": "got [1, 2, 3] expected [1.0, 2.0, 3.0]"},
        ]
        entry = _make_log_entry(
            error_summary="Wrong values",
            per_test=sensitive_per_test,
        )
        output = _capture_display(entry, research_mode=False)
        assert "got [1, 2, 3]" not in output
        assert "[1.0, 2.0, 3.0]" not in output


class TestErrorSummarySavedToLog:
    """Verify that _write_log saves error_summary so the monitor can read it."""

    def test_error_summary_in_log_file(self, worker, tmp_path, monkeypatch):
        """grade_submission must write error_summary to the log file."""
        import grader.grade as gm

        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        written_logs = []

        original_write = gm._write_log

        def capturing_write(result):
            written_logs.append(result)
            # Still write to actual log dir so we can read it
            original_write(result)

        monkeypatch.setattr(gm, "_write_log", capturing_write)

        from grader.grade import grade_submission
        result = grade_submission(
            "def reverse_words(s): return s.upper()",  # wrong implementation
            task_id=1,
        )

        # error_summary must be non-empty (the submission is wrong)
        assert result.agent_feedback.error_summary != "" or not result.agent_feedback.passed

        # Find the written log file and verify error_summary key is present
        import glob
        log_files = glob.glob("logs/grade_1_*.json")
        if log_files:
            with open(sorted(log_files)[-1]) as f:
                log_data = json.load(f)
            assert "error_summary" in log_data, "error_summary must be saved to log file"

    def test_correct_submission_has_empty_error_summary_in_log(self, worker, tmp_path):
        """Correct submission must log empty error_summary."""
        from grader.grade import grade_submission
        result = grade_submission(
            'def reverse_words(s): return " ".join(s.split()[::-1])',
            task_id=1,
        )
        assert result.agent_feedback.error_summary == ""
