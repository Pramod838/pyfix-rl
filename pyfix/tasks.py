"""
pyfix/tasks.py — Task dataclass and central registry.

Task files in tasks/ call _register() at import time to populate TASK_REGISTRY.
pyfix/env.py imports tasks/ to trigger registration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Task:
    task_id: int
    function_name: str
    description: str
    buggy_code: str
    public_examples: str


#: Populated by tasks/task*.py at import time
TASK_REGISTRY: Dict[int, Task] = {}


def _register(task: Task) -> Task:
    """Register a task in the global registry. Called by each task module."""
    TASK_REGISTRY[task.task_id] = task
    return task
