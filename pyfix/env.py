"""
pyfix/env.py — CodeRepairEnv: Gymnasium-compatible RL environment.

Formal specification:
  Name:               pyfix-rl / CodeRepairEnv
  Gymnasium version:  >= 0.26.0
  Reward range:       [0.0, 1.0]
  Max episode steps:  3  (max_attempts parameter, default)
  Deterministic:      Yes given same seed
  Render modes:       ["ansi"]

Episode dynamics:
  reset() → obs₀ (last_submission="", last_error="", attempts_remaining=3)
  step(action) → obs, reward, terminated, truncated, info
    terminated = True  iff  reward == 1.0  (success; natural end condition)
    truncated  = True  iff  reward < 1.0 and attempts_remaining == 0
    info = {"passed": bool, "error_summary": str}  — AgentFeedback only

Stepping after episode ends (terminated or truncated without reset) raises
RuntimeError. Call env.reset() before the next episode.
"""

from __future__ import annotations

import dataclasses
import re
import string
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
from gymnasium import spaces

from pyfix.tasks import TASK_REGISTRY, Task

# Import tasks package so all 4 tasks are registered in TASK_REGISTRY
import tasks  # noqa: F401 — side-effect import


class CodeRepairEnv(gym.Env):
    """
    Code-repair RL environment.

    The agent observes a buggy Python function and must submit a corrected
    version. It receives a binary reward (or partial-credit for Task 4) from
    an independent judge. Up to `max_attempts` attempts per episode.
    """

    metadata = {"render_modes": ["ansi"], "render_fps": 4}

    def __init__(
        self,
        task_id: int = 1,
        max_attempts: int = 3,
        render_mode: Optional[str] = None,
    ) -> None:
        super().__init__()

        if task_id not in TASK_REGISTRY:
            raise ValueError(
                f"task_id {task_id} not in registry {sorted(TASK_REGISTRY.keys())}"
            )
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

        self.task: Task = TASK_REGISTRY[task_id]
        self.max_attempts = max_attempts
        self.render_mode = render_mode

        _ch = string.printable  # charset covers all Python source characters

        self.observation_space = spaces.Dict({
            "buggy_code":         spaces.Text(min_length=0, max_length=4096,  charset=_ch),
            "description":        spaces.Text(min_length=0, max_length=1024,  charset=_ch),
            "public_examples":    spaces.Text(min_length=0, max_length=2048,  charset=_ch),
            "last_submission":    spaces.Text(min_length=0, max_length=4096,  charset=_ch),
            "last_error":         spaces.Text(min_length=0, max_length=512,   charset=_ch),
            "attempts_remaining": spaces.Discrete(max_attempts + 1),
        })

        self.action_space = spaces.Text(min_length=1, max_length=4096, charset=_ch)

        # Internal episode state — initialised to invalid sentinel until reset()
        self._attempts_remaining: int = 0
        self._last_submission: str = ""
        self._last_error: str = ""
        self._episode_active: bool = False

    # ------------------------------------------------------------------
    # Gymnasium 0.26+ API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        super().reset(seed=seed)
        self._attempts_remaining = self.max_attempts
        self._last_submission = ""
        self._last_error = ""
        self._episode_active = True
        return self._make_obs(), {}

    def step(
        self,
        action: str,
    ) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        """
        Submit a code fix and receive a reward signal.

        Returns (obs, reward, terminated, truncated, info) per Gymnasium 0.26+.
        info contains only AgentFeedback fields — never test counts or expected values.

        Raises RuntimeError if called after the episode has ended without reset().
        """
        if not self._episode_active:
            raise RuntimeError(
                "Episode has ended (terminated or truncated). "
                "Call env.reset() to start a new episode."
            )
        if self._attempts_remaining <= 0:
            raise RuntimeError(
                "No attempts remaining. Call env.reset() to start a new episode."
            )

        # Lazy import avoids circular dependency
        from grader.grade import grade_submission

        # Strip markdown code fences if the agent wrapped the code
        clean_action = _strip_fences(action)

        # Grade in the trusted grader process
        result = grade_submission(clean_action, self.task.task_id)

        self._attempts_remaining -= 1
        self._last_submission = clean_action
        self._last_error = result.agent_feedback.error_summary

        reward = result.reward
        terminated = result.agent_feedback.passed
        truncated = not result.agent_feedback.passed and self._attempts_remaining == 0

        # Mark episode inactive when it ends
        if terminated or truncated:
            self._episode_active = False

        # C7: expose only AgentFeedback fields to the agent
        info = dataclasses.asdict(result.agent_feedback)
        return self._make_obs(), reward, terminated, truncated, info

    def render(self) -> Optional[str]:
        if self.render_mode == "ansi":
            lines = [
                f"┌─ Task {self.task.task_id}: {self.task.function_name} ─────────────",
                f"│  Attempts remaining: {self._attempts_remaining}/{self.max_attempts}",
                f"│  Last error: {self._last_error or '(none)'}",
                "└─────────────────────────────────────────────────",
            ]
            text = "\n".join(lines)
            print(text)
            return text
        return None

    def close(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_obs(self) -> Dict[str, Any]:
        return {
            "buggy_code":         self.task.buggy_code,
            "description":        self.task.description,
            "public_examples":    self.task.public_examples,
            "last_submission":    self._last_submission,
            "last_error":         self._last_error,
            "attempts_remaining": self._attempts_remaining,
        }


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if present."""
    code = code.strip()
    m = re.match(r"^```(?:python)?\s*\n(.*?)```\s*$", code, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    return code
