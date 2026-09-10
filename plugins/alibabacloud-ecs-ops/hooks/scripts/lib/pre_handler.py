#!/usr/bin/env python3
"""Pre-tool-use hook handler.

Reads hook payload from stdin (bounded to 64 KB), extracts tool_name and
session_id, writes a start-time marker into the per-session state file
(fcntl-locked, atomic). Silent on any error — never blocks the agent.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

# Make sibling modules importable when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import SessionState  # noqa: E402
import trace_writer  # noqa: E402

PLUGIN_PREFIX = "alibabacloud"
STDIN_CAP = 65536
QODERWORK_MCP_WRAPPERS = ("qw_mcp_call", "qw_mcp_get", "CallMcpTool")

# Aliyun CLI invocation: matches `aliyun ...` at start of command OR
# after a shell separator (`&&`, `||`, `;`, `|`, `\n`, `(`), with optional
# `ENV=val` prefixes and optional path prefix (e.g. `/usr/local/bin/aliyun`).
# Word-bounded (excludes `aliyun-cli`, `myaliyun`, `cat /var/log/aliyun.log`).
# Kept in sync with post_handler.ALIYUN_INVOCATION_RE.
ALIYUN_INVOCATION_RE = re.compile(
    r"(?:^|[;&|\n(])"
    r"\s*"
    r"(?:[A-Z][A-Z0-9_]*=\S+\s+)*"
    r"(?:[^\s;&|]*/)?"
    r"aliyun"
    r"(?=\s|$|[;&|])"
)


def normalize_tool_call(tool_name: str, tool_input):
    """Unwrap QoderWork MCP wrapper payloads into the inner MCP tool shape."""
    if tool_name not in QODERWORK_MCP_WRAPPERS or not isinstance(tool_input, dict):
        return tool_name, tool_input
    inner_name = tool_input.get("toolName") or tool_input.get("tool_name") or ""
    if not isinstance(inner_name, str) or not inner_name:
        return tool_name, tool_input
    inner_input = tool_input.get("arguments")
    if not isinstance(inner_input, dict):
        inner_input = {}
    return inner_name, inner_input


def read_stdin_bounded() -> bytes:
    return sys.stdin.buffer.read(STDIN_CAP)


def is_ours_tool(tool_name: str, tool_input) -> bool:
    """Return True when this tool call concerns one of our plugins."""
    if not tool_name:
        return False
    lower = tool_name.lower()
    if PLUGIN_PREFIX in lower:
        return True
    if tool_name in ("Skill", "skill"):
        skill = ""
        if isinstance(tool_input, dict):
            skill = tool_input.get("skill", "") or ""
        if isinstance(skill, str) and PLUGIN_PREFIX in skill.lower():
            return True
    if tool_name in ("Agent", "agent"):
        sub = ""
        if isinstance(tool_input, dict):
            sub = tool_input.get("subagent_type", "") or ""
        if isinstance(sub, str) and PLUGIN_PREFIX in sub.lower():
            return True
    if tool_name == "Bash":
        cmd = ""
        if isinstance(tool_input, dict):
            cmd = tool_input.get("command", "") or ""
        if isinstance(cmd, str):
            if ALIYUN_INVOCATION_RE.search(cmd):
                return True
            if re.search(r"/skills/[A-Za-z0-9_-]+/SKILL\.md\b", cmd) and PLUGIN_PREFIX in cmd.lower():
                return True
    return False


def _debug_enabled() -> bool:
    return os.environ.get("ALIBABACLOUD_TELEMETRY_DEBUG") == "1"


def _debug(msg: str) -> None:
    if _debug_enabled():
        try:
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def _detail(tool_name: str, tool_input) -> str:
    """Best-effort short tag describing what the tool is about (no PII)."""
    if not isinstance(tool_input, dict):
        return ""
    if tool_name in ("Skill", "skill"):
        v = tool_input.get("skill", "") or ""
        return f"skill={v}" if v else ""
    if tool_name in ("Agent", "agent"):
        v = tool_input.get("subagent_type", "") or ""
        return f"subagent={v}" if v else ""
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        if isinstance(cmd, str) and cmd.strip():
            head = cmd.strip().split()[0]
            head = re.sub(r"[^A-Za-z0-9._-]", "_", head)[:32]
            return f"cmd_head={head}"
    return ""


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


def _sanitize_tool_name(tool_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", tool_name or "")[:120]


def main() -> int:
    if os.environ.get("ALIBABACLOUD_TELEMETRY") == "false":
        _debug("[pre] decision=skip reason=opted-out")
        return 0
    raw = read_stdin_bounded()
    if not raw:
        _debug("[pre] decision=skip reason=empty-stdin")
        return 0
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
    except Exception:
        _debug("[pre] decision=skip reason=invalid-json")
        return 0
    tool_name = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}
    tool_name, tool_input = normalize_tool_call(tool_name, tool_input)
    session_id = data.get("session_id") or ""
    tool_use_id = data.get("tool_use_id") or ""
    if not is_ours_tool(tool_name, tool_input):
        _debug(
            f"[pre] tool={tool_name or '<none>'} decision=skip reason=not-ours"
        )
        return 0
    if not session_id:
        _debug(
            f"[pre] tool={tool_name} decision=skip reason=no-session-id"
        )
        return 0

    client = _detect_client(text)
    key = tool_use_id or _sanitize_tool_name(tool_name)
    parent_span = None
    turn = 0
    is_duplicate = False
    unique_span_key = tool_use_id or key
    try:
        with SessionState(client, session_id) as st:
            st.data["tool_starts"][key] = int(time.time() * 1000)
            # --- Local trace: mark turn active, get parent span ---
            if trace_writer.trace_enabled():
                st.data["turn_has_trace"] = True
                # Dedup: Claude fires PreToolUse twice for the same
                # tool_use_id within one turn (symmetric with the
                # PostToolUse dedup via posted_tool_use_ids). Skip the
                # second fire so we neither write a duplicate tool_start
                # event nor a duplicate turn_spans entry.
                # When tool_use_id is present, it uniquely identifies a
                # call so repeated fires of the same ID are true duplicates.
                # When tool_use_id is absent (e.g. qoderwork), each fire is
                # a distinct call — use a monotonic seq to avoid false dedup.
                if tool_use_id:
                    dedup_key = tool_use_id
                else:
                    _seq = st.data.get("_pre_seq", 0) + 1
                    st.data["_pre_seq"] = _seq
                    dedup_key = f"{tool_name}:{_seq}"
                    unique_span_key = dedup_key
                pre_seen = st.data.setdefault("pre_seen_ids", [])
                if dedup_key in pre_seen:
                    is_duplicate = True
                else:
                    pre_seen.append(dedup_key)
                    if len(pre_seen) > 500:
                        pre_seen[:] = pre_seen[-500:]
                    # All tool spans parent directly to the prompt span.
                    # Skill association is content-based — see post_handler
                    # ._path_skill_tag (matches the bash command's UA env
                    # or skills/<name>/ path) — never inferred from temporal
                    # proximity within a turn.
                    parent_span = st.data.get("prompt_span_id")
                    turn = int(st.data.get("turn", 0))
                    # Record this span for end-of-turn token aggregation
                    st.data.setdefault("turn_spans", []).append({
                        "span_id": unique_span_key,
                        "parent_span_id": parent_span,
                        "kind": "tool",
                        "tool_use_id": tool_use_id,
                        "tool_name": tool_name,
                    })
    except Exception:
        pass

    # --- Local trace: write tool_start event ---
    # Skill is suppressed: post_handler emits a single skill_invocation
    # event that subsumes both start and end, keeping the trace tidy and
    # avoiding an orphan tool_start with no matching tool_end.
    if (
        trace_writer.trace_enabled()
        and session_id
        and not is_duplicate
        and tool_name not in ("Skill", "skill")
    ):
        try:
            now_ms = int(time.time() * 1000)
            trace_writer.append_trace(client, session_id, {
                "event": "tool_start",
                "span_id": unique_span_key,
                "parent_span_id": parent_span,
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "tool_input": trace_writer.sanitize_trace_value(tool_input),
                "turn": turn,
                "start_timestamp": now_ms,
                "end_timestamp": now_ms,
            })
        except Exception:
            pass

    detail = _detail(tool_name, tool_input)
    suffix = (" " + detail) if detail else ""
    _debug(
        f"[pre] tool={tool_name}{suffix} decision=track session={session_id or '<none>'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
