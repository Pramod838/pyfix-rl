"""
Hidden test suite for Task 3: compute_moving_average.

Bug A: slice too wide (data[i:i+window+1]).
Bug B: too many iterations (range(len(data)) vs range(len(data)-window+1)).
Bug C: integer division (//).

Each bug is independently detectable by the test cases below.
C9: grader performs explicit length check before value check.
"""

from hypothesis import strategies as st

FUNCTION_NAME = "compute_moving_average"


def reference_fn(data: list, window: int) -> list:
    """The correct implementation."""
    if window <= 0 or window > len(data):
        raise ValueError(f"window must be 1..{len(data)}")
    return [
        sum(data[i:i + window]) / window
        for i in range(len(data) - window + 1)
    ]


# Fixed test cases: (args_tuple, expected_output)
# args_tuple is (data, window) — grader calls fn(*args_tuple) = fn(data, window).
# "ValueError" sentinel means the grader expects a ValueError to be raised.
TEST_CASES = [
    (([1, 2, 3, 4, 5], 3),      [2.0, 3.0, 4.0]),         # basic — also checks length
    (([1, 10, 1, 10, 1], 3),    [4.0, 7.0, 4.0]),          # catches Bug A (wider slice)
    (([1, 2, 4], 2),             [1.5, 3.0]),               # catches Bug C (integer div)
    (([5.0], 1),                 [5.0]),                    # edge: window == len(data)
    (([1, 2], 1),                [1.0, 2.0]),               # window = 1
    (([0.5, 1.5, 2.5, 3.5], 2), [1.0, 2.0, 3.0]),          # floats
    (([10, 20, 30], 3),          [20.0]),                   # window == len, single output
    (([1, 3], 2),                [2.0]),                    # catches Bug C (1+3)//2 = 2 vs 2.0
]

# Invalid window test cases — grader expects ValueError for these
INVALID_CASES = [
    ([1, 2, 3], 0),     # window = 0: invalid
    ([1, 2, 3], -1),    # window negative: invalid
    ([1, 2, 3], 4),     # window > len(data): invalid
    ([1], 2),           # window > len(data): invalid
]


# C4 — Hypothesis adapter for Task 3.
# Strategy generates (data: list[float], window: int) with window <= len(data).
# Adapter unpacks these as separate arguments.
HYPOTHESIS_STRATEGY = st.tuples(
    st.lists(
        st.floats(
            min_value=-100.0,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        min_size=1,
        max_size=15,
    ),
    st.integers(min_value=1, max_value=5),
).filter(lambda t: t[1] <= len(t[0]))


def adapt_input(raw):
    """
    C4 — Unpack (data, window) tuple into args_tuple and expected.
    args_tuple = (data, window) so grader calls fn(data, window).
    """
    data, window = raw
    expected = reference_fn(data, window)
    return (data, window), expected
