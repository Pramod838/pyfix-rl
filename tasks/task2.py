"""
Task 2 (Medium) — is_valid_brackets
Adapted from TheAlgorithms/Python data_structures/stacks/balanced_parentheses.py
Commit 4a766c632cd6 | MIT Licence
Adaptations: (a) custom Stack replaced with list, (b) map direction changed,
             (c) function renamed. Two independent bugs introduced.
"""

from pyfix.tasks import Task, _register

task2 = _register(Task(
    task_id=2,
    function_name="is_valid_brackets",
    description=(
        "Return True if every opening bracket in the string has a matching\n"
        "closing bracket in the correct order. Return False otherwise.\n"
        "Supported brackets: () [] {}\n"
        "Non-bracket characters are silently ignored.\n\n"
        "Examples:\n"
        '  is_valid_brackets("()")       -> True\n'
        '  is_valid_brackets("({[]})")   -> True\n'
        '  is_valid_brackets("([)]")     -> False  (wrong order)\n'
        '  is_valid_brackets("((")       -> False  (unclosed)\n'
        '  is_valid_brackets("")         -> True'
    ),
    buggy_code="""\
# Adapted from: TheAlgorithms/Python data_structures/stacks/balanced_parentheses.py
# Original commit: 4a766c632cd6 (MIT Licence)
# Adaptations: custom Stack class replaced with list; map direction changed;
#              function renamed. Two bugs introduced for RL training research.

def is_valid_brackets(s: str) -> bool:
    \"\"\"Return True if brackets in s are balanced, False otherwise.\"\"\"
    stack = []
    bracket_map = {")": "(", "]": "[", "}": "{"}
    for char in s:
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if stack and stack[-1] == bracket_map[char]:  # Bug 1: silently ignores mismatches
                stack.pop()                               # (no early return False on wrong pair)
    return True  # Bug 2: should be len(stack) == 0
""",
    public_examples=(
        '>>> is_valid_brackets("()")\n'
        "True\n"
        '>>> is_valid_brackets("({[]})")\n'
        "True\n"
        '>>> is_valid_brackets("([)]")\n'
        "False\n"
        '>>> is_valid_brackets("((")\n'
        "False"
    ),
))
