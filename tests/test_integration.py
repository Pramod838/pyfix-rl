"""
tests/test_integration.py — End-to-end integration tests.

Tests the complete flow: env.step() → grader → worker → result → reward.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


CORRECT_FIXES = {
    1: 'def reverse_words(s): return " ".join(s.split()[::-1])',
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
}

BUGGY_FIXES = {
    1: 'def reverse_words(s): return " ".join(s.split(" ")[::-1])',
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
}


@pytest.mark.parametrize("task_id", [1, 2, 3])
def test_full_episode_correct_first_attempt(worker, task_id):
    """Correct code on first attempt: reward=1, terminated=True, truncated=False."""
    from pyfix.env import CodeRepairEnv
    env = CodeRepairEnv(task_id=task_id, max_attempts=3)
    obs, _ = env.reset()

    assert obs["buggy_code"]
    assert obs["last_submission"] == ""
    assert obs["attempts_remaining"] == 3

    obs2, reward, terminated, truncated, info = env.step(CORRECT_FIXES[task_id])

    assert reward == 1.0
    assert terminated is True
    assert truncated is False
    assert info["passed"] is True
    assert info["error_summary"] == ""
    assert obs2["last_submission"] == CORRECT_FIXES[task_id]
    assert obs2["attempts_remaining"] == 2  # one was used
    env.close()


@pytest.mark.parametrize("task_id", [1, 2, 3])
def test_full_episode_all_buggy_truncates(worker, task_id):
    """Three buggy attempts: reward=0, truncated=True after last attempt."""
    from pyfix.env import CodeRepairEnv
    env = CodeRepairEnv(task_id=task_id, max_attempts=3)
    env.reset()

    for i in range(2):
        _, r, term, trunc, _ = env.step(BUGGY_FIXES[task_id])
        assert r == 0.0 and not term and not trunc, f"Attempt {i+1} should not end episode"

    _, r, term, trunc, info = env.step(BUGGY_FIXES[task_id])
    assert r == 0.0
    assert trunc is True
    assert term is False
    assert info["passed"] is False
    env.close()


@pytest.mark.parametrize("task_id", [1, 2, 3])
def test_full_episode_refine_on_second_attempt(worker, task_id):
    """First attempt buggy, second attempt correct: solved on attempt 2."""
    from pyfix.env import CodeRepairEnv
    env = CodeRepairEnv(task_id=task_id, max_attempts=3)
    env.reset()

    # Attempt 1: buggy
    obs1, r, term, trunc, info = env.step(BUGGY_FIXES[task_id])
    assert r == 0.0 and not term
    assert obs1["last_submission"] == BUGGY_FIXES[task_id]
    assert obs1["attempts_remaining"] == 2

    # Attempt 2: correct
    obs2, r, term, trunc, info = env.step(CORRECT_FIXES[task_id])
    assert r == 1.0 and term is True
    assert obs2["attempts_remaining"] == 1
    env.close()


def test_no_expected_values_in_feedback(worker):
    """Agent feedback must never reveal expected test values."""
    from pyfix.env import CodeRepairEnv
    env = CodeRepairEnv(task_id=3, max_attempts=3)
    env.reset()

    # Submit buggy code for task 3
    _, _, _, _, info = env.step(BUGGY_FIXES[3])
    err = info["error_summary"]

    # Must not contain lists or numbers that look like expected output
    assert "[2.0, 3.0, 4.0]" not in err
    assert "[4.0, 7.0, 4.0]" not in err
    assert "expected 3" not in err.lower()   # expected length
    env.close()


def test_logs_created_on_grading(worker, tmp_path, monkeypatch):
    """Every grade_submission call must write to logs/."""
    from pyfix.env import CodeRepairEnv
    import grader.grade as gm

    # Redirect log directory to tmp_path
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    original_write = gm._write_log
    written = []

    def mock_write(result):
        written.append(result.task_id)
        original_write(result)

    monkeypatch.setattr(gm, "_write_log", mock_write)

    env = CodeRepairEnv(task_id=1, max_attempts=3)
    env.reset()
    env.step('def reverse_words(s): return s')
    env.step('def reverse_words(s): return " ".join(s.split()[::-1])')
    env.close()

    assert len(written) == 2, f"Expected 2 log writes, got {len(written)}"
