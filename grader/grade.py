"""
grader/grade.py — Orchestrates test execution and returns structured results.

Security principle:
  - Expected values are only ever present in this (grader) process.
  - Submitted code runs in the worker container via HTTP.
  - Each HTTP call is one test case; comparison happens here, not in worker.
  - AgentFeedback is the only part of GradeResult ever returned to the agent.

Information boundaries:
  - AgentFeedback: passed bool + sanitised error (exception type only, no values)
  - GradeResult: full details written to logs/ — NEVER sent to agent
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

from grader.anti_gaming import is_obviously_broken

logging.basicConfig(level=logging.INFO, format="[grader] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data classes (strict agent/researcher boundary)
# ---------------------------------------------------------------------------

@dataclass
class AgentFeedback:
    """
    Returned in env.step() info dict.
    Never contains test counts, expected values, or detailed failure info.
    """
    passed: bool
    error_summary: str  # max 200 chars; sanitised exception type, no values


@dataclass
class GradeResult:
    """
    Full grading result. Written to logs/ only.
    NEVER serialised into env.step() return values directly.
    env.step() calls dataclasses.asdict(result.agent_feedback) — two fields only.
    """
    agent_feedback: AgentFeedback
    reward: float
    task_id: int
    tests_passed: int = field(repr=False)
    tests_total: int = field(repr=False)
    per_test: List[dict] = field(repr=False, default_factory=list)


# ---------------------------------------------------------------------------
# Worker HTTP client
# ---------------------------------------------------------------------------

WORKER_URL = os.environ.get("PYFIX_WORKER_URL", "http://localhost:5001")


def _call_worker(code: str, fn: str, args: tuple) -> dict:
    """
    POST to the worker with (code, function_name, serialised_args).
    Returns {"ok": bool, "result": ...} or {"ok": false, "error": "..."}.
    Expected values are NEVER sent to the worker.
    """
    payload = json.dumps({
        "code": code,
        "fn": fn,
        "args_json": json.dumps(list(args)),
    }).encode()
    req = urllib.request.Request(
        f"{WORKER_URL}/run",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"WorkerUnavailable: {exc}"}
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"WorkerBadResponse: {exc}"}


# ---------------------------------------------------------------------------
# Suite loader
# ---------------------------------------------------------------------------

def _load_suite(task_id: int):
    """Import hidden/suite_taskN.py by absolute path (grader has hidden/ mounted)."""
    hidden_dir = Path(os.environ.get("PYFIX_HIDDEN_DIR", "./hidden"))
    suite_path = hidden_dir / f"suite_task{task_id}.py"
    if not suite_path.exists():
        raise FileNotFoundError(
            f"Hidden suite not found: {suite_path}. "
            "Is PYFIX_HIDDEN_DIR set? Is hidden/ mounted?"
        )
    spec = importlib.util.spec_from_file_location(f"suite_task{task_id}", suite_path)
    mod = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
    spec.loader.exec_module(mod)                   # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Hypothesis input collection
# ---------------------------------------------------------------------------

def _collect_hypothesis_inputs(strategy, adapt_fn, n: int = 20) -> List[Tuple]:
    """
    Generate n deterministic (args, expected) pairs using hypothesis.

    suppress_health_check=[HealthCheck.too_slow] is justified here:
    each test case involves an HTTP call to the worker (~200ms per call),
    which exceeds hypothesis's default health check threshold of 200ms.
    We suppress ONLY this check; all others remain active.
    """
    from hypothesis import given, settings, HealthCheck

    generated: List[Tuple] = []

    @settings(
        derandomize=True,
        max_examples=n,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(raw=strategy)
    def _collect(raw: Any) -> None:
        generated.append(adapt_fn(raw))

    _collect()
    return generated


# ---------------------------------------------------------------------------
# Type-aware value comparison
# ---------------------------------------------------------------------------

def _values_equal(actual: Any, expected: Any) -> bool:
    """
    Deep equality with float tolerance and strict bool/int separation.

    Rules:
    - bool is NOT equal to int, even though Python's bool is a subclass of int.
      Rationale: task contracts specify return types; returning 1 when bool is
      expected indicates incorrect type reasoning.
    - float tolerance: 1e-9 absolute difference.
    - Lists: element-wise comparison (length must match first).
    - Other types: exact equality.
    """
    # Strict bool check: bool ≠ int
    if isinstance(expected, bool) or isinstance(actual, bool):
        # Both must be exactly bool (not int, not other subclass)
        return type(actual) is bool and type(expected) is bool and actual == expected

    # float comparison with tolerance
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        try:
            return abs(float(actual) - float(expected)) < 1e-9
        except (TypeError, ValueError):
            return False

    # Nested list comparison
    if isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            return False
        return all(_values_equal(a, e) for a, e in zip(actual, expected))

    # Fallback: exact equality
    return actual == expected


def _validate_task1_output(actual: Any) -> Optional[str]:
    """Return an error string if output is invalid for Task 1, else None."""
    if not isinstance(actual, str):
        return f"TypeError: expected str, got {type(actual).__name__}"
    return None


def _validate_task2_output(actual: Any) -> Optional[str]:
    """Return an error string if output is invalid for Task 2, else None."""
    if type(actual) is not bool:
        return f"TypeError: expected bool, got {type(actual).__name__}"
    return None


def _validate_task3_output(actual: Any) -> Optional[str]:
    """Return an error string if output is invalid for Task 3, else None.

    Task 3 contract: output must be a list of float values (not int, not bool).
    """
    if not isinstance(actual, list):
        return f"TypeError: expected list, got {type(actual).__name__}"
    for i, v in enumerate(actual):
        if type(v) is not float:   # rejects int and bool; accepts only float
            return f"TypeError: element {i} must be float, got {type(v).__name__}"
    return None


def _validate_task4_output(actual: Any) -> Optional[str]:
    """Return an error string if output is invalid for Task 4, else None.

    Task 4 contract: output must be a list of list of float values (not int, not bool).
    """
    if not isinstance(actual, list):
        return f"TypeError: expected list of list, got {type(actual).__name__}"
    for i, row in enumerate(actual):
        if not isinstance(row, list):
            return f"TypeError: row {i} must be list, got {type(row).__name__}"
        for j, v in enumerate(row):
            if type(v) is not float:   # rejects int and bool; accepts only float
                return f"TypeError: element [{i}][{j}] must be float, got {type(v).__name__}"
    return None


_TASK_VALIDATORS = {
    1: _validate_task1_output,
    2: _validate_task2_output,
    3: _validate_task3_output,
    4: _validate_task4_output,
}


# ---------------------------------------------------------------------------
# Single test runner (shared by all tasks except task 3 and 4)
# ---------------------------------------------------------------------------

def _run_one(code: str, fn: str, args: tuple, expected: Any, task_id: int = 0) -> dict:
    """
    Run one test case via the worker; compare result in grader process.
    task_id is used for type-aware validation.
    """
    resp = _call_worker(code, fn, args)
    if not resp.get("ok", False):
        return {"passed": False, "error": resp.get("error", "Unknown worker error")}
    actual = resp.get("result")

    # Type validation before value comparison
    validator = _TASK_VALIDATORS.get(task_id)
    if validator:
        type_error = validator(actual)
        if type_error:
            return {"passed": False, "error": type_error}

    # Value comparison (expected value stays in grader process only)
    try:
        passed = _values_equal(actual, expected)
    except Exception:
        passed = False
    return {"passed": passed, "error": "" if passed else "Wrong answer"}


# ---------------------------------------------------------------------------
# Task-specific graders
# ---------------------------------------------------------------------------

def _grade_task1_or_2(code: str, suite, task_id: int) -> List[dict]:
    results = []
    fn = suite.FUNCTION_NAME

    for args, expected in suite.TEST_CASES:
        results.append(_run_one(code, fn, args, expected, task_id))

    if hasattr(suite, "HYPOTHESIS_STRATEGY"):
        pairs = _collect_hypothesis_inputs(suite.HYPOTHESIS_STRATEGY, suite.adapt_input)
        for args, expected in pairs:
            results.append(_run_one(code, fn, args, expected, task_id))
    elif hasattr(suite, "HYPOTHESIS_CASES"):
        for strategy, adapt_fn in suite.HYPOTHESIS_CASES:
            pairs = _collect_hypothesis_inputs(strategy, adapt_fn)
            for args, expected in pairs:
                results.append(_run_one(code, fn, args, expected, task_id))

    return results


def _grade_task3(code: str, suite) -> List[dict]:
    """
    C9 — explicit output-length assertion before value comparison.
    Does NOT reveal expected_len in agent-facing feedback.
    """
    results = []
    fn = suite.FUNCTION_NAME

    def _run_task3_case(args, expected):
        data, window = args
        resp = _call_worker(code, fn, (data, window))
        if not resp.get("ok", False):
            return {"passed": False, "error": resp.get("error", "Worker error")}
        actual = resp.get("result")

        # Type check first
        type_error = _validate_task3_output(actual)
        if type_error:
            return {"passed": False, "error": type_error}

        # Length check (C9): report length mismatch without revealing expected length
        expected_len = len(data) - window + 1
        if len(actual) != expected_len:
            # Do NOT reveal expected_len — just say length is wrong
            return {"passed": False, "error": "Wrong output length"}

        # Value comparison (expected stays in grader only)
        if not _values_equal(actual, expected):
            return {"passed": False, "error": "Wrong values"}
        return {"passed": True, "error": ""}

    for args, expected in suite.TEST_CASES:
        results.append(_run_task3_case(args, expected))

    # Invalid window cases — grader expects ValueError
    if hasattr(suite, "INVALID_CASES"):
        for data, window in suite.INVALID_CASES:
            resp = _call_worker(code, suite.FUNCTION_NAME, (data, window))
            ok = resp.get("ok", False)
            error_str = resp.get("error", "")
            # Exact match: runner formats as "ExceptionType: message", so ValueError
            # must appear at the start. This rejects RuntimeError("some ValueError...").
            passed = not ok and (
                error_str.startswith("ValueError:") or error_str == "ValueError"
            )
            results.append({
                "passed": passed,
                "error": "" if passed else "Expected ValueError for invalid window",
            })

    pairs = _collect_hypothesis_inputs(suite.HYPOTHESIS_STRATEGY, suite.adapt_input)
    for args, expected in pairs:
        results.append(_run_task3_case(args, expected))

    return results


def _grade_task4(code: str, suite) -> Tuple[float, List[dict], dict]:
    """
    Explicit category grouping with two separate hypothesis strategies:
      - HYPOTHESIS_STRATEGY_CAT1: always 2×2 matrices
      - HYPOTHESIS_STRATEGY_CAT2: always non-square matrices

    This ensures the documented category definitions are honoured:
      Category 1: 2×2 correctness
      Category 2: non-square matrix correctness
      Category 3: ValueError on bad input
    """
    CATEGORY_WEIGHTS = {1: 0.33, 2: 0.33, 3: 0.34}
    category_results: dict = {1: [], 2: [], 3: []}
    per_test = []
    fn = suite.FUNCTION_NAME

    for args, expected, category in suite.TEST_CASES_WITH_CATEGORY:
        resp = _call_worker(code, fn, args)
        ok = resp.get("ok", False)

        if category == 3:
            # Expects a ValueError — check the exception type name at string start.
            # Runner formats exceptions as "ExceptionType: message", so we check
            # startswith to avoid false positives like RuntimeError("some ValueError...").
            error_str = resp.get("error", "")
            passed = not ok and (
                error_str.startswith("ValueError:") or error_str == "ValueError"
            )
        else:
            actual = resp.get("result") if ok else None
            type_error = _validate_task4_output(actual) if ok else None
            if type_error:
                passed = False
            else:
                passed = ok and _values_equal(actual, expected)

        category_results[category].append(passed)
        per_test.append({
            "category": category,
            "passed": passed,
            "error": resp.get("error", "") if not passed else "",
        })

    # Category 1 hypothesis: always 2×2 matrices
    if hasattr(suite, "HYPOTHESIS_STRATEGY_CAT1"):
        pairs = _collect_hypothesis_inputs(suite.HYPOTHESIS_STRATEGY_CAT1, suite.adapt_input_cat1)
        for args, expected in pairs:
            resp = _call_worker(code, fn, args)
            ok = resp.get("ok", False)
            actual = resp.get("result") if ok else None
            type_error = _validate_task4_output(actual) if ok else None
            passed = ok and type_error is None and _values_equal(actual, expected)
            category_results[1].append(passed)
            per_test.append({
                "category": 1,
                "passed": passed,
                "error": resp.get("error", "") if not passed else "",
            })

    # Category 2 hypothesis: always non-square matrices
    if hasattr(suite, "HYPOTHESIS_STRATEGY_CAT2"):
        pairs = _collect_hypothesis_inputs(suite.HYPOTHESIS_STRATEGY_CAT2, suite.adapt_input_cat2)
        for args, expected in pairs:
            resp = _call_worker(code, fn, args)
            ok = resp.get("ok", False)
            actual = resp.get("result") if ok else None
            type_error = _validate_task4_output(actual) if ok else None
            passed = ok and type_error is None and _values_equal(actual, expected)
            category_results[2].append(passed)
            per_test.append({
                "category": 2,
                "passed": passed,
                "error": resp.get("error", "") if not passed else "",
            })

    # C9: a category passes only if ALL its tests pass
    reward = sum(
        CATEGORY_WEIGHTS[cat] * (1.0 if category_results[cat] and all(category_results[cat]) else 0.0)
        for cat in CATEGORY_WEIGHTS
    )
    return round(reward, 2), per_test, category_results


# ---------------------------------------------------------------------------
# Experiment logger (researcher-only)
# ---------------------------------------------------------------------------

def _write_log(result: GradeResult) -> None:
    """Write full grading details to logs/. Never exposed to the agent."""
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        ts = int(time.time() * 1000)
        log_path = log_dir / f"grade_{result.task_id}_{ts}.json"
        with open(log_path, "w") as fh:
            json.dump({
                "task_id": result.task_id,
                "reward": result.reward,
                # Agent-visible fields (safe to show in monitor normal mode)
                "passed": result.agent_feedback.passed,
                "error_summary": result.agent_feedback.error_summary,
                # Researcher-only fields (shown only in monitor --research mode)
                "tests_passed": result.tests_passed,
                "tests_total": result.tests_total,
                "per_test": result.per_test,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }, fh, indent=2)
    except Exception as exc:
        log.warning("Failed to write experiment log: %s", exc)


def _make_early_result(task_id: int, error_summary: str) -> GradeResult:
    """Create a zero-reward GradeResult for early-exit paths, then log it."""
    fb = AgentFeedback(passed=False, error_summary=error_summary[:200])
    result = GradeResult(
        agent_feedback=fb,
        reward=0.0,
        task_id=task_id,
        tests_passed=0,
        tests_total=0,
        per_test=[{"passed": False, "error": error_summary}],
    )
    _write_log(result)
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def grade_submission(code: str, task_id: int) -> GradeResult:
    """
    Grade submitted code for the given task. Called by env.step().

    Returns a GradeResult; env.step() exposes ONLY result.agent_feedback
    to the agent via dataclasses.asdict(result.agent_feedback).
    Every execution path writes to the experiment log.
    """
    # Step 1: static heuristic check (efficiency only, not security boundary)
    broken, reason = is_obviously_broken(code)
    if broken:
        return _make_early_result(task_id, reason)

    # Step 2: load hidden suite (grader process only)
    try:
        suite = _load_suite(task_id)
    except FileNotFoundError as exc:
        return _make_early_result(task_id, "GraderConfigError: hidden suite not found")
    except Exception as exc:
        return _make_early_result(task_id, f"GraderError: {type(exc).__name__}")

    # Step 3: run tests
    try:
        if task_id == 4:
            reward, per_test, _cat = _grade_task4(code, suite)
            total = len(per_test)
            passed_count = sum(t["passed"] for t in per_test)
            all_passed = reward >= 1.0
            error_summary = "" if all_passed else _summarise_error(per_test)
        elif task_id == 3:
            per_test = _grade_task3(code, suite)
            total = len(per_test)
            passed_count = sum(t["passed"] for t in per_test)
            all_passed = passed_count == total
            reward = 1.0 if all_passed else 0.0
            error_summary = "" if all_passed else _summarise_error(per_test)
        else:
            per_test = _grade_task1_or_2(code, suite, task_id)
            total = len(per_test)
            passed_count = sum(t["passed"] for t in per_test)
            all_passed = passed_count == total
            reward = 1.0 if all_passed else 0.0
            error_summary = "" if all_passed else _summarise_error(per_test)
    except Exception as exc:
        log.error("Unexpected grader error for task %d: %s", task_id, exc, exc_info=True)
        return _make_early_result(task_id, f"GraderError: {type(exc).__name__}")

    fb = AgentFeedback(passed=all_passed, error_summary=error_summary)
    result = GradeResult(
        agent_feedback=fb,
        reward=reward,
        task_id=task_id,
        tests_passed=passed_count,
        tests_total=total,
        per_test=per_test,
    )
    _write_log(result)
    return result


def _summarise_error(per_test: List[dict]) -> str:
    """
    Build a sanitised error summary for the agent.

    Rules (information boundary):
      - Never reveal expected values, test inputs, or expected output lengths.
      - Never reveal test counts.
      - Return only: exception type or generic failure label, truncated to 200 chars.

    Sanitisation strategy:
      - If the error matches patterns that could leak values (expected/got comparisons,
        list literals, assertion details), replace with a generic label.
      - Otherwise return the first line of the error message.
    """
    import re

    failures = [t for t in per_test if not t["passed"]]
    if not failures:
        return ""
    err = failures[0].get("error", "Test failed")

    # Keep only the first line
    first_line = err.split("\n")[0].strip()

    # Patterns that likely reveal expected values — replace with generic labels
    leak_patterns = [
        r"assert\s+.*(==|!=|in\s+)",          # assert X == Y
        r"expected\s+[\[\d\'\"]",              # expected [2.0, ...] or expected 3
        r"got\s+.*expected\s+",                # got X expected Y
        r"\[\s*[\d\-\.]",                      # starts with numeric list [1.0, ...]
        r"expected\s+\d",                      # expected 3 (length leak)
    ]
    for pattern in leak_patterns:
        if re.search(pattern, first_line, re.IGNORECASE):
            # Determine if it's a type error or value error based on the original
            if "TypeError" in err or "TypeError" in first_line:
                return "TypeError: check return type"
            if "Wrong output length" in first_line or "length" in first_line.lower():
                return "Wrong output length"
            return "Wrong answer"

    return first_line[:200]
