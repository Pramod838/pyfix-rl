"""
Task 3 (Hard) — compute_moving_average
Original function. Three independent bugs introduced.
"""

from pyfix.tasks import Task, _register

task3 = _register(Task(
    task_id=3,
    function_name="compute_moving_average",
    description=(
        "Return a list of float moving averages using a sliding window.\n"
        "Output length must be exactly len(data) - window + 1.\n"
        "Each element is the mean of a consecutive sub-list of length window.\n"
        "Values must be floats, not integers.\n"
        "Raise ValueError if window <= 0 or window > len(data).\n\n"
        "Examples:\n"
        "  compute_moving_average([1, 2, 3, 4, 5], 3) -> [2.0, 3.0, 4.0]\n"
        "  compute_moving_average([1, 2, 4], 2)        -> [1.5, 3.0]\n"
        "  compute_moving_average([5.0], 1)            -> [5.0]"
    ),
    buggy_code="""\
# Original function. Three bugs introduced for RL training research.

def compute_moving_average(data: list, window: int) -> list:
    \"\"\"Return a list of moving averages with the given window size.\"\"\"
    if window <= 0 or window > len(data):
        raise ValueError(f"window must be 1..{len(data)}")
    result = []
    for i in range(len(data)):                      # Bug B: too many iterations
        window_data = data[i : i + window + 1]      # Bug A: slice one too wide
        if not window_data:
            break
        avg = sum(window_data) // len(window_data)  # Bug C: integer division
        result.append(avg)
    return result
""",
    public_examples=(
        ">>> compute_moving_average([1, 2, 3, 4, 5], 3)\n"
        "[2.0, 3.0, 4.0]\n"
        ">>> compute_moving_average([1, 2, 4], 2)\n"
        "[1.5, 3.0]\n"
        ">>> compute_moving_average([5.0], 1)\n"
        "[5.0]"
    ),
))
