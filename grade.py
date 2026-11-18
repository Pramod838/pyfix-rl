#!/usr/bin/env python3
"""
grade.py — Standalone grader CLI. Grade a submitted fix file.

Usage:
  python grade.py --task 1 --file fix.py
  docker compose run --rm grader python grade.py --task 1 --file fix.py

Exit codes:
  0 — submission passed all hidden tests
  1 — submission failed
  2 — input error (file not found, bad task ID, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grade a submitted Python fix file against hidden tests."
    )
    parser.add_argument("--task", type=int, required=True, choices=[1, 2, 3, 4],
                        help="Task ID (1–4)")
    parser.add_argument("--file", type=str, required=True,
                        help="Path to .py file containing the submitted fix")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}"}), file=sys.stderr)
        sys.exit(2)

    code = path.read_text(encoding="utf-8")
    from grader.grade import grade_submission

    result = grade_submission(code, args.task)

    output = {
        "task_id": args.task,
        "file": str(path),
        "reward": result.reward,
        "passed": result.agent_feedback.passed,
        "error_summary": result.agent_feedback.error_summary,
    }
    print(json.dumps(output, indent=2))

    sys.exit(0 if result.agent_feedback.passed else 1)


if __name__ == "__main__":
    main()
