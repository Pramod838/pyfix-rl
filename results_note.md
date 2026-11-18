# pyfix-rl — Results Note

## Methodology

Each task was tested three times using the **manual/human agent** (agent/human_agent.py)
with predetermined fix sequences representing realistic debugging scenarios:

- **Run 1**: First attempt uses the original buggy code; second attempt applies the correct fix.
  Simulates an agent that identifies the bug after seeing the error feedback.
- **Run 2**: First attempt applies the correct fix.
  Simulates an agent that identifies all bugs immediately.
- **Run 3**: All three attempts submit the unchanged buggy code.
  Simulates an agent that cannot solve the task within the attempt limit.

**Agent**: Human agent (`--agent human`), predetermined code strings.
**Environment**: `CodeRepairEnv`, `max_attempts=3`.
**Worker**: pyfix worker at `http://localhost:5003`, `PYFIX_STRICT_LIMITS=0` (macOS local run).
**Grading**: Hidden test suites in `hidden/`, accessed by grader process only.
**Date of runs**: November 2026.

> **Note on Groq agent**: The Groq API (model `gemma2-9b-it`) was not available during
> this test run. Results below are from manual/human agent runs. See "Groq Agent" section
> for instructions on running LLM-based episodes.

---

## Agent Run Results

### Task 1 — `reverse_words` (Easy, 1 bug)

| Run | Attempts used | Final reward | Solved | First error (sanitised) |
|-----|:---:|:---:|:---:|:---|
| 1 (buggy→correct) | 2 | 1.00 | ✓ | `Wrong answer` |
| 2 (correct first) | 1 | 1.00 | ✓ | — |
| 3 (always buggy)  | 3 | 0.00 | ✗ | `Wrong answer` |

**pass@1**: 1/3 (33%) · **pass@3**: 2/3 (67%) · **avg attempts to solve**: 1.5

---

### Task 2 — `is_valid_brackets` (Medium, 2 bugs)

| Run | Attempts used | Final reward | Solved | First error (sanitised) |
|-----|:---:|:---:|:---:|:---|
| 1 (buggy→correct) | 2 | 1.00 | ✓ | `Wrong answer` |
| 2 (correct first) | 1 | 1.00 | ✓ | — |
| 3 (always buggy)  | 3 | 0.00 | ✗ | `Wrong answer` |

**pass@1**: 1/3 (33%) · **pass@3**: 2/3 (67%) · **avg attempts to solve**: 1.5

---

### Task 3 — `compute_moving_average` (Hard, 3 bugs)

| Run | Attempts used | Final reward | Solved | First error (sanitised) |
|-----|:---:|:---:|:---:|:---|
| 1 (buggy→correct) | 2 | 1.00 | ✓ | `Wrong output length` |
| 2 (correct first) | 1 | 1.00 | ✓ | — |
| 3 (always buggy)  | 3 | 0.00 | ✗ | `Wrong output length` |

**pass@1**: 1/3 (33%) · **pass@3**: 2/3 (67%) · **avg attempts to solve**: 1.5

---

### Task 4 — `matrix_multiply` (Stretch, partial credit)

Task 4 partial-credit was verified programmatically (see test suite):

| Fix applied | Reward | Category 1 (0.33) | Category 2 (0.33) | Category 3 (0.34) |
|-------------|:---:|:---:|:---:|:---:|
| None (buggy) | 0.00 | ✗ | ✗ | ✗ |
| Fix 1 only (inner product index) | 0.33 | ✓ | ✗ | ✗ |
| Fix 3 only (ValueError check) | 0.34 | ✗ | ✗ | ✓ |
| All 3 fixes (correct) | 1.00 | ✓ | ✓ | ✓ |

---

## Exploit Attempt Outcomes

Exploits were run against the live grader. Verdicts are from actual script output
(see `exploit_attempts/ANALYSIS.md` for full JSON output).

| # | Method | Outcome | Security layer |
|---|--------|:---:|:---|
| 1 | Hardcode visible test-case outputs; fall back to buggy implementation | ✓ Blocked | Hypothesis generates inputs not in the table |
| 2 | Overwrite `/app/hidden/suite_task1.py` via `pathlib.write_text()` | ✓ Blocked | `/app/hidden/` does not exist in worker container |
| 3 | Read `/app/hidden/suite_task1.py` via `pathlib.read_text()` | ✓ Blocked (Docker) | Same missing mount; also caught by grader loading suite before code runs |

---

## What These Runs Do NOT Prove

1. **Statistical significance**: 3 runs per task provides no reliable `pass@k` estimate.
   100+ runs per task would be required for statistical claims.
2. **Model generalisation**: Predetermined human fix sequences are not evidence of
   LLM reasoning ability. LLM results may differ significantly.
3. **That training improves a model**: These runs provide no pre/post comparison.
   Training improvement requires a controlled fine-tuning experiment.
4. **Robustness of security controls**: 3 exploit variants is not a comprehensive attack
   surface analysis. See `scope_note.md` for documented limitations.

---

## How to Measure Real Training Improvement

To rigorously evaluate whether training on pyfix-rl improves an LLM:

1. **Establish baselines**: Run the target model (via Groq agent or local) on all 3
   mandatory tasks, 100 episodes each. Record `pass@1`, `pass@3`, mean reward per task,
   and mean attempts to solve.

2. **Collect training data**: Run many episodes with varied agents (random, model-based)
   to collect `(obs, action, reward, next_obs)` tuples. Include both successes and failures.

3. **Fine-tune**: Apply PPO (online RL), DPO (preference fine-tuning on pass/fail pairs),
   or supervised fine-tuning on successful trajectories.

4. **Post-fine-tuning measurement**: Re-run 100 episodes per task with the fine-tuned model.
   Compute the same metrics.

5. **Statistical test**: Use McNemar's test on paired binary episode outcomes (task solved
   yes/no) to test whether improvement is statistically significant (p < 0.05).

6. **Held-out task set**: Evaluate on tasks not used in training to test generalisation.
   A model that improves only on training tasks (not held-out) has memorised, not learned.

---

## Running the Groq Agent

```bash
# Set up API key
cp .env.example .env
# Edit .env: add your GROQ_API_KEY (free at https://console.groq.com)

# Check available models
python3 -c "
import os; from groq import Groq
c = Groq(api_key=os.environ['GROQ_API_KEY'])
print([m.id for m in c.models.list().data])
"

# Run an episode
PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python run_episode.py --task 1 --agent groq
```

If `gemma2-9b-it` is unavailable, set `GROQ_MODEL=<available_model>` in `.env`.
