#!/usr/bin/env python3
"""User-prompt-submit hook handler.

Detects direct slash-style skill invocations (`/alibabacloud-*:<skill> ...`)
which Claude Code submits as plain prompts rather than invoking the Skill
tool. Emits a `skill_invocation` event so these are visible in telemetry
alongside Skill-tool and SKILL.md-read invocations.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Optional

# Make sibling modules importable when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sanitize  # noqa: E402
from state import SessionState  # noqa: E402
import trace_writer  # noqa: E402
import uuid  # noqa: E402

STDIN_CAP = 65536
DEBUG = os.environ.get("ALIBABACLOUD_TELEMETRY_DEBUG") == "1"

# Match a slash-style skill invocation at the start of a prompt:
#   /alibabacloud-core:alibabacloud-sdk-usage args...
SLASH_SKILL_RE = re.compile(
    r"^/(?P<plugin>alibabacloud[-a-zA-Z0-9_]*):(?P<skill>[a-zA-Z0-9_-]+)\b"
)

# Canonical arg order — must match post_handler.emit()
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


def _iso_now() -> str:
    now_ms = int(time.time() * 1000)
    t = time.gmtime(now_ms / 1000.0)
    millis = int(now_ms % 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", t) + f".{millis:03d}Z"


def _emit(args: dict) -> None:
    for key in _EMIT_ORDER:
        v = args.get(key)
        if v is None or v == "":
            continue
        print(f"--{key}")
        print(v)


def _debug(msg: str) -> None:
    if DEBUG:
        sys.stderr.write(msg if msg.endswith("\n") else msg + "\n")


def _classify_prompt(prompt: Any) -> Optional[dict]:
    if not isinstance(prompt, str) or not prompt:
        return None
    match = SLASH_SKILL_RE.match(prompt.strip())
    if not match:
        return None
    plugin = match.group("plugin")
    skill = match.group("skill")
    # Store skill_name as the bare skill (no plugin prefix) so the viewer's
    # `${plugin}:${skill}` join doesn't double the prefix.
    return {
        "skill_name": skill,
        "plugin_name": plugin,
    }


def main() -> int:
    if os.environ.get("ALIBABACLOUD_TELEMETRY") == "false":
        _debug("[prompt] decision=opted-out")
        return 1
    raw = sys.stdin.buffer.read(STDIN_CAP)
    if not raw:
        _debug("[prompt] decision=skip reason=empty-stdin")
        return 1
    text = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
    except Exception:
        _debug("[prompt] decision=skip reason=invalid-json")
        return 1
    prompt = data.get("prompt") or ""
    session_id = data.get("session_id") or ""
    if not session_id:
        _debug("[prompt] decision=skip reason=empty-session-id")
        return 1

    client = _detect_client(text)

    # --- Local trace: store prompt for potential backfill at Stop ---
    if trace_writer.trace_enabled() and session_id and prompt:
        try:
            with SessionState(client, session_id) as st:
                st.data["pending_prompt"] = prompt
                st.data["pending_prompt_ts"] = int(time.time() * 1000)
                st.data["prompt_span_id"] = uuid.uuid4().hex[:16]
                # New prompt = fresh per-turn span ledger
                st.data["turn_spans"] = []
        except Exception:
            pass

    seed = _classify_prompt(prompt)
    if seed is None:
        _debug("[prompt] decision=skip reason=not-slash-skill")
        return 1

    # Read turn and prompt_span_id; mark turn as having alibabacloud activity
    turn = 0
    prompt_span_id = ""
    try:
        with SessionState(client, session_id) as st:
            turn = int(st.data.get("turn", 0))
            prompt_span_id = st.data.get("prompt_span_id") or ""
            st.data["turn_has_trace"] = True
            if trace_writer.trace_enabled():
                # Slash-style skill: parent is the prompt span, recorded
                # in turn_spans for token aggregation.
                slash_span_id = f"skill_{seed['skill_name']}_{turn}"
                st.data.setdefault("turn_spans", []).append({
                    "span_id": slash_span_id,
                    "parent_span_id": prompt_span_id,
                    "kind": "skill_invocation",
                    "tool_use_id": "",
                    "skill_name": seed["skill_name"],
                })
    except Exception:
        pass

    now = _iso_now()
    now_ms = int(time.time() * 1000)
    tool_name = f"skill_{seed['skill_name']}"
    span_id = f"skill_{seed['skill_name']}_{turn}"
    args = {
        "client-name": client,
        "event-type": "skill_invocation",
        "start-timestamp": now,
        "end-timestamp": now,
        "tool-name": f"{turn}:{tool_name}",
        "session-id": session_id,
        "status": "success",
        "skill-name": seed["skill_name"],
        "plugin-name": seed["plugin_name"],
        "event-tag": "skill_invocation",
        "span-id": span_id,
        "parent-span-id": prompt_span_id,
    }
    _emit(args)

    # --- Local trace: write skill_invocation event ---
    if trace_writer.trace_enabled():
        trace_writer.append_trace(client, session_id, {
            "event": "skill_invocation",
            "span_id": span_id,
            "parent_span_id": prompt_span_id,
            "tool_name": "Skill",
            "skill_name": seed["skill_name"],
            "plugin_name": seed["plugin_name"],
            "status": "success",
            "turn": turn,
            "start_timestamp": now_ms,
            "end_timestamp": now_ms,
        })

    _debug(
        f"[prompt] tool={tool_name} decision=upload "
        f"event=skill_invocation skill={seed['skill_name']} "
        f"plugin={seed['plugin_name']} session={session_id} client={client}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
