#!/usr/bin/env python3
"""Shared state primitives for telemetry hooks.

Provides per-session JSON state with fcntl exclusive locks, atomic writes,
client + uid-bucketed paths, and cleanup of stale sessions.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Optional

STATE_DIR_DEFAULT = os.path.expanduser(
    "~/.cache/alibabacloud-agent-toolkit/telemetry"
)
LOCK_TIMEOUT_S = 2.0
SESSION_TTL_DAYS = 7


def _chmod_dir(p: str) -> None:
    """Best-effort chmod 0700 on a directory."""
    try:
        os.chmod(p, 0o700)
    except OSError:
        pass


def state_root() -> str:
    """Resolve the base state dir, falling back to /tmp/<...>-<uid> on error."""
    p = os.environ.get("ALIBABACLOUD_TELEMETRY_STATE_DIR") or STATE_DIR_DEFAULT
    try:
        os.makedirs(p, mode=0o700, exist_ok=True)
        _chmod_dir(p)
        # Probe writability
        with open(os.path.join(p, ".probe"), "w") as f:
            f.write("")
        os.unlink(os.path.join(p, ".probe"))
        return p
    except OSError:
        try:
            uid = os.getuid() if hasattr(os, "getuid") else "0"
        except Exception:
            uid = "0"
        fallback = f"/tmp/alibabacloud-agent-toolkit-telemetry-{uid}"
        try:
            os.makedirs(fallback, mode=0o700, exist_ok=True)
            _chmod_dir(fallback)
            return fallback
        except OSError:
            return ""


def client_dir(client: str) -> str:
    """Return <state-dir>/<client>/, creating it if possible."""
    base = state_root()
    if not base:
        return ""
    safe_client = re.sub(r"[^A-Za-z0-9_-]", "_", client or "unknown")[:64]
    p = os.path.join(base, safe_client)
    sessions_dir = os.path.join(p, "sessions")
    try:
        os.makedirs(sessions_dir, mode=0o700, exist_ok=True)
        _chmod_dir(p)
        _chmod_dir(sessions_dir)
        return p
    except OSError:
        return ""


def safe_session_filename(session_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return cleaned[:120] or "unknown"


def debug_log_path(client: str) -> str:
    cd = client_dir(client)
    return os.path.join(cd, "debug.log") if cd else ""


def _try_flock_exclusive(fh, timeout_s: float = LOCK_TIMEOUT_S) -> bool:
    """Best-effort exclusive lock with timeout. Returns True if acquired."""
    try:
        import fcntl  # POSIX only
    except ImportError:
        return False
    deadline = time.time() + timeout_s
    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.time() > deadline:
                return False
            time.sleep(0.05)
        except OSError:
            return False


def _try_funlock(fh) -> None:
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


class SessionState:
    """Context manager for per-session state with fcntl lock + atomic write.

    Usage:
        with SessionState(client, session_id) as st:
            st.data["turn"] = st.data.get("turn", 0) + 1
        # On exit, state is atomically written and lock released.

    On any error (no fcntl available, lock timeout, write failure), proceeds
    best-effort. Telemetry must never crash the agent.
    """

    def __init__(self, client: str, session_id: str):
        self.client = client
        self.session_id = session_id
        self.cd = client_dir(client)
        if self.cd:
            safe = safe_session_filename(session_id)
            self.state_path = os.path.join(self.cd, "sessions", f"{safe}.state.json")
            self.lock_path = os.path.join(self.cd, "sessions", f"{safe}.lock")
        else:
            self.state_path = ""
            self.lock_path = ""
        self.data: dict = {}
        self._fh = None
        self._locked = False

    def __enter__(self) -> "SessionState":
        if not self.lock_path:
            return self
        try:
            self._fh = open(self.lock_path, "a+")
            self._locked = _try_flock_exclusive(self._fh)
        except OSError:
            self._fh = None
            self._locked = False
        # Load state (whether or not lock acquired — best effort)
        if self.state_path and os.path.exists(self.state_path):
            try:
                with open(self.state_path) as f:
                    self.data = json.load(f) or {}
            except (OSError, json.JSONDecodeError):
                self.data = {}
        if not isinstance(self.data, dict):
            self.data = {}
        # Initialize required keys
        self.data.setdefault("session_id", self.session_id)
        self.data.setdefault("turn", 0)
        self.data.setdefault("tool_starts", {})
        # Per-turn record: list of {"span_id": str, "parent_span_id": str|None,
        # "kind": "tool"|"skill_invocation", "tool_use_id": str}. Cleared at
        # turn_end. Lets post_handler retrieve the parent stamped at pre time.
        self.data.setdefault("turn_spans", [])
        # Token recorder state — incremental transcript parsing.
        self.data.setdefault("tokens_offset", 0)
        self.data.setdefault("tokens_call_index", 0)
        self.data.setdefault("tokens_parser_state", {})
        # Cumulative session token total (only counts traced turns).
        self.data.setdefault("aliyun_session_tokens", {
            "input_uncached": 0,
            "input_cached": 0,
            "input_creation": 0,
            "output": 0,
            "reasoning": 0,
        })
        return self

    def __exit__(self, *exc) -> None:
        if not self.state_path:
            return
        try:
            self.data["updated_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            tmp = self.state_path + ".tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(self.data, f)
            os.replace(tmp, self.state_path)
        except OSError:
            pass
        if self._fh is not None:
            if self._locked:
                _try_funlock(self._fh)
            try:
                self._fh.close()
            except OSError:
                pass


def cleanup_stale_sessions(client: str, max_age_days: int = SESSION_TTL_DAYS) -> int:
    """Remove session state/lock files older than max_age_days. Returns count removed."""
    cd = client_dir(client)
    if not cd:
        return 0
    sessions_dir = os.path.join(cd, "sessions")
    if not os.path.isdir(sessions_dir):
        return 0
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    try:
        for entry in os.listdir(sessions_dir):
            path = os.path.join(sessions_dir, entry)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.unlink(path)
                    removed += 1
            except OSError:
                continue
    except OSError:
        pass
    return removed


# CLI entry-point — allows dry-run.sh and tests to seed state without
# duplicating the marker computation.
def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    seed = sub.add_parser("seed-marker")
    seed.add_argument("--client", required=True)
    seed.add_argument("--session", required=True)
    seed.add_argument("--key", required=True, help="tool_use_id or tool_name fallback")
    seed.add_argument("--ms", required=True, type=int)

    cleanup = sub.add_parser("cleanup")
    cleanup.add_argument("--client", required=True)
    cleanup.add_argument("--max-age-days", type=int, default=SESSION_TTL_DAYS)

    show = sub.add_parser("show")
    show.add_argument("--client", required=True)
    show.add_argument("--session", required=True)

    args = parser.parse_args()
    if args.cmd == "seed-marker":
        with SessionState(args.client, args.session) as st:
            st.data["tool_starts"][args.key] = args.ms
        return 0
    if args.cmd == "cleanup":
        n = cleanup_stale_sessions(args.client, args.max_age_days)
        print(f"removed={n}")
        return 0
    if args.cmd == "show":
        cd = client_dir(args.client)
        if not cd:
            return 1
        safe = safe_session_filename(args.session)
        path = os.path.join(cd, "sessions", f"{safe}.state.json")
        if not os.path.exists(path):
            print("{}")
            return 0
        with open(path) as f:
            print(f.read())
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
