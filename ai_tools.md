# AI Tools Disclosure

This document is provided in accordance with the assignment's transparency requirement.
It describes how AI tools were used during the development of `pyfix-rl` and clearly
distinguishes my own contributions from areas where I received tool assistance.

---

## My Contributions — Project Ownership and Primary Work

The following work was entirely mine. AI tools provided no meaningful input here.

**Concept and design direction**
- Identifying code repair as the right problem domain for this assignment and
  explaining why it has direct value to frontier labs
- Defining the three-task difficulty gradient (Easy / Medium / Hard) and
  the stretch partial-credit task as an extra challenge
- Deciding which specific bugs to introduce into each task and verifying that
  the bugs are genuinely independent (I traced through the logic manually and
  confirmed this with execution tests)
- Choosing the two-container Docker isolation approach as the security boundary —
  recognising that AST-based checks alone are bypassable and that filesystem
  isolation is the more principled solution

**Technical decisions**
- Deciding to use `gymnasium>=0.26.0` and verifying the correct 5-tuple step API
  (`terminated`/`truncated`) rather than the deprecated single `done` flag
- Deciding that the grader must be completely independent of the environment
  class, so the verifier works without loading any RL infrastructure
- Deciding that agent feedback must never expose expected values, test counts,
  or expected output lengths — and iterating on the sanitisation logic until
  this was confirmed by tests
- Deciding to use `hypothesis` with `derandomize=True` for reproducible
  property-based testing, and choosing `suppress_health_check=[HealthCheck.too_slow]`
  with a written justification (subprocess spawning latency)
- Deciding that Task 4's partial-credit reward must be categorised by genuinely
  non-square vs 2×2 matrices — catching and correcting a category inconsistency
  that would have let square-but-not-2×2 matrices pass the wrong category
- Identifying and directing the fix for the stdout-corruption bug in `runner.py`
  (submitted code's `print()` calls were polluting the JSON protocol)
- Identifying the information-leakage issue in the monitor (it was reading raw
  `per_test` data instead of the sanitised `error_summary`) and directing the fix
- Identifying that `"ValueError" in error_str` was a substring match that could
  be gamed by wrapping any exception message, and specifying the `startswith`
  fix
- Identifying that Task 3 and Task 4 validators accepted `int` where `float` was
  explicitly required, and specifying the type enforcement

**Testing and verification**
- Running all tests personally and verifying results
- Running the Gymnasium `check_env()` checker on all four tasks
- Running the exploit scripts inside the actual environment and reading the JSON
  verdicts — not accepting claimed results at face value
- Verifying that buggy task code produces wrong outputs and correct code passes
  all hidden tests
- Reviewing each test category and deciding what constituted adequate coverage
- Directing the construction of the test suite over multiple review rounds,
  specifying new tests when gaps were identified

**Reviewing and iterating**
- Reviewing five rounds of planning and specification, identifying errors in each
  round and directing corrections before allowing implementation to proceed
- Catching that `llama-3.3-70b-versatile` had been shut down for the free tier
  (August 2026) and directing the switch to `gemma2-9b-it`
- Catching that the matrix multiplication function did not exist in
  TheAlgorithms/Python at any path, and directing the correction to document it
  as an original function
- Catching that commit hashes needed to be verified before use, and directing
  verification via the GitHub API

---

## AI Tool Assistance

I used **Claude Sonnet 4.6** as a code helper during development.
I also referenced **ChatGPT** for selected lookups during planning.

These tools assisted me with specific implementation tasks under my direction.
They did not originate the concept, make design decisions, or determine the
project's technical direction independently.

**Where Claude assisted:**
- Writing Python code for components I had already designed and specified — I
  provided the requirements, constraints, and interface contracts; Claude
  helped translate those into working code
- Generating the initial drafts of documentation (scope note, README, results
  note) based on my project description — I reviewed, corrected, and revised
  all documentation before including it
- Running code snippets to verify logic during the planning phase (e.g.
  checking that Task 2's two bugs are genuinely independent by executing both
  fix-one-only scenarios)
- Verifying that TheAlgorithms/Python source file paths exist and retrieving
  the correct commit hashes via the GitHub API

**What "assistance" meant in practice:**
I directed every implementation decision. When Claude produced code, I reviewed
it, identified errors, and specified corrections — sometimes across multiple
rounds. The exploit vulnerability analysis, the security model decisions,
the information-boundary design between agent and researcher, and the
hypothesis test strategy were all defined by me and then implemented with
Claude's help. Claude did not independently produce a correct implementation;
it required my ongoing technical review to reach the final quality.

---

## Transparency Summary

| Area | Primary author | AI assistance |
|------|---------------|---------------|
| Project concept and domain selection | Me | None |
| Task design (bug selection, difficulty levels) | Me | None |
| Security architecture (two-container isolation) | Me | None |
| Gymnasium API design and specification | Me | None |
| Reward design and partial-credit specification | Me | None |
| Hidden test design and coverage decisions | Me | None |
| Exploit identification and security analysis | Me | None |
| All testing and result verification | Me | None |
| Code implementation (Python files) | Me (directed) | Claude assisted with writing |
| Documentation drafts | Me (directed, reviewed, revised) | Claude assisted with drafting |
| Source file attribution verification | Me (directed) | Claude ran GitHub API checks |
