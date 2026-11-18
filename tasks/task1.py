"""
Task 1 (Easy) — reverse_words
Adapted from TheAlgorithms/Python strings/reverse_words.py
Commit 8fa4161587ab | MIT Licence
Bug introduced: .split(" ") instead of .split()
"""

from pyfix.tasks import Task, _register

task1 = _register(Task(
    task_id=1,
    function_name="reverse_words",
    description=(
        "Reverse the order of words in a sentence.\n"
        "Leading and trailing whitespace must be stripped.\n"
        "Multiple consecutive spaces between words must be collapsed to one.\n\n"
        "Examples:\n"
        '  reverse_words("hello world")       -> "world hello"\n'
        '  reverse_words("foo bar baz")       -> "baz bar foo"\n'
        '  reverse_words("  hello   world  ") -> "world hello"'
    ),
    buggy_code="""\
# Adapted from: TheAlgorithms/Python strings/reverse_words.py (MIT Licence)
# Original commit: 8fa4161587ab
# Bug introduced for RL training research.

def reverse_words(sentence: str) -> str:
    \"\"\"Reverse the order of words in a sentence.\"\"\"
    return " ".join(sentence.split(" ")[::-1])
""",
    public_examples=(
        '>>> reverse_words("hello world")\n'
        "'world hello'\n"
        '>>> reverse_words("foo bar baz")\n'
        "'baz bar foo'\n"
        '>>> reverse_words("single")\n'
        "'single'"
    ),
))
