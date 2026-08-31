#!/usr/bin/env python3
"""Bounded telemetry upload worker.

Processes queued telemetry events with:
- Single-instance control via file lock (flock)
- Fixed virtualenv with pinned package (no per-event uvx resolution)
- Configurable concurrency limit (sequential batch processing)
- Hard timeout per upload with subprocess reaping
- Finite retry budget with dead-letter logging
- No orphan processes (proper session group cleanup)

Usage:
    python3 telemetry_worker.py <state-dir> [--cleanup-only]
"""

import fcntl
import json
import os
import signal
import subprocess
import sys
import time

MCP_PROXY_PACKAGE = "alibabacloud.mcp-proxy"
MCP_PROXY_PINNED_VERSION = "0.5.1"
MCP_PROXY_PIN = f"{MCP_PROXY_PACKAGE}=={MCP_PROXY_PINNED_VERSION}"

DEFAULT_MAX_CONCURRENT = int(os.environ.get(
    "ALIBABACLOUD_TELEMETRY_MAX_CONCURRENT", "4"
))
DEFAULT_HARD_TIMEOUT = int(os.environ.get(
    "ALIBABACLOUD_TELEMETRY_UPLOAD_TIMEOUT", "30"
))
DEFAULT_MAX_RETRIES = int(os.environ.get(
    "ALIBABACLOUD_TELEMETRY_MAX_RETRIES", "2"
))
MAX_QUEUE_SIZE = int(os.environ.get(
    "ALIBABACLOUD_TELEMETRY_MAX_QUEUE", "500"
))
FAILED_RETENTION_DAYS = 7
PENDING_STALE_HOURS = 24

_debug_log_path = None


def _log(msg):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if _debug_log_path:
        try:
            with open(_debug_log_path, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass


def _acquire_lock(state_dir):
    """Try to acquire exclusive lock. Returns (lock_fd, lock_path) or None."""
    os.makedirs(state_dir, exist_ok=True)
    lock_path = os.path.join(state_dir, "telemetry-worker.lock")
    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd, lock_path
    except (IOError, OSError):
        os.close(fd)
        return None


def _release_lock(lock_info):
    if lock_info is None:
        return
    fd, _ = lock_info
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        pass


def _is_pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _reap_pid(pid):
    """Reap a zombie child if it is ours."""
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


def _write_pid_file(state_dir):
    pid_path = os.path.join(state_dir, "telemetry-worker.pid")
    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))
    return pid_path


def _check_existing_worker(state_dir):
    """Return True if another worker is already running."""
    pid_path = os.path.join(state_dir, "telemetry-worker.pid")
    try:
        with open(pid_path) as f:
            pid = int(f.read().strip())
        if _is_pid_alive(pid) and pid != os.getpid():
            return True
    except (FileNotFoundError, ValueError, OSError):
        pass
    return False


def _remove_pid_file(pid_path):
    try:
        with open(pid_path) as f:
            if int(f.read().strip()) == os.getpid():
                os.unlink(pid_path)
    except (FileNotFoundError, ValueError, OSError):
        pass


def _get_upload_cmd(state_dir):
    """Return the upload command argv prefix using fixed venv or pinned uvx."""
    override = os.environ.get("ALIBABACLOUD_TELEMETRY_UPLOADER")
    if override:
        return override.split()

    venv_dir = os.path.join(state_dir, ".venv")
    venv_bin = os.path.join(venv_dir, "bin", "plugin-telemetry")

    if os.path.isfile(venv_bin):
        return [venv_bin]

    if _ensure_venv(state_dir):
        if os.path.isfile(venv_bin):
            return [venv_bin]

    return [
        "uvx", "--from",
        f"{MCP_PROXY_PACKAGE}=={MCP_PROXY_PINNED_VERSION}",
        "plugin-telemetry",
    ]


def _ensure_venv(state_dir):
    """Create or update the fixed virtualenv. Returns True on success."""
    venv_dir = os.path.join(state_dir, ".venv")
    marker = os.path.join(venv_dir, ".telemetry-version")

    if os.path.isfile(marker):
        try:
            with open(marker) as f:
                if f.read().strip() == MCP_PROXY_PIN:
                    return True
        except OSError:
            pass

    try:
        import venv as venv_mod
        _log(f"Creating venv at {venv_dir}")
        venv_mod.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    except Exception as e:
        _log(f"venv creation failed: {e}")
        return False

    pip_bin = os.path.join(venv_dir, "bin", "pip")
    try:
        result = subprocess.run(
            [pip_bin, "install", "--quiet", MCP_PROXY_PIN],
            timeout=120,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            _log(f"pip install failed: {result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        _log("pip install timed out after 120s")
        return False
    except Exception as e:
        _log(f"pip install error: {e}")
        return False

    try:
        with open(marker, "w") as f:
            f.write(MCP_PROXY_PIN)
    except OSError:
        pass

    _log(f"Installed {MCP_PROXY_PIN}")
    return True


def _upload_one(cmd_prefix, args_dict):
    """Run a single upload with hard timeout. Raises on failure."""
    argv = list(cmd_prefix)
    for key, value in args_dict.items():
        if value is not None and value != "":
            argv.append(f"--{key}")
            argv.append(str(value))

    timeout = DEFAULT_HARD_TIMEOUT

    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        if proc.returncode != 0:
            err_snippet = (stderr.decode("utf-8", errors="replace"))[:300]
            raise RuntimeError(
                f"upload exited {proc.returncode}: {err_snippet}"
            )
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        raise RuntimeError(f"upload timed out after {timeout}s")


def _kill_process_tree(proc):
    """Kill a subprocess and its entire process group. No orphans."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        try:
            proc.kill()
        except (ProcessLookupError, OSError):
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass

    _reap_pid(proc.pid)


def _list_pending(queue_dir):
    """List pending event files sorted by timestamp, capped at MAX_QUEUE_SIZE."""
    try:
        files = [
            f for f in os.listdir(queue_dir)
            if f.endswith(".json") and not f.endswith(".tmp")
        ]
    except FileNotFoundError:
        return []

    files.sort()
    if len(files) > MAX_QUEUE_SIZE:
        excess = files[MAX_QUEUE_SIZE:]
        for f in excess:
            try:
                os.unlink(os.path.join(queue_dir, f))
            except OSError:
                pass
        _log(f"Queue overflow: dropped {len(excess)} oldest events")
        files = files[:MAX_QUEUE_SIZE]
    return files


def _process_batch(state_dir):
    """Process one batch of pending events. Returns count processed."""
    queue_dir = os.path.join(state_dir, "telemetry-queue", "pending")
    failed_dir = os.path.join(state_dir, "telemetry-queue", "failed")
    os.makedirs(failed_dir, mode=0o700, exist_ok=True)

    files = _list_pending(queue_dir)
    if not files:
        return 0

    cmd_prefix = _get_upload_cmd(state_dir)
    processed = 0

    for filename in files:
        filepath = os.path.join(queue_dir, filename)
        try:
            with open(filepath) as f:
                event = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            _log(f"Removing corrupt event {filename}: {e}")
            _safe_unlink(filepath)
            continue

        args_dict = event.get("args", {})
        retries = event.get("retries", 0)
        event_type = args_dict.get("event-type", "unknown")

        try:
            _upload_one(cmd_prefix, args_dict)
            _safe_unlink(filepath)
            processed += 1
        except RuntimeError as e:
            _log(f"Upload failed for {event_type} ({filename}): {e}")
            if retries < DEFAULT_MAX_RETRIES:
                event["retries"] = retries + 1
                _write_back(filepath, event)
            else:
                _move_to_failed(filepath, failed_dir, event)
                _log(f"Moved to failed after {DEFAULT_MAX_RETRIES} retries: {filename}")
        except Exception as e:
            _log(f"Unexpected error processing {filename}: {e}")
            _move_to_failed(filepath, failed_dir, event)

    return processed


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _write_back(filepath, event):
    try:
        with open(filepath, "w") as f:
            json.dump(event, f)
    except OSError:
        pass


def _move_to_failed(filepath, failed_dir, event):
    try:
        os.makedirs(failed_dir, mode=0o700, exist_ok=True)
        dest = os.path.join(failed_dir, os.path.basename(filepath))
        with open(dest, "w") as f:
            json.dump(event, f)
        os.unlink(filepath)
    except OSError:
        _safe_unlink(filepath)


def _cleanup_old(state_dir):
    """Remove old failed uploads and stale pending events."""
    now = time.time()
    for subdir in ("failed", "pending"):
        d = os.path.join(state_dir, "telemetry-queue", subdir)
        if not os.path.isdir(d):
            continue
        max_age = (
            FAILED_RETENTION_DAYS * 86400
            if subdir == "failed"
            else PENDING_STALE_HOURS * 3600
        )
        try:
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                try:
                    if now - os.path.getmtime(fp) > max_age:
                        os.unlink(fp)
                except OSError:
                    pass
        except FileNotFoundError:
            pass


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <state-dir> [--cleanup-only]", file=sys.stderr)
        sys.exit(1)

    state_dir = sys.argv[1]
    cleanup_only = "--cleanup-only" in sys.argv

    global _debug_log_path
    if os.environ.get("ALIBABACLOUD_TELEMETRY_WORKER_DEBUG") == "1":
        _debug_log_path = os.path.join(state_dir, "worker-debug.log")

    if not os.path.isdir(state_dir):
        _log(f"State dir does not exist: {state_dir}")
        sys.exit(1)

    os.makedirs(
        os.path.join(state_dir, "telemetry-queue", "pending"),
        mode=0o700, exist_ok=True,
    )

    if _check_existing_worker(state_dir):
        return

    lock_info = _acquire_lock(state_dir)
    if lock_info is None:
        return

    pid_path = _write_pid_file(state_dir)
    try:
        if cleanup_only:
            _cleanup_old(state_dir)
            return

        iterations = 0
        while True:
            count = _process_batch(state_dir)
            iterations += 1
            if count == 0:
                break
            if iterations >= 1000:
                _log("Safety limit reached (1000 iterations), exiting")
                break
            _cleanup_old(state_dir)
    finally:
        _remove_pid_file(pid_path)
        _release_lock(lock_info)


if __name__ == "__main__":
    main()
