"""
Hidden test suite for Task 2: is_valid_brackets.

Covers: genuinely independent Bug 1 (silent mismatch) and Bug 2 (return True).
Reference: adapted from TheAlgorithms/Python balanced_parentheses.py (MIT).
"""

from hypothesis import strategies as st

FUNCTION_NAME = "is_valid_brackets"

_PAIRS = [("(", ")"), ("[", "]"), ("{", "}")]


def reference_fn(s: str) -> bool:
    """The correct implementation."""
    stack = []
    bracket_map = {")": "(", "]": "[", "}": "{"}
    for char in s:
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != bracket_map[char]:
                return False
    return len(stack) == 0


# Fixed test cases: (args_tuple, expected_output)
TEST_CASES = [
    (("()",),               True),
    (("([{}])",),           True),
    (("{[()]}",),           True),
    (("",),                 True),
    (("abc(def)ghi",),      True),    # non-bracket chars ignored
    (("(((",),              False),
    (("((",),               False),   # catches Bug 2 (return True)
    ((")()",),              False),   # catches Bug 1 (silent mismatch)
    (("([)]",),             False),   # catches Bug 1
    (("{",),                False),
    (("((())",),            False),   # one more open than close
    (("((()))",),           True),
]


# C4 — Two hypothesis strategies for Task 2.
# Strategy A: generates valid bracket strings → reference always True.
# Strategy B: generates guaranteed-invalid strings → reference always False.
# Each is a (strategy, adapt_fn) pair processed by the grader.

def _build_valid(raw):
    """Build a valid bracket string from random pair indices + extra chars."""
    pair_indices, extra_texts = raw
    stack = []
    result_parts = []
    for idx, extra in zip(pair_indices, extra_texts):
        open_b, close_b = _PAIRS[idx % len(_PAIRS)]
        result_parts.append(extra[:3])   # inject non-bracket characters
        result_parts.append(open_b)
        stack.append(close_b)
    # close all brackets in reverse
    while stack:
        result_parts.append(stack.pop())
    s = "".join(result_parts)
    return (s,), True   # expected is always True for a correctly built string


def _build_invalid(raw):
    """Build a string guaranteed to be invalid."""
    seed_str = raw[:5] if raw else ""
    # Simple invariant-breaker: start with a closing bracket that has no opener
    s = "]" + seed_str + "["
    return (s,), False  # expected is always False


HYPOTHESIS_CASES = [
    # Valid strings — always expect True
    (
        st.tuples(
            st.lists(st.integers(min_value=0, max_value=2), min_size=1, max_size=4),
            st.lists(
                st.text(
                    alphabet=st.characters(whitelist_categories=["Lu", "Ll"]),
                    max_size=3,
                ),
                min_size=1,
                max_size=4,
            ),
        ),
        _build_valid,
    ),
    # Invalid strings — always expect False
    (
        st.text(
            alphabet=st.characters(whitelist_categories=["Lu", "Ll"]),
            min_size=0,
            max_size=5,
        ),
        _build_invalid,
    ),
]
