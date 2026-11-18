#!/usr/bin/env python3
"""
run_episode.py — Run a single pyfix-rl episode and report results.

Usage:
  python run_episode.py --task 1 --agent groq
  python run_episode.py --task 2 --agent human
  docker compose run --rm grader python run_episode.py --task 1 --agent groq

Tasks:  1 = easy (reverse_words)
        2 = medium (is_valid_brackets)
        3 = hard (compute_moving_average)
        4 = stretch / partial credit (matrix_multiply)
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a pyfix-rl episode.")
    parser.add_argument(
        "--task", type=int, required=True, choices=[1, 2, 3, 4],
        help="Task ID: 1=easy  2=medium  3=hard  4=stretch"
    )
    parser.add_argument(
        "--agent", choices=["groq", "human"], default="human",
        help="Agent type. Use 'human' if no Groq API key is available."
    )
    args = parser.parse_args()

    from pyfix.env import CodeRepairEnv

    if args.agent == "groq":
        from agent.groq_agent import GroqAgent
        agent = GroqAgent()
    else:
        from agent.human_agent import HumanAgent
        agent = HumanAgent()

    env = CodeRepairEnv(task_id=args.task, max_attempts=3, render_mode="ansi")
    obs, _ = env.reset()

    banner = f"pyfix-rl  |  Task {args.task}: {env.task.function_name}"
    print(f"\n{'='*len(banner)}")
    print(banner)
    print(f"{'='*len(banner)}\n")

    episode_log = []
    total_reward = 0.0
    start = time.monotonic()

    for attempt_num in range(1, 4):
        print(f"--- Attempt {attempt_num}/3 ---")
        action = agent.act(obs)
        preview = action[:300].replace("\n", "\\n")
        print(f"[agent] Submitting: {preview}{'...' if len(action) > 300 else ''}")

        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        entry = {
            "attempt": attempt_num,
            "reward": reward,
            "passed": info["passed"],
            "error_summary": info["error_summary"],
        }
        episode_log.append(entry)

        status = "✓ PASSED" if info["passed"] else "✗ FAILED"
        print(f"[env]   {status}  reward={reward:.2f}")
        if info["error_summary"]:
            print(f"[env]   Error: {info['error_summary']}")
        print()

        if terminated:
            print(f"✓ Task solved on attempt {attempt_num}!")
            break
        if truncated:
            print(f"✗ All 3 attempts exhausted without solving the task.")
            break

    elapsed = time.monotonic() - start
    summary = {
        "task_id": args.task,
        "function": env.task.function_name,
        "agent": args.agent,
        "solved": any(e["passed"] for e in episode_log),
        "attempts_used": len(episode_log),
        "total_reward": round(total_reward, 2),
        "attempts": episode_log,
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    print(f"\n{'='*50}")
    print(f"Episode summary:")
    print(json.dumps(summary, indent=2))
    print(f"{'='*50}\n")

    env.close()
    sys.exit(0 if summary["solved"] else 1)


if __name__ == "__main__":
    main()
