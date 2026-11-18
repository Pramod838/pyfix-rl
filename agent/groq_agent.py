"""
agent/groq_agent.py — Groq free-tier LLM agent.

Default model: gemma2-9b-it (configurable via GROQ_MODEL env var).
C8: llama-3.3-70b-versatile was shut down for free/dev tier on 16 Aug 2026.
On startup, lists available models so the user can verify compatibility.

Multi-turn within an episode: each step feeds last_submission + last_error
back into the prompt so the model can refine its fix.
"""

from __future__ import annotations

import os
import re

SYSTEM_PROMPT = """\
You are a Python debugging assistant.
You are given a buggy Python function. Your job is to find and fix all bugs.

RULES:
- Return ONLY the corrected function — nothing else.
- Do NOT include any explanation or commentary.
- Do NOT wrap the code in markdown fences.
- Keep the function signature exactly as given.
"""


def _build_prompt(obs: dict) -> str:
    parts = [
        "=== BUGGY FUNCTION ===",
        obs["buggy_code"],
        "",
        "=== TASK DESCRIPTION ===",
        obs["description"],
        "",
        "=== PUBLIC EXAMPLES ===",
        obs["public_examples"],
    ]
    if obs.get("last_submission"):
        parts += [
            "",
            "=== YOUR PREVIOUS ATTEMPT ===",
            obs["last_submission"],
            "",
            "=== ERROR FROM PREVIOUS ATTEMPT ===",
            obs.get("last_error") or "(no error details available)",
            "",
            "The previous attempt did not pass. Study the error above and fix the remaining issue(s).",
        ]
    parts += [
        "",
        "Return the corrected function ONLY. No explanation. No markdown.",
    ]
    return "\n".join(parts)


class GroqAgent:
    """LLM agent using the Groq free-tier API."""

    def __init__(self) -> None:
        from groq import Groq

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set. Copy .env.example to .env and add your key.\n"
                "Free account: https://console.groq.com"
            )

        self.client = Groq(api_key=api_key)
        self.model = os.environ.get("GROQ_MODEL", "gemma2-9b-it")

        # C8: list available models at startup so user can verify
        try:
            available = [m.id for m in self.client.models.list().data]
            print(f"[agent] Available Groq models: {available}")
            if self.model not in available:
                print(f"[agent] WARNING: '{self.model}' is NOT in the available list.")
                print(f"[agent] Set GROQ_MODEL to one of the above models.")
            else:
                print(f"[agent] Using model: {self.model}")
        except Exception as exc:
            print(f"[agent] Could not list models: {exc} — will attempt anyway")

    def act(self, obs: dict) -> str:
        """Return a code fix string given the current observation."""
        prompt = _build_prompt(obs)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        code = response.choices[0].message.content.strip()
        return _strip_fences(code)


def _strip_fences(code: str) -> str:
    """Remove markdown code fences if the model wrapped the response."""
    code = code.strip()
    m = re.match(r"^```(?:python)?\s*\n(.*?)```\s*$", code, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    return code
