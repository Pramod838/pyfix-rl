"""
pyfix/runner.py — Minimal child-process entrypoint for running submitted code.

Spawned by pyfix/worker.py for every individual test case.
Has NO knowledge of expected outputs, hidden test files, or the grader.

Usage (internal):
  python runner.py <code_path> <function_name> <args_json>

Stdout: a single JSON line — either
  {"ok": true, "result": <value>}
or
  {"ok": false, "error": "<ExceptionType>: <message>"}

The worker reads this JSON; the grader compares result to expected value.

STDOUT ISOLATION: submitted code's print() calls are redirected to stderr
before the function executes, so they cannot corrupt the JSON protocol line
on stdout.
"""

from __future__ import annotations

import importlib.util
import json
import sys


def _redirect_stdout_to_stderr():
    """
    Redirect sys.stdout to sys.stderr so any print() calls inside submitted
    code go to stderr (captured by the worker) rather than stdout.
    Returns the original stdout for restoration.
    """
    original = sys.stdout
    sys.stdout = sys.stderr
    return original


def _restore_stdout(original):
    """Restore sys.stdout to its original value."""
    sys.stdout = original


def main() -> None:
    if len(sys.argv) != 4:
        print(json.dumps({
            "ok": False,
            "error": "Usage: runner.py <code_path> <fn_name> <args_json>",
        }))
        sys.exit(0)

    code_path, fn_name, args_json = sys.argv[1], sys.argv[2], sys.argv[3]

    # Deserialise arguments
    try:
        args = json.loads(args_json)
        if not isinstance(args, list):
            raise TypeError("args_json must be a JSON array")
    except (json.JSONDecodeError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": f"ArgsDecodeError: {exc}"}))
        sys.exit(0)

    # Load the submitted module
    # Redirect stdout → stderr BEFORE exec_module so module-level prints are safe
    original_stdout = _redirect_stdout_to_stderr()
    try:
        spec = importlib.util.spec_from_file_location("solution", code_path)
        mod = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
        spec.loader.exec_module(mod)                   # type: ignore[union-attr]
    except Exception as exc:
        _restore_stdout(original_stdout)
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(0)

    # Find the target function
    fn = getattr(mod, fn_name, None)
    if fn is None or not callable(fn):
        _restore_stdout(original_stdout)
        print(json.dumps({
            "ok": False,
            "error": f"AttributeError: no callable '{fn_name}' in submitted code",
        }))
        sys.exit(0)

    # Execute — stdout is still redirected to stderr during function call
    try:
        result = fn(*args)
    except Exception as exc:
        _restore_stdout(original_stdout)
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(0)

    # Restore stdout before printing the JSON protocol line
    _restore_stdout(original_stdout)

    try:
        # Verify the result is JSON-serialisable before printing
        serialised = json.dumps({"ok": True, "result": result})
        print(serialised)
    except (TypeError, ValueError) as exc:
        print(json.dumps({
            "ok": False,
            "error": f"SerializationError: return value cannot be serialised to JSON: {exc}",
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
