"""
Hidden test suite for Task 4: matrix_multiply.

Partial-credit reward:
  Category 1 (0.33): 2×2 matrix correctness — requires Fix 1 only.
  Category 2 (0.33): non-square matrix correctness — requires Fix 1 AND Fix 2.
  Category 3 (0.34): ValueError on bad/incompatible input — requires Fix 3 only.

Category definitions are strict:
  - Category 1: A is 2×2, B is 2×2 (output is always 2×2).
  - Category 2: genuinely non-square — rows_A ≠ cols_B in the output shape.
  - Category 3: inputs that must raise ValueError.

The two separate HYPOTHESIS_STRATEGY_CATn strategies ensure hypothesis-generated
tests honour these definitions. Square matrices that are not 2×2 are excluded from
both categories to avoid ambiguity.

C6: empty and ragged matrices are explicitly unsupported (raise ValueError).
"""

from hypothesis import strategies as st

FUNCTION_NAME = "matrix_multiply"


def reference_fn(A: list, B: list) -> list:
    """The correct implementation with all three fixes applied."""
    # C6: validate input
    if not A or not A[0] or not B or not B[0]:
        raise ValueError("Empty matrix")
    if any(len(row) != len(A[0]) for row in A):
        raise ValueError("Ragged matrix — all rows of A must have equal length")
    if any(len(row) != len(B[0]) for row in B):
        raise ValueError("Ragged matrix — all rows of B must have equal length")
    if len(A[0]) != len(B):
        raise ValueError(
            f"Cannot multiply {len(A)}x{len(A[0])} by {len(B)}x{len(B[0])}"
        )
    rows_A, cols_A, cols_B = len(A), len(A[0]), len(B[0])
    C = [[0.0] * cols_B for _ in range(rows_A)]
    for i in range(rows_A):
        for j in range(cols_B):
            for k in range(cols_A):
                C[i][j] += A[i][k] * B[k][j]
    return C


# TEST_CASES_WITH_CATEGORY: (args_tuple, expected_or_sentinel, category)
# For category 3: expected is the string "ValueError" (sentinel); grader checks exception.
TEST_CASES_WITH_CATEGORY = [
    # --- Category 1: 2×2 correctness ---
    (([[1, 2], [3, 4]], [[5, 6], [7, 8]]),       [[19.0, 22.0], [43.0, 50.0]], 1),
    (([[1, 0], [0, 1]], [[2, 3], [4, 5]]),        [[2.0, 3.0], [4.0, 5.0]],    1),  # identity
    (([[2, 2], [2, 2]], [[1, 1], [1, 1]]),        [[4.0, 4.0], [4.0, 4.0]],    1),
    # --- Category 2: non-square matrices (rows_A ≠ cols_B) ---
    (([[1, 2, 3]], [[4], [5], [6]]),              [[32.0]],                     2),  # 1×3 × 3×1 → 1×1
    (([[1, 2], [3, 4], [5, 6]], [[7, 8], [9, 10]]),
     [[25.0, 28.0], [57.0, 64.0], [89.0, 100.0]], 2),                               # 3×2 × 2×2 → 3×2
    (([[1, 0, 0]], [[1], [0], [0]]),              [[1.0]],                     2),  # 1×3 × 3×1 → 1×1
    # --- Category 3: ValueError on bad input ---
    (([[1, 2, 3]], [[4, 5], [6, 7]]),            "ValueError",                 3),  # 1×3 × 2×2: incompatible
    (([[1, 2]], [[3, 4]]),                        "ValueError",                 3),  # 1×2 × 1×2: incompatible
    (([[]], [[]]),                                "ValueError",                 3),  # empty matrix
    (([[1, 2], [3]], [[4], [5]]),                 "ValueError",                 3),  # ragged A
]


# ---------------------------------------------------------------------------
# Hypothesis strategies — separated by category to avoid ambiguity
# ---------------------------------------------------------------------------

# Category 1: always 2×2 × 2×2 → 2×2 output
HYPOTHESIS_STRATEGY_CAT1 = st.tuples(
    st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),  # fill_base
    st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False),  # offset
)


def adapt_input_cat1(raw):
    """Build a 2×2 × 2×2 matrix pair."""
    fill, offset = raw
    A = [
        [float(fill + i * 2 + j) for j in range(2)]
        for i in range(2)
    ]
    B = [
        [float(fill + offset + i + j * 2) for j in range(2)]
        for i in range(2)
    ]
    expected = reference_fn(A, B)
    return (A, B), expected


# Category 2: genuinely non-square — rows_A ≠ cols_B
# Constraint: rows_A and cols_B differ so the output matrix is non-square.
HYPOTHESIS_STRATEGY_CAT2 = st.tuples(
    st.integers(min_value=1, max_value=4),  # rows_A
    st.integers(min_value=1, max_value=4),  # shared dimension (cols_A = rows_B)
    st.integers(min_value=1, max_value=4),  # cols_B
    st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
).filter(lambda t: t[0] != t[2])  # rows_A ≠ cols_B → genuinely non-square output


def adapt_input_cat2(raw):
    """Build a non-square matrix pair (rows_A ≠ cols_B)."""
    rows_A, shared, cols_B, fill = raw
    A = [
        [float(fill + i * shared + j) for j in range(shared)]
        for i in range(rows_A)
    ]
    B = [
        [float(fill + i + j * cols_B) for j in range(cols_B)]
        for i in range(shared)
    ]
    expected = reference_fn(A, B)
    return (A, B), expected


# Keep adapt_input for backwards compatibility (used in tests)
def adapt_input(raw):
    """Alias to adapt_input_cat2 for backwards-compatible test usage."""
    return adapt_input_cat2(raw)
