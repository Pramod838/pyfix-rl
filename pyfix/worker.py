"""
pyfix/worker.py — Minimal stdlib HTTP server for the worker container.

Security model:
  - This server NEVER executes submitted code in-process.
  - Each POST /run spawns a fresh child process (pyfix/runner.py) with
    per-process resource limits (CPU time, virtual memory).
  - The child process runs in a new session (setsid) so the entire process
    group can be killed on timeout — orphaned grandchildren are terminated.
  - The worker container has NO /app/hidden mount.
  - If mandatory resource limits cannot be applied, the request is rejected
    rather than silently continuing without the protection.

Documented limitations:
  - Without OS-level sandboxing (nsjail/seccomp), submitted code can still
    read files from the worker's accessible filesystem, make network calls
    inside the worker's network namespace, and import any installed package.
  - The security boundary is the Docker two-container isolation (no hidden/
    mount in the worker container), not the in-process resource limits.

Usage:
  python -m pyfix.worker          (via docker-compose worker service)
  WORKER_PORT=5001 python -m pyfix.worker
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[worker] %(message)s")
log = logging.getLogger(__name__)

# Path to the runner script (sibling of this file)
RUNNER = str(Path(__file__).parent / "runner.py")

# Execution limits
TIMEOUT = 5.0            # wall-clock seconds per test-case execution
MAX_REQUEST_BYTES = 128 * 1024   # 128 KB maximum request body
MAX_OUTPUT_BYTES  = 64  * 1024   # 64 KB maximum stdout/stderr

# Whether to reject requests when resource limits cannot be applied.
# Set PYFIX_STRICT_LIMITS=0 to disable (useful for platforms without full resource support).
STRICT_LIMITS = os.environ.get("PYFIX_STRICT_LIMITS", "1") != "0"


def _set_child_limits() -> None:
    """
    Resource limits applied inside each child process (Unix only).

    If STRICT_LIMITS is True and a limit fails to apply, raise RuntimeError
    so the worker can return a controlled failure instead of silently running
    without the protection.
    """
    errors = []
    try:
        import resource
        # 5 CPU-seconds hard limit
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    except Exception as exc:
        errors.append(f"RLIMIT_CPU: {exc}")

    try:
        import resource
        # 256 MB virtual address space
        resource.setrlimit(resource.RLIMIT_AS, (256 << 20, 256 << 20))
    except Exception as exc:
        errors.append(f"RLIMIT_AS: {exc}")

    if errors and STRICT_LIMITS:
        raise RuntimeError(f"Cannot apply resource limits: {'; '.join(errors)}")
    elif errors:
        # Non-strict: log but continue
        for e in errors:
            print(f"[runner-warning] Resource limit not applied: {e}", file=sys.stderr)


def _kill_process_group(pid: int) -> None:
    """
    Kill the entire process group of a child process.
    This ensures any grandchildren spawned by submitted code are also terminated.
    Only used on Unix; silently skipped on other platforms.
    """
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGKILL)
    except Exception:
        pass


def _communicate_limited(
    proc: subprocess.Popen,
    max_bytes: int,
    timeout: float,
) -> tuple:
    """
    Stream stdout and stderr from proc with hard size limits.

    Unlike subprocess.communicate(), this function kills the process group as
    soon as either stream exceeds max_bytes — it does not buffer unbounded
    output into RAM first.

    Returns (stdout_str, stderr_str, kill_reason) where kill_reason is one of:
      None           — process finished normally within limits
      "TimeoutError" — wall-clock timeout exceeded
      "OutputTooLarge" — stdout or stderr exceeded max_bytes

    Uses two daemon reader threads (one per stream) and one watchdog thread.
    """
    stdout_buf: list = []
    stderr_buf: list = []
    stdout_size = [0]
    stderr_size = [0]
    kill_reason: list = [None]
    done = threading.Event()

    def _read(stream, buf: list, size_ref: list) -> None:
        try:
            while True:
                chunk = stream.read(1024)
                if not chunk:
                    break
                available = max_bytes - size_ref[0]
                if available <= 0:
                    # Already over limit — kill and stop reading
                    if kill_reason[0] is None:
                        kill_reason[0] = "OutputTooLarge"
                    _kill_process_group(proc.pid)
                    break
                if len(chunk) > available:
                    buf.append(chunk[:available])
                    size_ref[0] += available
                    if kill_reason[0] is None:
                        kill_reason[0] = "OutputTooLarge"
                    _kill_process_group(proc.pid)
                    break
                buf.append(chunk)
                size_ref[0] += len(chunk)
        except Exception:
            pass

    def _watchdog() -> None:
        if not done.wait(timeout=timeout):
            if kill_reason[0] is None:
                kill_reason[0] = "TimeoutError"
            _kill_process_group(proc.pid)

    t_out = threading.Thread(target=_read, args=(proc.stdout, stdout_buf, stdout_size), daemon=True)
    t_err = threading.Thread(target=_read, args=(proc.stderr, stderr_buf, stderr_size), daemon=True)
    t_wd  = threading.Thread(target=_watchdog, daemon=True)

    t_out.start()
    t_err.start()
    t_wd.start()

    # Wait for readers (slightly longer than timeout to let watchdog act first)
    t_out.join(timeout=timeout + 2.0)
    t_err.join(timeout=1.0)
    done.set()          # signal watchdog we're done reading
    proc.wait()         # reap the process

    stdout_str = "".join(stdout_buf)
    stderr_str = "".join(stderr_buf)
    return stdout_str, stderr_str, kill_reason[0]


class WorkerHandler(BaseHTTPRequestHandler):
    """Handle GET /health and POST /run."""

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # Suppress per-request access logs

    def _send_json(self, body: dict, status: int = 200) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json({"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            self.send_response(404)
            self.end_headers()
            return

        # Validate Content-Length — return 200 JSON for all errors (consistent protocol)
        raw_length = self.headers.get("Content-Length")
        if not raw_length:
            self._send_json({"ok": False, "error": "MissingContentLength"})
            return
        try:
            length = int(raw_length)
        except ValueError:
            self._send_json({"ok": False, "error": "InvalidContentLength"})
            return

        # Enforce max request body size
        if length > MAX_REQUEST_BYTES:
            self._send_json({"ok": False, "error": "RequestTooLarge"})
            return

        # Parse JSON body
        try:
            raw_body = self.rfile.read(length)
            body = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json({"ok": False, "error": f"MalformedJSON: {exc}"})
            return

        # Validate required fields and types
        if not isinstance(body, dict):
            self._send_json({"ok": False, "error": "InvalidBody: must be object"})
            return

        code = body.get("code")
        fn   = body.get("fn")
        args_json = body.get("args_json", "[]")

        if not isinstance(code, str) or not code.strip():
            self._send_json({"ok": False, "error": "InvalidField: code must be non-empty string"})
            return
        if not isinstance(fn, str) or not fn.strip():
            self._send_json({"ok": False, "error": "InvalidField: fn must be non-empty string"})
            return
        if not isinstance(args_json, str):
            self._send_json({"ok": False, "error": "InvalidField: args_json must be string"})
            return

        # Validate args_json is parseable JSON array
        try:
            parsed_args = json.loads(args_json)
            if not isinstance(parsed_args, list):
                raise ValueError("args_json must be a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            self._send_json({"ok": False, "error": f"InvalidArgsJSON: {exc}"})
            return

        # Write submitted code to a UUID-named temp file
        tmp_path = f"/tmp/pyfix_{uuid.uuid4().hex}.py"
        proc = None
        try:
            with open(tmp_path, "w") as fh:
                fh.write(code)

            proc = subprocess.Popen(
                [sys.executable, RUNNER, tmp_path, fn, args_json],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                # start_new_session=True: child runs in a new process group,
                # so we can kill the entire group on timeout.
                start_new_session=True,
                preexec_fn=_set_child_limits,
            )

            stdout, stderr, kill_reason = _communicate_limited(proc, MAX_OUTPUT_BYTES, TIMEOUT)

            if kill_reason == "TimeoutError":
                self._send_json({"ok": False, "error": "TimeoutError: execution exceeded 5 seconds"})
                return
            if kill_reason == "OutputTooLarge":
                self._send_json({"ok": False, "error": "OutputTooLarge: stdout/stderr exceeded size limit"})
                return

            stdout_stripped = stdout.strip()
            if proc.returncode == 0 and stdout_stripped:
                try:
                    response = json.loads(stdout_stripped)
                    # Validate the runner returned the expected protocol shape
                    if "ok" not in response:
                        response = {"ok": False, "error": "RunnerProtocolError: missing 'ok' field"}
                except json.JSONDecodeError:
                    # Could not parse — submitted code might have printed to stdout
                    # despite the stdout-redirect fix; treat as error
                    response = {"ok": False, "error": "RunnerOutputError: non-JSON on stdout"}
            else:
                # Non-zero exit or empty stdout: use last stderr line as error message
                err_lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
                err = err_lines[-1][:200] if err_lines else "Non-zero exit (no stderr)"
                # Sanitise: never relay assert X == Y messages
                if "assert" in err.lower() and "==" in err:
                    err = "AssertionError in submitted code"
                response = {"ok": False, "error": err}

        except RuntimeError as exc:
            # Resource limit setup failed with STRICT_LIMITS enabled
            response = {"ok": False, "error": f"SecuritySetupError: {exc}"}
            if proc is not None and proc.returncode is None:
                _kill_process_group(proc.pid)
        except Exception as exc:
            response = {"ok": False, "error": f"WorkerInternalError: {type(exc).__name__}: {exc}"}
            if proc is not None and proc.returncode is None:
                _kill_process_group(proc.pid)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        self._send_json(response)


def main() -> None:
    port = int(os.environ.get("WORKER_PORT", 5001))
    server = HTTPServer(("0.0.0.0", port), WorkerHandler)
    log.info("Listening on :%d — submitted code runs in fresh child processes", port)
    log.info("STRICT_LIMITS=%s  TIMEOUT=%.1fs  MAX_REQUEST=%dKB",
             STRICT_LIMITS, TIMEOUT, MAX_REQUEST_BYTES // 1024)
    server.serve_forever()


if __name__ == "__main__":
    main()
