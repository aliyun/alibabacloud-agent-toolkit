#!/usr/bin/env python3
"""LLM token usage recorder (library, not CLI).

Reads the agent client's transcript file incrementally (byte-offset cached
in SessionState), parses LLM-call usage, and returns normalized rows.
Caller decides how to embed the rows into trace JSONL.

Each returned row also carries `tool_use_ids` so the caller can attribute
tokens to the specific tool span(s) that the LLM call produced.

Python 3.10 compatible: stdlib only.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Iterable, Optional

# Cap how much new transcript we'll process in one Stop pass.
MAX_NEW_BYTES_PER_CALL = 64 * 1024 * 1024  # 64 MB


def _int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    now_ms = int(time.time() * 1000)
    t = time.gmtime(now_ms / 1000.0)
    millis = int(now_ms % 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", t) + f".{millis:03d}Z"


def _iter_jsonl(content: bytes) -> Iterable[dict]:
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            yield obj


def _read_transcript_slice(path: str, offset: int) -> tuple[bytes, int]:
    """Read transcript bytes from `offset` to EOF (capped). Restart at 0
    if the file shrank (rotation / truncation)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return b"", offset
    if size < offset:
        offset = 0
    if size == offset:
        return b"", offset
    end = min(size, offset + MAX_NEW_BYTES_PER_CALL)
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            content = f.read(end - offset)
    except OSError:
        return b"", offset
    # Trim to last full line: if the writer is mid-line at EOF, or the
    # MAX_NEW_BYTES_PER_CALL cap split a line, we'd otherwise advance the
    # offset past a partial JSON line and silently drop it on the next pass.
    last_nl = content.rfind(b"\n")
    if last_nl < 0:
        # No newline in slice (single huge unterminated line) - retry next pass.
        return b"", offset
    if last_nl + 1 < len(content):
        content = content[:last_nl + 1]
    return content, offset + len(content)


def _extract_claude_tool_use_ids(message: dict) -> list[str]:
    ids: list[str] = []
    content = message.get("content")
    if not isinstance(content, list):
        return ids
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            bid = block.get("id")
            if isinstance(bid, str) and bid:
                ids.append(bid)
    return ids


def _scrub_usage_claude(usage: dict) -> dict:
    keep = {
        "input_tokens", "cache_creation_input_tokens",
        "cache_read_input_tokens", "output_tokens", "cache_creation",
    }
    return {k: v for k, v in usage.items() if k in keep}


# Normalized token contract used by stop_handler:
#   input_uncached + input_cached + input_creation = total prompt input.
# Claude usage fields: input_tokens excludes cache_read/cache_creation.
# Codex usage fields: input_tokens includes cached_input_tokens, so subtract cached
# before assigning input_uncached. Keep this client-specific difference here only.
def _parse_claude(
    content: bytes,
    start_call_index: int,
    fallback_turn_id: str,
    prev_state: dict,
) -> tuple[list[dict], dict]:
    """Each `type:"assistant"` JSONL with a `usage` block is one LLM call,
    deduped by `message.id` (Claude splits one response across rows that
    share the id and repeat the usage block)."""
    last_msg_id = prev_state.get("last_msg_id") or ""
    rows: list[dict] = []
    call_idx = start_call_index
    for obj in _iter_jsonl(content):
        if obj.get("type") != "assistant":
            continue
        msg = obj.get("message") or {}
        usage = msg.get("usage") or {}
        if not usage:
            continue
        msg_id = msg.get("id") or ""
        if msg_id and msg_id == last_msg_id:
            continue
        last_msg_id = msg_id or last_msg_id
        call_idx += 1
        rows.append({
            # Claude transcript writes the wall-clock timestamp on each
            # assistant entry; falling back to _now_iso() would cluster every
            # call at the stop_handler invocation moment, breaking turn-order.
            "ts": obj.get("timestamp") or _now_iso(),
            "client": "claude-code",
            "session_id": obj.get("sessionId") or "",
            "turn_id": fallback_turn_id,
            "call_index": call_idx,
            "model": msg.get("model") or "",
            "tool_use_ids": _extract_claude_tool_use_ids(msg),
            "normalized": {
                "input_uncached": _int(usage.get("input_tokens")),
                "input_cached": _int(usage.get("cache_read_input_tokens")),
                "input_creation": _int(usage.get("cache_creation_input_tokens")),
                "output": _int(usage.get("output_tokens")),
                "reasoning": None,
            },
            "raw_usage": _scrub_usage_claude(usage),
        })
    return rows, {"last_msg_id": last_msg_id}


def _parse_codex(
    content: bytes,
    start_call_index: int,
    fallback_turn_id: str,
    prev_state: dict,
) -> tuple[list[dict], dict]:
    """Codex uses event_msg envelopes:
       - payload.type=token_count -> info.last_token_usage is the per-call usage
       - payload.type=function_call -> payload.call_id maps to tool_use_id
       We track recently-seen function_call call_ids and attribute them to
       the next token_count.
    """
    rows: list[dict] = []
    call_idx = start_call_index
    current_turn_id = prev_state.get("turn_id") or fallback_turn_id
    current_model = prev_state.get("model") or ""
    current_session = prev_state.get("session_id") or ""
    pending_call_ids: list[str] = list(prev_state.get("pending_call_ids") or [])

    for obj in _iter_jsonl(content):
        top_type = obj.get("type")
        if top_type == "session_meta":
            current_session = (obj.get("payload") or {}).get("id") or current_session
            continue
        if top_type == "turn_context":
            mdl = (obj.get("payload") or {}).get("model")
            if mdl:
                current_model = mdl
            continue
        # Codex 0.132+ writes function_call under response_item (not event_msg).
        # Capture call_id here so tokens reported in the next token_count get
        # attributed to the right tool span.
        if top_type == "response_item":
            payload = obj.get("payload") or {}
            if payload.get("type") == "function_call":
                cid = payload.get("call_id")
                if isinstance(cid, str) and cid:
                    pending_call_ids.append(cid)
            continue
        if top_type != "event_msg":
            continue
        payload = obj.get("payload") or {}
        ptype = payload.get("type")

        if ptype == "task_started":
            tid = payload.get("turn_id")
            if tid:
                current_turn_id = tid
            pending_call_ids = []
            continue

        if ptype == "function_call":
            cid = payload.get("call_id")
            if isinstance(cid, str) and cid:
                pending_call_ids.append(cid)
            continue

        if ptype != "token_count":
            continue
        info = payload.get("info") or {}
        last = info.get("last_token_usage") or {}
        if not last:
            continue
        input_total = _int(last.get("input_tokens")) or 0
        cached = _int(last.get("cached_input_tokens")) or 0
        # Codex: input_tokens INCLUDES cached_input_tokens
        input_uncached = max(input_total - cached, 0)
        call_idx += 1
        rows.append({
            "ts": obj.get("timestamp") or _now_iso(),
            "client": "codex",
            "session_id": current_session,
            "turn_id": current_turn_id,
            "call_index": call_idx,
            "model": current_model,
            "tool_use_ids": list(pending_call_ids),
            "normalized": {
                "input_uncached": input_uncached,
                "input_cached": cached,
                "input_creation": None,
                "output": _int(last.get("output_tokens")),
                "reasoning": _int(last.get("reasoning_output_tokens")),
            },
            "raw_usage": {
                "input_tokens": last.get("input_tokens"),
                "cached_input_tokens": last.get("cached_input_tokens"),
                "output_tokens": last.get("output_tokens"),
                "reasoning_output_tokens": last.get("reasoning_output_tokens"),
                "total_tokens": last.get("total_tokens"),
            },
        })
        pending_call_ids = []
    return rows, {
        "turn_id": current_turn_id,
        "model": current_model,
        "session_id": current_session,
        "pending_call_ids": pending_call_ids,
    }


def _parse_qoderwork(
    content: bytes,
    start_call_index: int,
    fallback_turn_id: str,
    prev_state: dict,
) -> tuple[list[dict], dict]:
    """QoderWork transcript schema matches Claude's: each `type:"assistant"`
    JSONL carries `message.usage` with `input_tokens`,
    `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`.

    Delegate to `_parse_claude` and rewrite the client label. QoderWork
    0.1.59-qw writes placeholder zeros for every assistant message; we
    still emit the llm_call rows so the viewer shows call timing, count
    and model — token chips just read 0 until QoderWork starts populating
    real usage numbers (no code change needed then).
    """
    rows, new_state = _parse_claude(
        content, start_call_index, fallback_turn_id, prev_state,
    )
    for row in rows:
        row["client"] = "qoderwork"
    return rows, new_state


def _parse_unknown(
    content: bytes,
    start_call_index: int,
    fallback_turn_id: str,
    prev_state: dict,
) -> tuple[list[dict], dict]:
    del content, start_call_index, fallback_turn_id, prev_state
    return [], {}


PARSERS = {
    "claude-code": _parse_claude,
    "codex": _parse_codex,
    "qoderwork": _parse_qoderwork,
}


def process_stop(
    client: str,
    transcript_path: str,
    offset: int,
    call_index: int,
    parser_state: dict,
    fallback_turn_id: str,
) -> tuple[list[dict], int, int, dict]:
    """Read new transcript bytes; return (rows, new_offset, new_call_index,
    new_parser_state). On any error returns ([], offset, call_index,
    parser_state) so caller can no-op safely.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return [], offset, call_index, parser_state
    parser = PARSERS.get(client, _parse_unknown)
    content, new_offset = _read_transcript_slice(transcript_path, offset)
    if not content:
        return [], new_offset, call_index, parser_state
    rows, new_parser_state = parser(
        content, call_index, fallback_turn_id,
        parser_state if isinstance(parser_state, dict) else {},
    )
    new_call_index = call_index + len(rows)
    return rows, new_offset, new_call_index, new_parser_state
