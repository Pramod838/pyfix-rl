"""
agent/human_agent.py — Manual stdin agent for walkthroughs and local testing.

Use this when no Groq API key is available, or for demonstrating the
environment interactively during the 30-minute technical walkthrough.

Usage:
  python run_episode.py --task 1 --agent human
"""

from __future__ import annotations

import sys


class HumanAgent:
    """Read a code fix from stdin. Fully valid per assignment instructions."""

    def act(self, obs: dict) -> str:
        print("\n" + "=" * 65)
        print(f"TASK {obs['attempts_remaining'] and '(attempt ' + str(4 - obs['attempts_remaining']) + '/3)' or ''}")
        print(f"\nDescription:\n{obs['description']}")
        print(f"\nBuggy code:\n{obs['buggy_code']}")
        print(f"\nPublic examples:\n{obs['public_examples']}")
        if obs.get("last_submission"):
            print(f"\n--- Previous submission ---\n{obs['last_submission']}")
            print(f"\n--- Error ---\n{obs.get('last_error') or '(none)'}")
        print(f"\nAttempts remaining: {obs['attempts_remaining']}")
        print("=" * 65)
        print("Paste your corrected function. Enter 'END' on a blank line to submit:\n")

        lines = []
        while True:
            line = sys.stdin.readline()
            if not line or line.strip() == "END":
                break
            lines.append(line.rstrip("\n"))
        return "\n".join(lines)
