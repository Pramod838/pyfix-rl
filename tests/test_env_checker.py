"""
Validate CodeRepairEnv using Gymnasium's official environment checker.

Run:
  python tests/test_env_checker.py          (standalone)
  python -m pytest tests/ -v                (via pytest)
"""

from __future__ import annotations

import sys
import os

# Allow running from the project root without installation
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_env_checker_all_tasks() -> None:
    from gymnasium.utils.env_checker import check_env
    from pyfix.env import CodeRepairEnv

    for task_id in [1, 2, 3, 4]:
        print(f"  Checking task {task_id} ({['easy','medium','hard','stretch'][task_id-1]})...",
              flush=True)
        env = CodeRepairEnv(task_id=task_id, render_mode="ansi")
        # skip_render_check=False validates the render() method too
        check_env(env, warn=True, skip_render_check=False)
        print(f"  Task {task_id}: OK", flush=True)
        env.close()


if __name__ == "__main__":
    print("Running Gymnasium environment checker on all tasks...")
    test_env_checker_all_tasks()
    print("\n✓ All environment checks passed.")
