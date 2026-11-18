"""
tests/test_env.py — Tests for CodeRepairEnv lifecycle and API.

Requires the worker to be running (uses `worker` fixture).
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


@pytest.fixture
def env1(worker):
    from pyfix.env import CodeRepairEnv
    e = CodeRepairEnv(task_id=1, max_attempts=3)
    yield e
    e.close()


class TestEnvReset:
    def test_reset_returns_obs_and_info(self, env1):
        obs, info = env1.reset()
        assert isinstance(obs, dict)
        assert isinstance(info, dict)

    def test_reset_initialises_attempts(self, env1):
        obs, _ = env1.reset()
        assert obs["attempts_remaining"] == 3

    def test_reset_clears_last_submission(self, env1):
        obs, _ = env1.reset()
        assert obs["last_submission"] == ""

    def test_reset_clears_last_error(self, env1):
        obs, _ = env1.reset()
        assert obs["last_error"] == ""

    def test_reset_buggy_code_present(self, env1):
        obs, _ = env1.reset()
        assert "reverse_words" in obs["buggy_code"]
        assert "split" in obs["buggy_code"]

    def test_reset_description_present(self, env1):
        obs, _ = env1.reset()
        assert len(obs["description"]) > 0

    def test_obs_in_observation_space(self, env1):
        obs, _ = env1.reset()
        assert env1.observation_space.contains(obs)

    def test_multiple_resets_allowed(self, env1):
        for _ in range(3):
            obs, _ = env1.reset()
            assert obs["attempts_remaining"] == 3


class TestEnvStep:
    def test_step_returns_5tuple(self, env1):
        env1.reset()
        result = env1.step("def reverse_words(s): return s")
        assert len(result) == 5

    def test_step_decrements_attempts(self, env1):
        env1.reset()
        obs, _, _, _, _ = env1.step("def reverse_words(s): return s")
        assert obs["attempts_remaining"] == 2

    def test_correct_code_terminates(self, env1):
        env1.reset()
        correct = 'def reverse_words(s): return " ".join(s.split()[::-1])'
        _, reward, terminated, truncated, info = env1.step(correct)
        assert reward == 1.0
        assert terminated is True
        assert truncated is False
        assert info["passed"] is True

    def test_buggy_code_no_terminate(self, env1):
        env1.reset()
        _, reward, terminated, truncated, info = env1.step("def reverse_words(s): return s")
        assert reward == 0.0
        assert terminated is False
        assert info["passed"] is False

    def test_truncation_after_max_attempts(self, env1):
        env1.reset()
        for i in range(2):
            _, _, term, trunc, _ = env1.step("def reverse_words(s): return s")
            assert not term and not trunc
        # Third (final) attempt
        _, reward, term, trunc, _ = env1.step("def reverse_words(s): return s")
        assert trunc is True
        assert term is False
        assert reward == 0.0

    def test_info_contains_only_agent_fields(self, env1):
        env1.reset()
        _, _, _, _, info = env1.step("def reverse_words(s): return s")
        assert set(info.keys()) == {"passed", "error_summary"}
        # Must not contain researcher-only fields
        assert "tests_passed" not in info
        assert "tests_total" not in info
        assert "per_test" not in info

    def test_step_raises_after_terminated(self, env1):
        env1.reset()
        correct = 'def reverse_words(s): return " ".join(s.split()[::-1])'
        env1.step(correct)  # terminates
        with pytest.raises(RuntimeError, match="Episode has ended"):
            env1.step(correct)

    def test_step_raises_after_truncated(self, env1):
        env1.reset()
        for _ in range(3):
            env1.step("def reverse_words(s): return s")
        with pytest.raises(RuntimeError, match="Episode has ended|No attempts remaining"):
            env1.step("def reverse_words(s): return s")

    def test_reset_re_enables_episode(self, env1):
        env1.reset()
        correct = 'def reverse_words(s): return " ".join(s.split()[::-1])'
        env1.step(correct)  # terminates
        env1.reset()       # should allow new episode
        obs, reward, _, _, _ = env1.step(correct)
        assert reward == 1.0

    def test_last_submission_updated(self, env1):
        env1.reset()
        action = "def reverse_words(s): return s"
        obs, _, _, _, _ = env1.step(action)
        assert obs["last_submission"] == action

    def test_markdown_fence_stripped(self, env1):
        env1.reset()
        fenced = '```python\ndef reverse_words(s):\n    return " ".join(s.split()[::-1])\n```'
        _, reward, term, _, _ = env1.step(fenced)
        assert reward == 1.0 and term is True


class TestEnvInit:
    def test_invalid_task_id(self):
        from pyfix.env import CodeRepairEnv
        with pytest.raises(ValueError, match="task_id"):
            CodeRepairEnv(task_id=99)

    def test_invalid_max_attempts(self):
        from pyfix.env import CodeRepairEnv
        with pytest.raises(ValueError, match="max_attempts"):
            CodeRepairEnv(task_id=1, max_attempts=0)

    def test_all_tasks_constructable(self):
        from pyfix.env import CodeRepairEnv
        for tid in [1, 2, 3, 4]:
            env = CodeRepairEnv(task_id=tid)
            assert env.task.task_id == tid
            env.close()


class TestTask4PartialReward:
    def test_full_reward(self, worker):
        from pyfix.env import CodeRepairEnv
        env = CodeRepairEnv(task_id=4, max_attempts=3)
        env.reset()
        correct = (
            'def matrix_multiply(A, B):\n'
            '    if not A or not A[0] or not B or not B[0]: raise ValueError("E")\n'
            '    if any(len(r)!=len(A[0]) for r in A): raise ValueError("R")\n'
            '    if any(len(r)!=len(B[0]) for r in B): raise ValueError("R")\n'
            '    if len(A[0])!=len(B): raise ValueError("D")\n'
            '    C=[[0.0]*len(B[0]) for _ in range(len(A))]\n'
            '    for i in range(len(A)):\n'
            '        for j in range(len(B[0])):\n'
            '            for k in range(len(A[0])): C[i][j]+=A[i][k]*B[k][j]\n'
            '    return C'
        )
        _, reward, term, _, info = env.step(correct)
        assert reward == pytest.approx(1.0, abs=0.01)
        assert term is True
        env.close()
