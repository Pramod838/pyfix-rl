"""
tests/test_tasks.py — Verify correct and buggy code behaviours for all tasks.

Requires the worker to be running (uses `worker` fixture from conftest.py).
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

CORRECT = {
    1: 'def reverse_words(s):\n    return " ".join(s.split()[::-1])',
    2: (
        'def is_valid_brackets(s):\n'
        '    stack=[]; bm={")": "(", "]": "[", "}": "{"}\n'
        '    for c in s:\n'
        '        if c in "([{": stack.append(c)\n'
        '        elif c in ")]}": \n'
        '            if not stack or stack.pop()!=bm[c]: return False\n'
        '    return len(stack)==0'
    ),
    3: (
        'def compute_moving_average(data, window):\n'
        '    if window <= 0 or window > len(data): raise ValueError()\n'
        '    return [sum(data[i:i+window])/window for i in range(len(data)-window+1)]'
    ),
    4: (
        'def matrix_multiply(A, B):\n'
        '    if not A or not A[0] or not B or not B[0]: raise ValueError("Empty")\n'
        '    if any(len(r)!=len(A[0]) for r in A) or any(len(r)!=len(B[0]) for r in B): raise ValueError("Ragged")\n'
        '    if len(A[0])!=len(B): raise ValueError("Bad dims")\n'
        '    C=[[0.0]*len(B[0]) for _ in range(len(A))]\n'
        '    for i in range(len(A)):\n'
        '        for j in range(len(B[0])):\n'
        '            for k in range(len(A[0])): C[i][j]+=A[i][k]*B[k][j]\n'
        '    return C'
    ),
}

BUGGY = {
    1: 'def reverse_words(s):\n    return " ".join(s.split(" ")[::-1])',
    2: (
        'def is_valid_brackets(s):\n'
        '    stack=[]; bm={")": "(", "]": "[", "}": "{"}\n'
        '    for c in s:\n'
        '        if c in "([{": stack.append(c)\n'
        '        elif c in ")]}": \n'
        '            if stack and stack[-1]==bm[c]: stack.pop()\n'
        '    return True'
    ),
    3: (
        'def compute_moving_average(data, window):\n'
        '    if window <= 0 or window > len(data): raise ValueError()\n'
        '    result=[]\n'
        '    for i in range(len(data)):\n'
        '        wd=data[i:i+window+1]\n'
        '        if not wd: break\n'
        '        result.append(sum(wd)//len(wd))\n'
        '    return result'
    ),
    4: (
        'def matrix_multiply(A, B):\n'
        '    rows_A,cols_A,cols_B=len(A),len(A[0]),len(B[0])\n'
        '    C=[[0.0]*rows_A for _ in range(cols_B)]\n'
        '    for i in range(rows_A):\n'
        '        for j in range(cols_B):\n'
        '            for k in range(cols_A): C[i][j]+=A[i][k]*B[j][k]\n'
        '    return C'
    ),
}


@pytest.mark.parametrize("task_id", [1, 2, 3, 4])
def test_correct_code_passes(worker, task_id):
    from grader.grade import grade_submission
    result = grade_submission(CORRECT[task_id], task_id)
    assert result.reward == 1.0, f"Task {task_id} correct code should pass: {result.agent_feedback.error_summary}"
    assert result.agent_feedback.passed is True


@pytest.mark.parametrize("task_id", [1, 2, 3, 4])
def test_buggy_code_fails(worker, task_id):
    from grader.grade import grade_submission
    result = grade_submission(BUGGY[task_id], task_id)
    assert result.reward < 1.0, f"Task {task_id} buggy code should fail"
    assert result.agent_feedback.passed is False


def test_task2_bug1_independent(worker):
    """Fix Bug1 only — Bug2 (return True) must still block."""
    from grader.grade import grade_submission
    fix1_only = (
        'def is_valid_brackets(s):\n'
        '    stack=[]; bm={")": "(", "]": "[", "}": "{"}\n'
        '    for c in s:\n'
        '        if c in "([{": stack.append(c)\n'
        '        elif c in ")]}": \n'
        '            if not stack or stack.pop()!=bm[c]: return False\n'
        '    return True'  # Bug2 still present
    )
    result = grade_submission(fix1_only, 2)
    assert result.reward == 0.0, "Fix1-only should still fail due to Bug2"


def test_task2_bug2_independent(worker):
    """Fix Bug2 only — Bug1 (silent mismatch) must still block."""
    from grader.grade import grade_submission
    fix2_only = (
        'def is_valid_brackets(s):\n'
        '    stack=[]; bm={")": "(", "]": "[", "}": "{"}\n'
        '    for c in s:\n'
        '        if c in "([{": stack.append(c)\n'
        '        elif c in ")]}": \n'
        '            if stack and stack[-1]==bm[c]: stack.pop()\n'
        '    return len(stack)==0'  # Bug1 still present
    )
    result = grade_submission(fix2_only, 2)
    assert result.reward == 0.0, "Fix2-only should still fail due to Bug1"


def test_task2_returns_int_fails(worker):
    """Agent returning int (1/0) instead of bool must fail type check."""
    from grader.grade import grade_submission
    # This is caught by AST heuristic (bare constant) but validates the concept
    returns_one = 'def is_valid_brackets(s): return 1'
    result = grade_submission(returns_one, 2)
    assert not result.agent_feedback.passed


def test_task4_partial_credit_fix1_only(worker):
    """Fix Bug1 only → Category 1 reward (0.33)."""
    from grader.grade import grade_submission
    fix1 = (
        'def matrix_multiply(A, B):\n'
        '    rows_A,cols_A,cols_B=len(A),len(A[0]),len(B[0])\n'
        '    C=[[0.0]*rows_A for _ in range(cols_B)]\n'
        '    for i in range(rows_A):\n'
        '        for j in range(cols_B):\n'
        '            for k in range(cols_A): C[i][j]+=A[i][k]*B[k][j]\n'
        '    return C'
    )
    result = grade_submission(fix1, 4)
    assert result.reward == pytest.approx(0.33, abs=0.01)


def test_task4_partial_credit_fix3_only(worker):
    """Fix Bug3 only → Category 3 reward (0.34)."""
    from grader.grade import grade_submission
    fix3 = (
        'def matrix_multiply(A, B):\n'
        '    if not A or not A[0] or not B or not B[0]: raise ValueError("E")\n'
        '    if any(len(r)!=len(A[0]) for r in A): raise ValueError("R")\n'
        '    if any(len(r)!=len(B[0]) for r in B): raise ValueError("R")\n'
        '    if len(A[0])!=len(B): raise ValueError("D")\n'
        '    rows_A,cols_A,cols_B=len(A),len(A[0]),len(B[0])\n'
        '    C=[[0.0]*rows_A for _ in range(cols_B)]\n'  # Bug2 still
        '    for i in range(rows_A):\n'
        '        for j in range(cols_B):\n'
        '            for k in range(cols_A): C[i][j]+=A[i][k]*B[j][k]\n'  # Bug1 still
        '    return C'
    )
    result = grade_submission(fix3, 4)
    assert result.reward == pytest.approx(0.34, abs=0.01)


def test_task3_invalid_window_raises(worker):
    """Correct implementation must raise ValueError for invalid window."""
    from grader.grade import grade_submission
    # Correct code that handles all cases
    result = grade_submission(CORRECT[3], 3)
    assert result.agent_feedback.passed is True


def test_task3_missing_valueerror_fails(worker):
    """Code that doesn't raise ValueError for invalid window must fail."""
    from grader.grade import grade_submission
    no_check = (
        'def compute_moving_average(data, window):\n'
        '    return [sum(data[i:i+window])/window for i in range(len(data)-window+1)]'
    )
    result = grade_submission(no_check, 3)
    # Should fail the INVALID_CASES since no ValueError is raised
    assert not result.agent_feedback.passed


def test_task3_int_list_rejected(worker):
    """
    Task 3 requires float output. Returning a list of integers must fail even
    if the numeric values are correct (e.g. [2, 3, 4] instead of [2.0, 3.0, 4.0]).
    """
    from grader.grade import grade_submission
    # Returns int via integer division; values numerically correct but wrong type
    int_code = (
        'def compute_moving_average(data, window):\n'
        '    if window <= 0 or window > len(data): raise ValueError()\n'
        '    return [sum(data[i:i+window])//window for i in range(len(data)-window+1)]\n'
    )
    result = grade_submission(int_code, 3)
    assert not result.agent_feedback.passed, (
        "Integer list must be rejected — Task 3 requires float output"
    )


def test_task4_int_matrix_rejected(worker):
    """
    Task 4 requires float matrix elements. Returning integers must fail even
    if the numeric values are correct.
    """
    from grader.grade import grade_submission
    # Correct logic but uses integer arithmetic — returns int elements
    int_matrix_code = (
        'def matrix_multiply(A, B):\n'
        '    if not A or not A[0] or not B or not B[0]: raise ValueError("E")\n'
        '    if any(len(r)!=len(A[0]) for r in A): raise ValueError("R")\n'
        '    if any(len(r)!=len(B[0]) for r in B): raise ValueError("R")\n'
        '    if len(A[0])!=len(B): raise ValueError("D")\n'
        '    C=[[0]*len(B[0]) for _ in range(len(A))]\n'  # int 0, not float 0.0
        '    for i in range(len(A)):\n'
        '        for j in range(len(B[0])):\n'
        '            for k in range(len(A[0])): C[i][j]+=A[i][k]*B[k][j]\n'
        '    return C\n'
    )
    result = grade_submission(int_matrix_code, 4)
    assert not result.agent_feedback.passed, (
        "Integer matrix must be rejected — Task 4 requires float elements"
    )


def test_task3_runtimeerror_does_not_pass_invalid_window(worker):
    """
    Raising RuntimeError with 'ValueError' in its message must NOT pass the
    invalid-window test. Only an actual ValueError satisfies the check.
    """
    from grader.grade import grade_submission
    fake_valueerror = (
        'def compute_moving_average(data, window):\n'
        '    if window <= 0 or window > len(data):\n'
        '        raise RuntimeError("ValueError occurred for invalid window")\n'
        '    return [sum(data[i:i+window])/window for i in range(len(data)-window+1)]\n'
    )
    result = grade_submission(fake_valueerror, 3)
    # RuntimeError does not start with "ValueError:" so invalid cases must fail
    assert not result.agent_feedback.passed, (
        "RuntimeError with 'ValueError' in message must NOT satisfy the ValueError check"
    )
