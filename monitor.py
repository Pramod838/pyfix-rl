#!/usr/bin/env python3
"""
monitor.py — Live execution monitor for pyfix-rl.

Watches the logs/ directory for new grading events and displays them
in a readable terminal format. Clearly separates agent-visible information
from researcher-only debugging details.

Usage:
  python monitor.py                   # watch all tasks, agent view only
  python monitor.py --research        # include researcher-only details
  python monitor.py --task 1          # watch task 1 only
  python monitor.py --follow          # live-tail mode (poll every second)

Information boundaries enforced:
  Agent-visible:   passed/failed, error summary, reward, attempt count
  Researcher-only: test inputs, expected outputs, actual outputs, per-test results

IMPORTANT: Researcher-only information is ONLY displayed when --research is used.
Never include researcher-only data in agent observations or feedback.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional


LOG_DIR = Path(os.environ.get("PYFIX_LOG_DIR", "logs"))

TASK_NAMES = {1: "reverse_words", 2: "is_valid_brackets",
              3: "compute_moving_average", 4: "matrix_multiply"}

RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
GREY    = "\033[90m"
MAGENTA = "\033[95m"


def _colour(text: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"{code}{text}{RESET}"
    return text


def _fmt_reward(reward: float) -> str:
    if reward >= 1.0:
        return _colour("1.00 ✓ SOLVED", GREEN)
    if reward > 0:
        return _colour(f"{reward:.2f} (partial)", YELLOW)
    return _colour("0.00 ✗ FAILED", RED)


def _fmt_passed(passed: bool) -> str:
    return _colour("PASS", GREEN) if passed else _colour("FAIL", RED)


def display_grade_event(entry: dict, research_mode: bool) -> None:
    """Display one grading log entry in a formatted way.

    Information boundary:
      Normal mode:   shows only agent-visible fields (passed, error_summary, reward).
      Research mode: additionally shows researcher-only fields (tests_passed,
                     tests_total, per_test raw errors). Never mix the two modes.
    """
    task_id  = entry.get("task_id", "?")
    reward   = entry.get("reward", 0.0)
    passed   = entry.get("passed", False)
    ts       = entry.get("timestamp", "")
    fn_name  = TASK_NAMES.get(task_id, f"task{task_id}")
    sep      = "─" * 60

    # --- Agent-visible section (normal mode and research mode) ---
    # Reads only the sanitised error_summary saved by _write_log — never per_test.
    print(_colour(sep, CYAN))
    print(_colour(f" Task {task_id}: {fn_name}  [{ts}]", BOLD))
    print(f" Reward:        {_fmt_reward(reward)}")
    print(f" Status:        {_fmt_passed(passed)}")

    error_summary = entry.get("error_summary", "")
    if error_summary:
        print(f" Agent error:   {_colour(error_summary, YELLOW)}")

    # --- Researcher-only section (--research flag required) ---
    # per_test, tests_passed, tests_total are NEVER read outside this block.
    if research_mode:
        t_pass   = entry.get("tests_passed", 0)
        t_total  = entry.get("tests_total", 0)
        per_test = entry.get("per_test", [])

        print(_colour(f"\n {BOLD}[RESEARCHER ONLY — NOT VISIBLE TO AGENT]{RESET}", MAGENTA))
        print(_colour(f" Tests passed:  {t_pass} / {t_total}", GREY))

        if per_test:
            print(_colour(f" Per-test results:", GREY))
            for i, t in enumerate(per_test, 1):
                cat     = t.get("category", "")
                ok      = t.get("passed", False)
                err     = t.get("error", "")
                cat_str = f" [cat{cat}]" if cat else ""
                status  = _colour("✓", GREEN) if ok else _colour("✗", RED)
                err_str = f"  {_colour(err[:80], RED)}" if err and not ok else ""
                print(f"   {i:>3}. {status}{cat_str}{err_str}")

    print(_colour(sep, CYAN))
    print()


def load_log(path: Path) -> Optional[dict]:
    """Load and parse a JSON log file. Return None on error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def watch(task_filter: Optional[int], research_mode: bool, follow: bool) -> None:
    """
    Main monitoring loop.

    In --follow mode: poll LOG_DIR every second for new files.
    Without --follow: display all existing logs and exit.
    """
    LOG_DIR.mkdir(exist_ok=True)
    seen: set = set()

    print(_colour(f"\n pyfix-rl Monitor  {'[RESEARCH MODE]' if research_mode else '[AGENT VIEW]'}", BOLD))
    print(_colour(f" Watching: {LOG_DIR.resolve()}", GREY))
    if research_mode:
        print(_colour(f" ⚠ Research mode: showing expected/actual values (researcher only)", YELLOW))
    if follow:
        print(_colour(" Press Ctrl+C to stop.\n", GREY))
    else:
        print()

    while True:
        log_files = sorted(LOG_DIR.glob("grade_*.json"), key=lambda p: p.stat().st_mtime)

        for lf in log_files:
            if lf in seen:
                continue
            seen.add(lf)

            entry = load_log(lf)
            if entry is None:
                continue
            if task_filter and entry.get("task_id") != task_filter:
                continue

            display_grade_event(entry, research_mode)

        if not follow:
            break

        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live monitor for pyfix-rl execution events.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--task", type=int, choices=[1, 2, 3, 4],
                        help="Filter to a specific task")
    parser.add_argument("--research", action="store_true",
                        help="Show researcher-only details (test counts, error details)")
    parser.add_argument("--follow", action="store_true",
                        help="Live-tail mode: poll for new events every second")
    parser.add_argument("--log-dir", type=str, default=None,
                        help="Override log directory (default: logs/)")
    args = parser.parse_args()

    if args.log_dir:
        global LOG_DIR
        LOG_DIR = Path(args.log_dir)

    watch(args.task, args.research, args.follow)


if __name__ == "__main__":
    main()
