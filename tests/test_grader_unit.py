"""
tests/test_grader_unit.py — Unit tests for grader logic (no worker required).

Tests pure-Python functions: is_obviously_broken, _values_equal, _summarise_error.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from grader.anti_gaming import is_obviously_broken
from grader.grade import _values_equal, _summarise_error


class TestIsObviouslyBroken:
    """Tests for the AST-based heuristic checker."""

    def test_valid_function(self):
        broken, _ = is_obviously_broken("def f(x): return x + 1")
        assert not broken

    def test_syntax_error(self):
        broken, reason = is_obviously_broken("def f(x: return x")
        assert broken
        assert "SyntaxError" in reason

    def test_bare_constant_int(self):
        broken, reason = is_obviously_broken("def f(x): return 42")
        assert broken
        assert "bare constant" in reason

    def test_bare_constant_string(self):
        broken, reason = is_obviously_broken("def f(x): return 'hello'")
        assert broken

    def test_bare_constant_none(self):
        broken, reason = is_obviously_broken("def f(x): return None")
        assert broken

    def test_bare_constant_bool(self):
        # 'return True' is also a constant — catches "def f(): return True"
        broken, reason = is_obviously_broken("def f(x): return True")
        assert broken

    def test_multi_statement_not_broken(self):
        code = "def f(x):\n    result = x + 1\n    return result"
        broken, _ = is_obviously_broken(code)
        assert not broken

    def test_conditional_return(self):
        code = "def f(x):\n    if x: return True\n    return False"
        broken, _ = is_obviously_broken(code)
        assert not broken

    def test_empty_code(self):
        broken, reason = is_obviously_broken("")
        # Empty code is valid Python (empty module) but has no function — not broken by our check
        assert not broken


class TestValuesEqual:
    """Tests for type-aware deep equality."""

    # Bool / int separation
    def test_bool_true_equals_true(self):
        assert _values_equal(True, True)

    def test_bool_false_equals_false(self):
        assert _values_equal(False, False)

    def test_bool_true_not_int_one(self):
        assert not _values_equal(True, 1)

    def test_int_one_not_bool_true(self):
        assert not _values_equal(1, True)

    def test_bool_false_not_int_zero(self):
        assert not _values_equal(False, 0)

    def test_int_zero_not_bool_false(self):
        assert not _values_equal(0, False)

    # Float tolerance
    def test_float_equal_exact(self):
        assert _values_equal(2.0, 2.0)

    def test_float_equal_tolerance(self):
        assert _values_equal(2.0 + 1e-10, 2.0)

    def test_float_not_equal(self):
        assert not _values_equal(2.0, 2.1)

    def test_int_float_cross(self):
        assert _values_equal(2, 2.0)
        assert _values_equal(2.0, 2)

    def test_int_float_cross_not_equal(self):
        assert not _values_equal(2, 3.0)

    # String comparison
    def test_strings_equal(self):
        assert _values_equal("hello", "hello")

    def test_strings_not_equal(self):
        assert not _values_equal("hello", "world")

    # List comparison
    def test_lists_equal(self):
        assert _values_equal([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])

    def test_lists_different_length(self):
        assert not _values_equal([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_lists_int_float_equal(self):
        assert _values_equal([2, 3], [2.0, 3.0])

    def test_nested_lists(self):
        assert _values_equal([[1.0, 2.0], [3.0, 4.0]], [[1.0, 2.0], [3.0, 4.0]])

    def test_nested_lists_not_equal(self):
        assert not _values_equal([[1.0, 2.0]], [[1.0, 3.0]])

    def test_bool_in_list(self):
        # List containing bool vs list containing int — should not be equal
        assert not _values_equal([True, False], [1, 0])


class TestSummariseError:
    """Tests for safe agent-facing error summarisation."""

    def test_empty_per_test(self):
        assert _summarise_error([]) == ""

    def test_all_passed(self):
        result = _summarise_error([{"passed": True, "error": ""}])
        assert result == ""

    def test_first_failure_shown(self):
        per_test = [
            {"passed": False, "error": "TypeError: bad type"},
            {"passed": False, "error": "ValueError: bad value"},
        ]
        summary = _summarise_error(per_test)
        assert "TypeError" in summary
        assert len(summary) <= 200

    def test_no_expected_values_leaked(self):
        # Error containing "expected [2.0, 3.0]" must be sanitised
        per_test = [{"passed": False, "error": "got [1.0, 2.0] expected [2.0, 3.0]"}]
        summary = _summarise_error(per_test)
        assert "[2.0, 3.0]" not in summary
        assert "[1.0, 2.0]" not in summary

    def test_assert_pattern_removed(self):
        per_test = [{"passed": False, "error": "assert result == [2.0, 3.0]"}]
        summary = _summarise_error(per_test)
        assert "[2.0, 3.0]" not in summary

    def test_truncated_at_200_chars(self):
        long_err = "TypeError: " + "x" * 300
        per_test = [{"passed": False, "error": long_err}]
        summary = _summarise_error(per_test)
        assert len(summary) <= 200
