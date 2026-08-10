#!/usr/bin/env python3
"""Local audit trace writer.

Appends JSONL records to per-session trace files for user self-audit.
Default ON — set ALIBABACLOUD_TRACE=false to disable.
Never uploaded. Trace files older than 90 days are auto-cleaned on stop.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import client_dir  # noqa: E402

TRACE_MAX_BYTES = 65536  # 64KB response cap
TRACE_TTL_DAYS = 90  # auto-cleanup traces older than 3 months

# --- Light sanitization patterns (local data, minimal masking) ---

_TRACE_SANITIZE_PATTERNS = [
    # Alibaba Cloud AccessKey IDs (use lookaround instead of \b for CJK compatibility)
    (re.compile(r"(?<![A-Za-z0-9])LTAI[A-Za-z0-9]{8,30}(?![A-Za-z0-9])"), "***"),
    # STS tokens
    (re.compile(r"(?<![A-Za-z0-9])STS\.[A-Za-z0-9+/=]{10,}"), "***"),
    # JWT tokens
    (re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "***"),
    # PEM private key blocks
    (re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----[\s\S]*?-----END[^-]*PRIVATE KEY-----"), "***"),
    # key=value credential patterns
    (re.compile(r"(?i)\b(accesskeysecret|accesskey_secret|secret_access_key)\s*[=:]\s*\S+"), r"\1=***"),
    # CN mobile
    (re.compile(r"\b1[3-9]\d{9}\b"), "***"),
    # Email
    (re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "***"),
]


def trace_enabled() -> bool:
    """Return True unless ALIBABACLOUD_TRACE is explicitly 'false'."""
    return os.environ.get("ALIBABACLOUD_TRACE", "").lower() != "false"


def trace_dir(client: str) -> str:
    """Return trace directory path, creating it if needed.

    Priority: ALIBABACLOUD_TRACE_DIR env > <client_dir>/traces/
    """
    override = os.environ.get("ALIBABACLOUD_TRACE_DIR", "").strip()
    if override:
        try:
            os.makedirs(override, mode=0o700, exist_ok=True)
            return override
        except OSError:
            return ""
    cd = client_dir(client)
    if not cd:
        return ""
    traces = os.path.join(cd, "traces")
    try:
        os.makedirs(traces, mode=0o700, exist_ok=True)
        return traces
    except OSError:
        return ""


def _iso_from_ms(ms: int) -> str:
    """Convert epoch milliseconds to ISO 8601 string with ms precision."""
    secs = ms / 1000.0
    t = time.gmtime(secs)
    millis = int(ms % 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", t) + f".{millis:03d}Z"


def sanitize_trace_value(value: Any) -> Any:
    """Recursively sanitize strings in dicts/lists. Light patterns only."""
    if isinstance(value, str):
        s = value
        for pat, repl in _TRACE_SANITIZE_PATTERNS:
            s = pat.sub(repl, s)
        return s
    if isinstance(value, dict):
        return {k: sanitize_trace_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_trace_value(item) for item in value]
    return value


def truncate_response(obj: Any, max_bytes: int = TRACE_MAX_BYTES) -> Tuple[Any, bool]:
    """Serialize obj to JSON; if > max_bytes, truncate and return marker.

    Returns (obj_or_truncated_string, was_truncated).
    """
    if obj is None:
        return None, False
    try:
        serialized = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        serialized = str(obj)
    if len(serialized.encode("utf-8")) <= max_bytes:
        return obj, False
    # Truncate: return raw string capped at max_bytes
    truncated = serialized.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    return truncated, True


def append_trace(client: str, session_id: str, record: dict) -> None:
    """Append one JSONL record to the session trace file.

    Uses O_APPEND for atomic writes. Best-effort — never raises.
    """
    td = trace_dir(client)
    if not td:
        return
    # Safe filename
    safe_session = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")[:120]
    filepath = os.path.join(td, f"{safe_session}.jsonl")

    # Fill timestamps if not provided
    now_ms = int(time.time() * 1000)
    if "start_timestamp" not in record:
        record["start_timestamp"] = _iso_from_ms(now_ms)
    elif isinstance(record["start_timestamp"], int):
        record["start_timestamp"] = _iso_from_ms(record["start_timestamp"])
    if "end_timestamp" not in record:
        record["end_timestamp"] = record["start_timestamp"]
    elif isinstance(record["end_timestamp"], int):
        record["end_timestamp"] = _iso_from_ms(record["end_timestamp"])

    # Fill common fields
    record.setdefault("session_id", session_id)
    record.setdefault("client", client)

    try:
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        fd = os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def cleanup_stale_traces(max_age_days: int = TRACE_TTL_DAYS) -> int:
    """Remove JSONL trace files older than max_age_days across all clients.

    Scans:
      1. $ALIBABACLOUD_TELEMETRY_STATE_DIR
      2. ~/.cache/alibabacloud-agent-toolkit/telemetry/
      3. /tmp/alibabacloud-agent-toolkit-telemetry-<uid>/

    Returns total number of files removed. Best-effort, never raises.
    """
    from state import STATE_DIR_DEFAULT

    dirs_to_scan: list[str] = []
    override = os.environ.get("ALIBABACLOUD_TELEMETRY_STATE_DIR", "").strip()
    if override and os.path.isdir(override):
        dirs_to_scan.append(override)
    if os.path.isdir(STATE_DIR_DEFAULT):
        dirs_to_scan.append(STATE_DIR_DEFAULT)
    try:
        uid = os.getuid() if hasattr(os, "getuid") else "0"
    except Exception:
        uid = "0"
    tmp_dir = f"/tmp/alibabacloud-agent-toolkit-telemetry-{uid}"
    if os.path.isdir(tmp_dir):
        dirs_to_scan.append(tmp_dir)

    cutoff = time.time() - (max_age_days * 86400)
    removed = 0

    for base in dirs_to_scan:
        try:
            for client_entry in os.listdir(base):
                traces_path = os.path.join(base, client_entry, "traces")
                if not os.path.isdir(traces_path):
                    continue
                for fname in os.listdir(traces_path):
                    if not fname.endswith(".jsonl"):
                        continue
                    fpath = os.path.join(traces_path, fname)
                    try:
                        if os.path.getmtime(fpath) < cutoff:
                            os.unlink(fpath)
                            removed += 1
                    except OSError:
                        continue
        except OSError:
            continue

    return removed
