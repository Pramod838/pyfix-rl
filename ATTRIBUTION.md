# Attribution

## Source Project

**TheAlgorithms/Python**
Repository: https://github.com/TheAlgorithms/Python
Licence: MIT (https://github.com/TheAlgorithms/Python/blob/master/LICENSE)

The MIT Licence permits modification and redistribution with attribution.
Two task functions in this project are adapted from this repository.

---

## Task 1 — `reverse_words`

**Original file:** `strings/reverse_words.py`
**Verified commit:** `8fa4161587ab` (author: Tithi Joshi)
**GitHub URL:** https://github.com/TheAlgorithms/Python/blob/8fa4161587ab/strings/reverse_words.py

**Original function:**
```python
def reverse_words(sentence: str) -> str:
    return " ".join(sentence.split()[::-1])
```

**Adaptation:** No structural changes. One bug was introduced for RL training research:
`.split()` changed to `.split(" ")`.

---

## Task 2 — `is_valid_brackets`

**Original file:** `data_structures/stacks/balanced_parentheses.py`
**Verified commit:** `4a766c632cd6` (author: 1227haran)
**GitHub URL:** https://github.com/TheAlgorithms/Python/blob/4a766c632cd6/data_structures/stacks/balanced_parentheses.py

**Adaptations made:**
1. Custom `Stack` class (from `.stack` import) replaced with Python built-in `list`
   using `.append()` and `.pop()` — a standard simplification for standalone use.
2. Map direction changed from opening→closing to closing→opening (logically equivalent).
3. Function renamed from `balanced_parentheses` to `is_valid_brackets`.

**Two bugs introduced for RL training research:**
- Bug 1: Mismatch handling changed from "return False" to "silently ignore".
- Bug 2: Final return changed from `len(stack) == 0` to `True`.

---

## Task 3 — `compute_moving_average`

**Source:** Original function written for this project.
No external attribution.

---

## Task 4 — `matrix_multiply`

**Source:** Original function written for this project.
No external attribution. (No matrix multiplication function was found in
TheAlgorithms/Python after searching paths: `matrix_ops/`, `matrix/`, `maths/`,
`linear_algebra/`, `linear_algebra/src/`.)

---

## MIT Licence Text (TheAlgorithms/Python)

```
MIT License

Copyright (c) 2016-2024 TheAlgorithms and contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
