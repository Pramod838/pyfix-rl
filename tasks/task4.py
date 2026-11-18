"""
Task 4 (Stretch) — matrix_multiply
Original function. Three bugs with partial-credit reward.
"""

from pyfix.tasks import Task, _register

task4 = _register(Task(
    task_id=4,
    function_name="matrix_multiply",
    description=(
        "Multiply matrix A (m x n) by matrix B (n x p) and return the result (m x p).\n"
        "Return values should be floats.\n"
        "Raise ValueError if:\n"
        "  - Either matrix is empty or ragged (rows of unequal length)\n"
        "  - Dimensions are incompatible: len(A[0]) != len(B)\n\n"
        "Examples:\n"
        "  matrix_multiply([[1,2],[3,4]], [[5,6],[7,8]])\n"
        "    -> [[19.0, 22.0], [43.0, 50.0]]\n"
        "  matrix_multiply([[1,2,3]], [[4],[5],[6]])\n"
        "    -> [[32.0]]"
    ),
    buggy_code="""\
# Original function. Three bugs introduced for RL training research.

def matrix_multiply(A: list, B: list) -> list:
    \"\"\"Multiply matrix A (m x n) by matrix B (n x p). Returns m x p matrix.\"\"\"
    # Bug 3: no dimension or validity check (should raise ValueError)
    rows_A, cols_A, cols_B = len(A), len(A[0]), len(B[0])
    C = [[0.0] * rows_A for _ in range(cols_B)]  # Bug 2: dimensions transposed
    for i in range(rows_A):
        for j in range(cols_B):
            for k in range(cols_A):
                C[i][j] += A[i][k] * B[j][k]    # Bug 1: B[j][k] instead of B[k][j]
    return C
""",
    public_examples=(
        ">>> matrix_multiply([[1,2],[3,4]], [[5,6],[7,8]])\n"
        "[[19.0, 22.0], [43.0, 50.0]]\n"
        ">>> matrix_multiply([[1,2,3]], [[4],[5],[6]])\n"
        "[[32.0]]"
    ),
))
