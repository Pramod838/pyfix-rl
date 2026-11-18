# pyfix-rl

A minimal, production-quality Python **Code-Repair RL Environment** for training and
evaluating AI coding assistants. Submitted as the take-home assignment for the
**Adzzad Labs — Lead RL Environment Engineer** role.

The agent observes a buggy Python function, submits a corrected version, and receives
a binary reward from an independent judge. Up to three attempts per episode; sanitised
error feedback between attempts.

---

## What Was Built

- **Gymnasium-compatible environment** with correct 0.26+ API (`terminated`/`truncated`)
- **Four code-repair tasks** at three difficulty levels (Easy / Medium / Hard / Stretch)
- **Independent grader** that separates trusted grading from untrusted code execution
- **Two-container Docker isolation**: submitted code has no access to hidden test files
- **Automated test suite** covering grader, worker, environment, integration, security, and monitoring
- **Live execution monitor** with agent-visible vs. researcher-only separation
- **Three exploit demonstrations** with real execution verdicts
- Groq free-tier agent and human/manual agent

---

## Architecture

```
Agent → CodeRepairEnv → grade_submission()
                              │
                        GRADER container   ← has ./hidden:ro mounted
                        (expected values)
                              │  POST {code, fn, input}  ← no expected value
                              ▼
                        WORKER container   ← NO hidden/ mount
                        (fresh subprocess per test)
                              │  actual output via HTTP
                              ▼
                        Grader compares actual vs expected
                        Returns AgentFeedback(passed, error_summary)
                        Writes full log to logs/
```

**Security boundary**: `/app/hidden/` is not mounted in the worker container.
Submitted code genuinely cannot read hidden test files. This is filesystem isolation,
not a permissions check.

---

## The Four Tasks

| ID | Function | Difficulty | Bugs | Reward | Tests |
|----|----------|------------|------|--------|-------|
| 1 | `reverse_words` | Easy | 1 | Binary (0 / 1) | 28 |
| 2 | `is_valid_brackets` | Medium | 2 (independent) | Binary | 52 |
| 3 | `compute_moving_average` | Hard | 3 (interacting) + invalid-window | Binary | 32 |
| 4 | `matrix_multiply` | Stretch | 3 (per category) | Partial 0–1 | 50 |

Task 4 reward = 0.33 × (2×2 correct) + 0.33 × (non-square correct) + 0.34 × (ValueError raised).

---

## Setup

### Requirements

- Python 3.11+ with pip
- Docker and Docker Compose (for full isolation)
- A free Groq API key (https://console.groq.com) — optional, only needed for LLM agent

### Install (local development)

```bash
git clone <this-repo>
cd pyfix-rl
pip3 install -e .
pip3 install -r requirements.txt
```

### Environment variables

```bash
cp .env.example .env
# Edit .env:
#   GROQ_API_KEY=your_key_here    (optional — only for Groq agent)
#   GROQ_MODEL=gemma2-9b-it       (default; change if model unavailable)
#   PYFIX_WORKER_URL=http://worker:5001   (Docker) or http://localhost:5001 (local)
#   PYFIX_HIDDEN_DIR=/app/hidden  (Docker) or ./hidden (local)
```

---

## Running the Environment

### Option A: Docker (recommended — full isolation)

> **Verification status**: Docker commands were not executed in a live Docker
> environment during this assignment run (Docker unavailable in test environment).
> Commands below are correct based on the `Dockerfile` and `docker-compose.yml`
> configuration. Run `docker compose config` to validate the configuration locally.

```bash
# Build and start both containers
docker compose up --build -d

# Wait for worker health check to pass
docker compose ps

# One command to run a full episode (human agent)
docker compose run --rm grader python3 run_episode.py --task 1 --agent human

# One command to run with Groq LLM agent
docker compose run --rm grader python3 run_episode.py --task 1 --agent groq

# One command to grade a submitted fix file
docker compose run --rm grader python3 grade.py --task 1 --file fix.py
```

### Option B: Local (development, without Docker)

```bash
# Terminal 1: Start the worker server
WORKER_PORT=5001 PYFIX_STRICT_LIMITS=0 python3 -m pyfix.worker

# Terminal 2: Run a full episode
PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 run_episode.py --task 1 --agent human

# Grade a file
PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 grade.py --task 1 --file fix.py
```

### Human/manual agent

The human agent reads the task description and buggy code, then accepts a code fix from stdin.
No API key required. Valid per assignment instructions.

```bash
PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 run_episode.py --task 1 --agent human
# Paste your fix and type END on a blank line to submit
```

### Groq LLM agent

```bash
# Verify available models first
python3 -c "
import os; from groq import Groq
c = Groq(api_key=os.environ['GROQ_API_KEY'])
print([m.id for m in c.models.list().data])
"
# If gemma2-9b-it is listed, you're ready. Otherwise set GROQ_MODEL in .env.

PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 run_episode.py --task 1 --agent groq
```

---

## Automated Tests

```bash
# Run the full test suite (requires worker on port 5001)
PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 -m pytest tests/ -v

# Run only unit tests (no worker required)
python3 -m pytest tests/test_grader_unit.py -v

# Run Gymnasium environment checker
PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 tests/test_env_checker.py
```

**Test categories:**

| File | Coverage |
|------|----------|
| `test_grader_unit.py` | `is_obviously_broken`, `_values_equal`, `_summarise_error` |
| `test_tasks.py` | Correct/buggy/partial fixes, int-vs-float rejection, ValueError exact match |
| `test_env.py` | Reset/step/termination/truncation/guard behaviour |
| `test_worker.py` | HTTP requests, timeouts, validation, output limits, security |
| `test_integration.py` | Full episode flow, feedback leakage, logging |
| `test_security.py` | Exploit prevention, type checks, sanitisation |
| `test_monitor.py` | Monitor information separation (normal vs research mode) |
| `test_env_checker.py` | Gymnasium official checker on all 4 tasks |

---

## Exploit Demonstrations

```bash
# Start worker first
python3 -m pyfix.worker &

# Run all three exploits (self-documenting; print JSON verdicts)
PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 exploit_attempts/exploit_01_hardcode.py

PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 exploit_attempts/exploit_02_overwrite.py

PYFIX_WORKER_URL=http://localhost:5001 PYFIX_HIDDEN_DIR=./hidden \
  python3 exploit_attempts/exploit_03_read_hidden.py
```

See `exploit_attempts/ANALYSIS.md` for full verdicts.

---

## Monitoring

```bash
# View all existing grading logs (agent-visible info only)
python3 monitor.py

# Include researcher-only details (test counts, error specifics)
python3 monitor.py --research

# Live-tail mode (poll every second for new events)
python3 monitor.py --follow

# Filter to a specific task
python3 monitor.py --task 3 --research
```

---

## Viewing Logs

Grading logs are written to `logs/` as JSON files. Each file contains:

```json
{
  "task_id": 1,
  "reward": 0.0,
  "passed": false,
  "error_summary": "Wrong answer",
  "tests_passed": 17,
  "tests_total": 28,
  "per_test": [...],
  "timestamp": "2026-11-18T16:00:00Z"
}
```

`error_summary` is the sanitised agent-visible error. `tests_passed`, `tests_total`,
and `per_test` are researcher-only. They are never sent to the agent.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `WorkerUnavailable` error | Start the worker: `python3 -m pyfix.worker` |
| `Hidden suite not found` | Set `PYFIX_HIDDEN_DIR=./hidden` |
| `Address already in use` | Another worker is running. Use a different port: `WORKER_PORT=5002 python3 -m pyfix.worker` |
| `OSError: [Errno 1]` with resource limits | Set `PYFIX_STRICT_LIMITS=0` for local macOS development |
| Groq model unavailable | Run the model-list command and set `GROQ_MODEL` in `.env` |
| `task_id not in registry` | Import `tasks` package before using the env |
| `python: command not found` | Use `python3` (macOS) or `python` (inside Docker container) |

---

## Project Structure

```
pyfix-rl/
├── README.md           scope_note.md   results_note.md
├── ATTRIBUTION.md      ai_tools.md
├── Dockerfile          docker-compose.yml   .dockerignore
├── requirements.txt    setup.py         .env.example
├── run_episode.py      grade.py         monitor.py
│
├── pyfix/              # RL environment package
│   ├── env.py          # CodeRepairEnv(gymnasium.Env)
│   ├── tasks.py        # Task dataclass + registry
│   ├── worker.py       # HTTP server (worker container)
│   └── runner.py       # child-process entrypoint
│
├── tasks/              # task definitions (shown to agent)
│   ├── task1..4.py
│
├── grader/             # independent verifier
│   ├── grade.py        # GradeResult + orchestrator
│   └── anti_gaming.py  # AST heuristics (efficiency only)
│
├── hidden/             # ro-mounted; grader reads, worker never sees
│   ├── suite_task1..4.py
│
├── agent/
│   ├── groq_agent.py   human_agent.py
│
├── tests/              # automated test suite
│   ├── conftest.py     test_grader_unit.py  test_tasks.py
│   ├── test_env.py     test_worker.py       test_integration.py
│   ├── test_security.py test_monitor.py     test_env_checker.py
│
└── exploit_attempts/
    ├── exploit_01_hardcode.py   exploit_02_overwrite.py
    ├── exploit_03_read_hidden.py  ANALYSIS.md
```

---

## Python Version

Python **3.11**. `hypothesis==6.112.2`, `gymnasium>=0.26.0`.
On macOS for local testing, Python 3.9+ also works with `PYFIX_STRICT_LIMITS=0`.
