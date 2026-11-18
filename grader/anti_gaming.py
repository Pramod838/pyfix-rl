"""
grader/anti_gaming.py — AST-based heuristics for obviously broken submissions.

IMPORTANT: This is an efficiency check, NOT a security boundary.
  - It avoids spawning worker subprocesses for trivially broken code.
  - The real security boundary is the two-container isolation:
    the worker container has no /app/hidden mount.
  - AST heuristics are bypassable and are documented as such.

Checks performed:
  1. Syntax errors — cannot even be parsed.
  2. Bare constant return — single-statement function body returning a constant.
"""

from __future__ import annotations

import ast
from typing import Tuple


def is_obviously_broken(code: str) -> Tuple[bool, str]:
    """
    Return (True, reason) if the submission has an obvious structural problem.
    Return (False, "") if it passes all heuristic checks.

    >>> is_obviously_broken("def f(x): return 42")
    (True, "Submission returns a bare constant in 'f'")
    >>> is_obviously_broken("def f(x): return x + 1")
    (False, '')
    """
    # Check 1: parseable Python
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return True, f"SyntaxError: {exc}"

    # Check 2: bare constant return (e.g., def f(): return 42)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = node.body
        if (
            len(body) == 1
            and isinstance(body[0], ast.Return)
            and isinstance(body[0].value, ast.Constant)
        ):
            return True, f"Submission returns a bare constant in '{node.name}'"

    return False, ""
