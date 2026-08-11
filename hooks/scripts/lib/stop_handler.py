#!/usr/bin/env python3
"""Stop / StopFailure hook handler.

Increments per-session turn counter. When the turn involved alibabacloud
tools (turn_has_trace flag), emits a `user_prompt_turn_start` event to
stdout for remote telemetry upload, and writes local trace events.

Exit codes:
    0 — event emitted to stdout (caller should upload)
    1 — no event emitted (nothing to upload)
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid as _uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import SessionState, cleanup_stale_sessions  # noqa: E402
import trace_writer  # noqa: E402
import token_recorder  # noqa: E402

EMPTY_TOKENS = {
    "input_uncached": 0, "input_cached": 0, "input_creation": 0,
    "output": 0, "reasoning": 0,
}


def _add_tokens(a: dict, b: dict) -> dict:
    out = dict(a)
    for k in EMPTY_TOKENS:
        av = out.get(k) or 0
        bv = b.get(k) or 0
        out[k] = av + bv
    return out


DEBUG = os.environ.get("ALIBABACLOUD_TELEMETRY_DEBUG") == "1"

_EMIT_ORDER = [
    "client-name", "event-type", "start-timestamp", "end-timestamp",
    "tool-name", "session-id", "status",
    "mcp-tool", "skill-name", "plugin-name", "tool-request-id",
    "cli-command", "event-tag", "error-message",
    "span-id", "parent-span-id",
    "skill-tag", "mcp-session-id",
    "input-uncached-tokens", "input-cached-tokens", "input-creation-tokens",
    "output-tokens", "reasoning-tokens",
]


def _detect_client(payload_str: str) -> str:
    if os.environ.get("COPILOT_CLI") == "1":
        return "copilot-cli"
    if os.environ.get("CODEX_CLI") == "1":
        return "codex"
    if os.environ.get("QODER_WORK") == "1":
        return "qoderwork"
    if "__vscode" in payload_str:
        return "vscode"
    if '"turn_id":' in payload_str:
        return "codex"
    return "claude-code"


def _iso_from_ms(ms: int) -> str:
    t = time.gmtime(ms / 1000.0)
    millis = int(ms % 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", t) + f".{millis:03d}Z"


def _uploader_cmd() -> list:
    """Resolve mcp-proxy invocation. Env var lets .sh override for dev."""
    override = os.environ.get("ALIBABACLOUD_TELEMETRY_UPLOADER")
    if override:
        return override.split()
    return ["uvx", "alibabacloud.mcp-proxy@latest", "plugin-telemetry"]


_MCP_SESSION_DIR = os.path.expanduser(
    "~/.cache/alibabacloud-agent-toolkit/mcp-sessions"
)
_AGENT_BINARIES = ("claude", "codex", "QoderWork")


def _find_agent_pid() -> "int | None":
    """Walk up the process tree to find the agent (claude/codex/QoderWork) PID."""
    import subprocess as _sp
    pid = os.getpid()
    for _ in range(10):
        try:
            ppid = int(_sp.check_output(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                text=True, stderr=_sp.DEVNULL,
            ).strip())
        except Exception:
            break
        if ppid <= 1:
            break
        try:
            comm = _sp.check_output(
                ["ps", "-o", "comm=", "-p", str(ppid)],
                text=True, stderr=_sp.DEVNULL,
            ).strip().rsplit("/", 1)[-1]
        except Exception:
            break
        if comm in _AGENT_BINARIES:
            return ppid
        pid = ppid
    return None


def _read_mcp_session_id() -> str:
    """Read mcpSessionId written by the MCP server, keyed by agent PID."""
    agent_pid = _find_agent_pid()
    if not agent_pid:
        return ""
    path = os.path.join(_MCP_SESSION_DIR, f"{agent_pid}.json")
    try:
        with open(path) as f:
            return json.load(f).get("mcpSessionId", "")
    except Exception:
        return ""


_OPTIN_FIELDS = frozenset({
    "cli-command", "error-message",
    "input-uncached-tokens", "input-cached-tokens", "input-creation-tokens",
    "output-tokens", "reasoning-tokens",
})
_OPTIN_FILE = os.path.expanduser("~/.config/alibabacloud/telemetry-optin")


def _strip_optin_fields(args: dict) -> None:
    """Remove opt-in fields when the user has not authorized collection."""
    if os.path.isfile(_OPTIN_FILE):
        return
    for k in _OPTIN_FIELDS:
        args.pop(k, None)


def _spawn_upload(args: dict) -> None:
    """Fire-and-forget mcp-proxy upload for per-call events. The primary
    user_prompt_turn_start event still flows via stdout to the .sh wrapper —
    this is only for the N extra llm_call events that don't fit the
    single-event stdout protocol."""
    import subprocess
    argv = list(_uploader_cmd())
    for key in _EMIT_ORDER:
        v = args.get(key)
        if v is None or v == "":
            continue
        argv.append(f"--{key}")
        argv.append(str(v))
    log_path = os.environ.get("ALIBABACLOUD_TELEMETRY_UPLOAD_LOG")
    if log_path:
        try:
            out_fd = open(log_path, "ab")
        except Exception:
            out_fd = subprocess.DEVNULL
    else:
        out_fd = subprocess.DEVNULL
    try:
        subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=out_fd,
            stderr=out_fd,
            start_new_session=True,
        )
    except Exception:
        pass


def _emit(args: dict) -> None:
    for key in _EMIT_ORDER:
        v = args.get(key)
        if v is None or v == "":
            continue
        print(f"--{key}")
        print(v)


def _debug(msg: str) -> None:
    if DEBUG:
        try:
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def main() -> int:
    if os.environ.get("ALIBABACLOUD_TELEMETRY") == "false":
        _debug("[stop] decision=skip reason=opted-out")
        return 1
    raw = sys.stdin.buffer.read(65536)
    if not raw:
        _debug("[stop] decision=skip reason=empty-stdin")
        return 1
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
    except Exception:
        data = {}
    session_id = data.get("session_id") or ""
    if not session_id:
        _debug("[stop] decision=skip reason=no-session-id")
        return 1
    client = _detect_client(text)
    hook_event_name = data.get("hook_event_name") or "Stop"

    new_turn = 0
    should_emit = False
    emit_args: dict = {}
    try:
        with SessionState(client, session_id) as st:
            turn_has_trace = st.data.get("turn_has_trace", False)
            prompt_span = st.data.get("prompt_span_id") or ""
            pending_prompt_ts = st.data.get("pending_prompt_ts")
            current_turn = int(st.data.get("turn", 0))
            stop_ts = int(time.time() * 1000)

            # --- Token recorder: read transcript slice (always advance offset) ---
            transcript_path = data.get("transcript_path") or ""
            tokens_offset = int(st.data.get("tokens_offset", 0))
            tokens_call_index = int(st.data.get("tokens_call_index", 0))
            tokens_parser_state = st.data.get("tokens_parser_state") or {}
            fallback_turn_id = f"stop-{current_turn}"
            token_rows: list[dict] = []
            new_offset = tokens_offset
            new_call_index = tokens_call_index
            new_parser_state = tokens_parser_state
            try:
                token_rows, new_offset, new_call_index, new_parser_state = (
                    token_recorder.process_stop(
                        client, transcript_path, tokens_offset,
                        tokens_call_index, tokens_parser_state,
                        fallback_turn_id,
                    )
                )
            except Exception:
                token_rows = []

            # Always advance offsets, even when this turn is not traced —
            # otherwise the next traced turn would re-attribute these tokens.
            st.data["tokens_offset"] = new_offset
            st.data["tokens_call_index"] = new_call_index
            if isinstance(new_parser_state, dict):
                st.data["tokens_parser_state"] = new_parser_state

            # --- Token aggregation: always compute (consumed by both
            # local trace below and the remote user_prompt_turn_start emit) ---
            # Map tool_use_id → span_id for tool token attribution. The
            # viewer reconstructs the parent chain itself, so no parent_map
            # or skill_set is needed here.
            turn_spans = st.data.get("turn_spans") or []
            tool_use_to_span = {
                s["tool_use_id"]: s["span_id"]
                for s in turn_spans
                if s.get("tool_use_id")
            }
            # Layer 1 (strict): turn totals + per-call list. The viewer
            # reconstructs Layer 2 (skill-attributed estimates) by walking
            # each call's tool spans — see
            # telemetry_view/data.py::compute_token_layers.
            turn_tokens = dict(EMPTY_TOKENS)
            llm_calls: list = []
            for row in token_rows:
                n = row.get("normalized") or {}
                turn_tokens = _add_tokens(turn_tokens, n)
                tool_use_ids = list(row.get("tool_use_ids") or [])
                tool_span_ids = [
                    tool_use_to_span.get(tu_id) or tu_id
                    for tu_id in tool_use_ids
                ]
                call_ts = row.get("ts") or _iso_from_ms(stop_ts)
                llm_calls.append({
                    "span_id": _uuid.uuid4().hex[:16],
                    "call_index": row.get("call_index"),
                    "model": row.get("model"),
                    "ts": call_ts,
                    "tool_use_ids": tool_use_ids,
                    "tool_span_ids": tool_span_ids,
                    "llm_tokens": dict(n),
                })

            # --- Local trace: backfill prompt, write llm_call + turn_end ---
            if trace_writer.trace_enabled() and turn_has_trace:
                pending = st.data.get("pending_prompt")
                if pending:
                    trace_writer.append_trace(client, session_id, {
                        "event": "prompt",
                        "span_id": prompt_span,
                        "parent_span_id": None,
                        "prompt": trace_writer.sanitize_trace_value(pending),
                        "turn": current_turn,
                        "start_timestamp": pending_prompt_ts,
                        "end_timestamp": stop_ts,
                    })

                # First-class llm_call events in the timeline. Sit at turn
                # level (parent = prompt_span), siblings with tool_call
                # events, ordered by start_timestamp. The turn_end.llm_calls
                # side-table below is preserved for backward-compat with
                # viewers that read it directly.
                for call in llm_calls:
                    trace_writer.append_trace(client, session_id, {
                        "event": "llm_call",
                        "span_id": call["span_id"],
                        "parent_span_id": prompt_span,
                        "turn": current_turn,
                        "start_timestamp": call["ts"],
                        "end_timestamp": call["ts"],
                        "call_index": call["call_index"],
                        "model": call["model"],
                        "tool_use_ids": call["tool_use_ids"],
                        "tool_span_ids": call["tool_span_ids"],
                        "llm_tokens": call["llm_tokens"],
                    })

                # Update cumulative session total (only counts traced turns)
                session_total = st.data.get("aliyun_session_tokens") or dict(EMPTY_TOKENS)
                session_total = _add_tokens(session_total, turn_tokens)
                st.data["aliyun_session_tokens"] = session_total

                # tool_tokens kept as empty dict for backward compatibility:
                # old viewers fall through their legacy path and render no
                # chips rather than crashing or showing duplicated numbers.
                trace_writer.append_trace(client, session_id, {
                    "event": "turn_end",
                    "span_id": _uuid.uuid4().hex[:16],
                    "parent_span_id": prompt_span,
                    "stop_reason": hook_event_name,
                    "turn": current_turn,
                    "start_timestamp": stop_ts,
                    "end_timestamp": stop_ts,
                    "turn_tokens": turn_tokens,
                    "aliyun_session_tokens": session_total,
                    "llm_calls": llm_calls,
                    "tool_tokens": {},
                })

            # --- Remote telemetry: per-LLM-call uploads (fire-and-forget) ---
            # These bypass the single-event stdout protocol because the .sh
            # wrapper only fires one mcp-proxy invocation per hook trigger.
            # Each call gets its own background uvx process; ordering in SLS
            # is by start_timestamp (no callIndex needed, no model uploaded).
            if turn_has_trace and prompt_span and llm_calls:
                for call in llm_calls:
                    upload_args = {
                        "client-name": client,
                        "event-type": "llm_call",
                        "start-timestamp": call["ts"],
                        "end-timestamp": call["ts"],
                        "tool-name": f"{current_turn}:llm_call",
                        "session-id": session_id,
                        "status": "success",
                        "event-tag": "llm_call",
                        "span-id": call["span_id"],
                        "parent-span-id": prompt_span,
                        "mcp-session-id": _read_mcp_session_id(),
                        "input-uncached-tokens": str(call["llm_tokens"].get("input_uncached") or 0),
                        "input-cached-tokens":   str(call["llm_tokens"].get("input_cached")   or 0),
                        "input-creation-tokens": str(call["llm_tokens"].get("input_creation") or 0),
                        "output-tokens":         str(call["llm_tokens"].get("output")         or 0),
                        "reasoning-tokens":      str(call["llm_tokens"].get("reasoning")      or 0),
                    }
                    _strip_optin_fields(upload_args)
                    _spawn_upload(upload_args)

            # --- Remote telemetry: emit user_prompt_turn_start ---
            if turn_has_trace and prompt_span:
                start_ts = pending_prompt_ts or stop_ts
                emit_args = {
                    "client-name": client,
                    "event-type": "user_prompt_turn_start",
                    "start-timestamp": _iso_from_ms(start_ts),
                    "end-timestamp": _iso_from_ms(stop_ts),
                    "tool-name": f"{current_turn}:user_prompt",
                    "session-id": session_id,
                    "status": "success",
                    "event-tag": "user_prompt_turn_start",
                    "span-id": prompt_span,
                    "mcp-session-id": _read_mcp_session_id(),
                    "input-uncached-tokens": str(turn_tokens.get("input_uncached") or 0),
                    "input-cached-tokens": str(turn_tokens.get("input_cached") or 0),
                    "input-creation-tokens": str(turn_tokens.get("input_creation") or 0),
                    "output-tokens": str(turn_tokens.get("output") or 0),
                    "reasoning-tokens": str(turn_tokens.get("reasoning") or 0),
                }
                _strip_optin_fields(emit_args)
                should_emit = True

            # Reset trace state for next turn
            if trace_writer.trace_enabled() or turn_has_trace:
                st.data.pop("turn_has_trace", None)
                st.data.pop("pending_prompt", None)
                st.data.pop("pending_prompt_ts", None)
                st.data.pop("prompt_span_id", None)
                st.data["turn_spans"] = []
                # Clear post-tool-use dedup set — claude double-fires are
                # always within the same turn, so this keeps memory bounded
                # without losing any dedup signal.
                st.data["posted_tool_use_ids"] = []
                # Same for pre-tool-use dedup set (claude fires PreToolUse
                # twice per tool_use_id within one turn).
                st.data["pre_seen_ids"] = []

            # Increment turn (existing behavior)
            st.data["turn"] = int(st.data.get("turn", 0)) + 1
            new_turn = st.data["turn"]
    except Exception:
        pass

    if should_emit:
        _emit(emit_args)
        _debug(
            f"[stop] turn={new_turn} session={session_id} client={client} "
            f"decision=upload event=user_prompt_turn_start"
        )
        # Opportunistic cleanup (cheap)
        try:
            cleanup_stale_sessions(client)
            trace_writer.cleanup_stale_traces()
        except Exception:
            pass
        return 0

    _debug(f"[stop] turn={new_turn} session={session_id} client={client} decision=no-emit")
    try:
        cleanup_stale_sessions(client)
        trace_writer.cleanup_stale_traces()
    except Exception:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
