#!/usr/bin/env python3
"""Bounded telemetry upload worker daemon.

Replaces the old fire-and-forget ``uvx ... @latest`` pattern that created
unlimited orphan processes and exhausted disk via UV cache duplication.

The daemon is single-instance (fcntl lock), drains a file-based queue,
enforces concurrency and hard-timeout limits, pins the upload tool to a
fixed version, and cleans up all children on exit.

Hook scripts enqueue events by writing a JSON file to the queue directory
and calling this module's ``enqueue_and_start()`` helper.
"""

import atexit
import errno
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

_LOG = logging.getLogger("telemetry-worker")

# ── Configuration (override via env) ────────────────────────────────
_VERSION_DEFAULT = "0.1.21"
_MAX_CONCURRENT_DEFAULT = 3
_HARD_TIMEOUT_DEFAULT = 120
_IDLE_TIMEOUT_DEFAULT = 600
_POLL_INTERVAL_DEFAULT = 1.0
_QUEUE_MAX_DEFAULT = 10000


def _cfg_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _state_dir() -> str:
    base = os.environ.get(
        "ALIBABACLOUD_TELEMETRY_STATE_DIR",
        os.path.expanduser(
            "~/.cache/alibabacloud-agent-toolkit/telemetry"
        ),
    )
    try:
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, ".probe")
        open(probe, "w").close()
        os.unlink(probe)
    except OSError:
        uid = os.getuid() if hasattr(os, "getuid") else 0
        base = f"/tmp/alibabacloud-agent-toolkit-telemetry-{uid}"
        os.makedirs(base, exist_ok=True)
    return base


def _client_name() -> str:
    if os.environ.get("COPILOT_CLI") == "1":
        return "copilot-cli"
    if os.environ.get("CODEX_CLI") == "1":
        return "codex"
    if os.environ.get("QODER_WORK") == "1":
        return "qoderwork"
    return "claude-code"


# ── Upload logic ────────────────────────────────────────────────────

def _uploader_cmd() -> list:
    override = os.environ.get("ALIBABACLOUD_TELEMETRY_UPLOADER")
    if override:
        return override.split()
    version = os.environ.get(
        "ALIBABACLOUD_TELEMETRY_PROXY_VERSION", _VERSION_DEFAULT
    )
    return ["uvx", f"alibabacloud.mcp-proxy=={version}", "plugin-telemetry"]


def _run_upload(args: list, timeout: int, cdir: str) -> None:
    debug = os.environ.get("ALIBABACLOUD_TELEMETRY_DEBUG") == "1"
    try:
        kwargs = dict(
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if debug else subprocess.DEVNULL,
            stderr=subprocess.PIPE if debug else subprocess.DEVNULL,
        )
        proc = subprocess.Popen(args, **kwargs)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
            rc = -1
            _LOG.warning("upload killed after %ds timeout", timeout)

        if debug and cdir:
            log_path = os.path.join(cdir, "debug.log")
            try:
                with open(log_path, "a") as f:
                    f.write(
                        f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
                        f"[worker] upload-done rc={rc}\n"
                    )
                    if rc != 0 and stdout:
                        f.write(f"  stdout: {stdout.decode(errors='replace')[:2048]}\n")
                    if rc != 0 and stderr:
                        f.write(f"  stderr: {stderr.decode(errors='replace')[:2048]}\n")
            except OSError:
                pass
    except FileNotFoundError:
        _LOG.error("uvx not found — upload skipped")
    except Exception:
        _LOG.exception("upload failed")


# ── Queue I/O ───────────────────────────────────────────────────────

def _read_queue_file(path: str):
    try:
        with open(path) as f:
            data = json.load(f)
        os.unlink(path)
        if isinstance(data, dict) and "args" in data:
            return data
    except (json.JSONDecodeError, OSError):
        try:
            os.unlink(path)
        except OSError:
            pass
    return None


def _drain_queue(queue_dir: str, max_items: int) -> list:
    items = []
    try:
        entries = sorted(os.listdir(queue_dir))
    except OSError:
        return items
    for name in entries:
        if len(items) >= max_items:
            break
        if not name.endswith(".json"):
            continue
        item = _read_queue_file(os.path.join(queue_dir, name))
        if item:
            items.append(item)
    return items


# ── Worker loop ─────────────────────────────────────────────────────

_shutdown = threading.Event()


def _handle_signal(signum, _frame):
    _shutdown.set()


def _daemon_main() -> int:
    state_dir = _state_dir()
    safe_client = "".join(
        c if c.isalnum() or c in "_-" else "_" for c in _client_name()
    )[:64]
    cdir = os.path.join(state_dir, safe_client)
    os.makedirs(cdir, exist_ok=True)

    queue_dir = os.path.join(cdir, "upload-queue")
    os.makedirs(queue_dir, exist_ok=True)

    lock_path = os.path.join(cdir, "worker.lock")
    pid_path = os.path.join(cdir, "worker.pid")
    log_path = os.path.join(cdir, "debug.log")

    try:
        lock_fd = open(lock_path, "w")
    except OSError:
        return 1

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        lock_fd.close()
        return 1

    lock_fd.write(f"{os.getpid()}\n")
    lock_fd.flush()

    try:
        with open(pid_path, "w") as f:
            f.write(f"{os.getpid()}\n")
    except OSError:
        pass

    def _cleanup():
        try:
            os.unlink(pid_path)
        except OSError:
            pass
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass

    atexit.register(_cleanup)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    debug = os.environ.get("ALIBABACLOUD_TELEMETRY_DEBUG") == "1"
    if debug:
        try:
            with open(log_path, "a") as f:
                f.write(
                    f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
                    f"[worker] daemon started pid={os.getpid()}\n"
                )
        except OSError:
            pass

    max_concurrent = _cfg_int(
        "ALIBABACLOUD_TELEMETRY_MAX_CONCURRENT", _MAX_CONCURRENT_DEFAULT
    )
    hard_timeout = _cfg_int(
        "ALIBABACLOUD_TELEMETRY_HARD_TIMEOUT", _HARD_TIMEOUT_DEFAULT
    )
    idle_timeout = _cfg_int(
        "ALIBABACLOUD_TELEMETRY_IDLE_TIMEOUT", _IDLE_TIMEOUT_DEFAULT
    )
    poll_interval = float(
        os.environ.get("ALIBABACLOUD_TELEMETRY_POLL_INTERVAL", str(_POLL_INTERVAL_DEFAULT))
    )
    queue_max = _cfg_int(
        "ALIBABACLOUD_TELEMETRY_QUEUE_MAX", _QUEUE_MAX_DEFAULT
    )

    work_queue: "list[dict]" = []
    threads: "list[threading.Thread]" = []
    last_active = time.monotonic()

    while not _shutdown.is_set():
        threads = [t for t in threads if t.is_alive()]

        batch = _drain_queue(queue_dir, queue_max)
        if batch:
            work_queue.extend(batch)
            last_active = time.monotonic()

        if work_queue and len(threads) < max_concurrent:
            slots = min(max_concurrent - len(threads), len(work_queue))
            for _ in range(slots):
                item = work_queue.pop(0)
                args = item["args"]
                item_timeout = min(
                    item.get("timeout", hard_timeout), hard_timeout
                )
                cmd = list(_uploader_cmd()) + args
                t = threading.Thread(
                    target=_run_upload,
                    args=(cmd, item_timeout, cdir),
                    daemon=True,
                )
                t.start()
                threads.append(t)

        if not work_queue and not threads:
            if time.monotonic() - last_active > idle_timeout:
                if debug:
                    try:
                        with open(log_path, "a") as f:
                            f.write(
                                f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
                                f"[worker] idle timeout, exiting\n"
                            )
                    except OSError:
                        pass
                break

        _shutdown.wait(poll_interval)

    for t in threads:
        t.join(timeout=hard_timeout + 5)

    _cleanup()
    return 0


# ── Enqueue helper (used by hook scripts) ───────────────────────────

def enqueue_and_start(args: list, timeout: int = 120) -> None:
    """Write one event to the queue directory and ensure the daemon is
    running.  Safe to call from any shell/Python context.
    """
    state_dir = _state_dir()
    safe_client = "".join(
        c if c.isalnum() or c in "_-" else "_" for c in _client_name()
    )[:64]
    cdir = os.path.join(state_dir, safe_client)
    queue_dir = os.path.join(cdir, "upload-queue")
    os.makedirs(queue_dir, exist_ok=True)

    item = {"args": args, "timeout": timeout, "ts": time.time()}
    fd, path = tempfile.mkstemp(
        suffix=".json", prefix="evt-", dir=queue_dir
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(item, f)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        return

    _ensure_daemon(cdir)


def _ensure_daemon(cdir: str) -> None:
    pid_path = os.path.join(cdir, "worker.pid")
    alive = False
    try:
        with open(pid_path) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        alive = True
    except (OSError, ValueError):
        pass

    if alive:
        return

    try:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception:
        pass


# ── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.exit(_daemon_main())
