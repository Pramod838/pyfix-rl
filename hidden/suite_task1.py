"""
Hidden test suite for Task 1: reverse_words.

TEST_CASES: fixed assertions (not shown to agent).
HYPOTHESIS_STRATEGY + adapt_input: property-based tests.

Reference: TheAlgorithms/Python strings/reverse_words.py commit 8fa4161587ab (MIT).
"""

from hypothesis import strategies as st

FUNCTION_NAME = "reverse_words"


def reference_fn(sentence: str) -> str:
    """The correct implementation — used to compute expected values."""
    return " ".join(sentence.split()[::-1])


# Fixed test cases: (args_tuple, expected_output)
# args_tuple is passed as *args to the submitted function.
TEST_CASES = [
    (("hello world",),          "world hello"),
    (("foo bar baz",),          "baz bar foo"),
    (("  hello   world  ",),    "world hello"),   # catches Bug: split(" ") vs split()
    (("single",),               "single"),
    (("a b  c",),               "c b a"),         # catches Bug: extra spaces
    (("",),                     ""),
    (("   ",),                  ""),               # all whitespace → empty
    (("A B C D",),              "D C B A"),
]

# C4 — Hypothesis input adapter for Task 1.
# Strategy generates (words, gap_counts, leading_spaces, trailing_spaces).
# Adapter builds a sentence with varied whitespace to reliably catch the bug.
HYPOTHESIS_STRATEGY = st.tuples(
    st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=["Lu", "Ll"]),
            min_size=1,
            max_size=8,
        ),
        min_size=1,
        max_size=5,
    ),
    st.lists(st.integers(min_value=1, max_value=3), min_size=0, max_size=4),
    st.integers(min_value=0, max_value=2),  # leading spaces
    st.integers(min_value=0, max_value=2),  # trailing spaces
)


def adapt_input(raw):
    """
    Convert (words, gap_counts, leading, trailing) → ((sentence,), expected).
    Builds a sentence with intentionally varied inter-word whitespace.
    """
    words, gap_counts, leading, trailing = raw
    parts = []
    for i, word in enumerate(words):
        parts.append(word)
        if i < len(words) - 1:
            sep = gap_counts[i] if i < len(gap_counts) else 1
            parts.append(" " * sep)
    sentence = " " * leading + "".join(parts) + " " * trailing
    expected = reference_fn(sentence)
    return (sentence,), expected
