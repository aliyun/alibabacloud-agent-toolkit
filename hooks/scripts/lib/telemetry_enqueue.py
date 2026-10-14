#!/usr/bin/env python3
"""Queue a telemetry event for bounded background upload.

Reads --key/value lines from stdin (output of post/prompt/stop handlers)
and writes them as a JSON file to the per-client queue directory.
Optionally starts the bounded worker in the background.

Usage:
    echo -e "--event-type\\nmcp_tool_use\\n--tool-name\\nFoo" | \\
        python3 telemetry_enqueue.py <cdir> [--no-worker]
"""

import json
import os
import subprocess
import sys
import time
import uuid


def enqueue_event(cdir, args_dict, start_worker=True):
    """Write a single event to the queue directory and optionally start worker."""
    queue_dir = os.path.join(cdir, "telemetry-queue", "pending")
    os.makedirs(queue_dir, mode=0o700, exist_ok=True)

    event = {
        "args": args_dict,
        "retries": 0,
        "timestamp": time.time(),
    }

    filename = f"{int(time.time() * 1000000)}-{uuid.uuid4().hex[:8]}.json"
    filepath = os.path.join(queue_dir, filename)

    tmp = filepath + ".tmp"
    with open(tmp, "w") as f:
        json.dump(event, f)
    os.rename(tmp, filepath)

    if start_worker:
        _ensure_worker(cdir)


def _ensure_worker(cdir):
    """Start the bounded worker in the background if not already running."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    worker = os.path.join(script_dir, "telemetry_worker.py")

    env = os.environ.copy()
    env["ALIBABACLOUD_TELEMETRY_WORKER_STATE_DIR"] = cdir
    if os.environ.get("ALIBABACLOUD_TELEMETRY_DEBUG") == "1":
        env["ALIBABACLOUD_TELEMETRY_WORKER_DEBUG"] = "1"

    try:
        subprocess.Popen(
            [sys.executable, worker, cdir],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
            close_fds=True,
        )
    except Exception:
        pass


def _parse_lines_to_dict(text):
    """Parse alternating --key / value lines into a flat dict."""
    lines = [l for l in text.splitlines() if l]
    args_dict = {}
    i = 0
    while i < len(lines):
        if lines[i].startswith("--") and i + 1 < len(lines):
            key = lines[i][2:]
            args_dict[key] = lines[i + 1]
            i += 2
        else:
            i += 1
    return args_dict


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    cdir = sys.argv[1]
    no_worker = "--no-worker" in sys.argv

    text = sys.stdin.read()
    if not text.strip():
        return

    args_dict = _parse_lines_to_dict(text)
    if not args_dict:
        return

    enqueue_event(cdir, args_dict, start_worker=not no_worker)


if __name__ == "__main__":
    main()
