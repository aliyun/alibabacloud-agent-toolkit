#!/usr/bin/env python3
"""Normalize host-specific tool calls into stable telemetry tool shapes."""
from __future__ import annotations

import json
import os
import re
import shlex
from typing import Any


QODERWORK_MCP_WRAPPERS = ("qw_mcp_call", "qw_mcp_get", "CallMcpTool")
NORMALIZED_CALLCLI_TOOL = (
    "mcp__alibabacloud-core__AlibabaCloud___CallCLI"
)

# Aliyun CLI invocation at the start of a command or after a shell separator.
# Word-bounded so text such as `myaliyun` and `/var/log/aliyun.log` does not
# match. Pre and post classification import this exact expression.
ALIYUN_INVOCATION_RE = re.compile(
    r"(?:^|[;&|\n(])"
    r"\s*"
    r"(?:[A-Z][A-Z0-9_]*=\S+\s+)*"
    r"(?:[^\s;&|]*/)?"
    r"aliyun"
    r"(?=\s|$|[;&|])"
)


def _unwrap_qoder(tool_name: str, tool_input: Any) -> tuple[str, Any]:
    """Unwrap a native Qoder-family MCP wrapper payload."""
    if tool_name not in QODERWORK_MCP_WRAPPERS or not isinstance(tool_input, dict):
        return tool_name, tool_input
    inner_name = tool_input.get("toolName") or tool_input.get("tool_name") or ""
    if not isinstance(inner_name, str) or not inner_name:
        return tool_name, tool_input
    inner_input = tool_input.get("arguments")
    if not isinstance(inner_input, dict):
        inner_input = {}
    return inner_name, inner_input


def _json_command(tokens: list[str]) -> str | None:
    """Return the first valid JSON object's Alibaba Cloud CLI command."""
    for token in tokens:
        if not token.startswith("{"):
            continue
        try:
            payload = json.loads(token)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        command = payload.get("command")
        if isinstance(command, str) and ALIYUN_INVOCATION_RE.search(command):
            return command
    return None


def extract_wrapped_callcli(command: str) -> str | None:
    """Extract a CallCLI command from a Bash-invoked ``mcpx.py`` connector.

    Parsing is data-only: shell text is tokenized with :mod:`shlex` and JSON is
    decoded with :mod:`json`; no part of the input is evaluated or executed.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None

    list_separators = {"&&", "||", ";"}
    for index, token in enumerate(tokens):
        if os.path.basename(token) != "mcpx.py":
            continue

        left = index
        while left > 0 and tokens[left - 1] not in list_separators:
            left -= 1
        right = index + 1
        while right < len(tokens) and tokens[right] not in list_separators:
            right += 1
        invocation = tokens[left:right]
        local_index = index - left
        try:
            call_index = invocation.index("call", local_index + 1)
        except ValueError:
            continue
        if (
            call_index + 1 >= len(invocation)
            or invocation[call_index + 1] != "CallCLI"
        ):
            continue
        return _json_command(invocation)
    return None


def normalize_tool_call(tool_name: str, tool_input: Any) -> tuple[str, Any]:
    """Normalize native Qoder wrappers and Bash-wrapped MCP Core CallCLI."""
    inner_name, inner_input = _unwrap_qoder(tool_name, tool_input)
    if inner_name != tool_name or inner_input is not tool_input:
        return inner_name, inner_input

    if tool_name != "Bash" or not isinstance(tool_input, dict):
        return tool_name, tool_input
    outer_command = tool_input.get("command")
    if not isinstance(outer_command, str):
        return tool_name, tool_input
    callcli_command = extract_wrapped_callcli(outer_command)
    if not callcli_command:
        return tool_name, tool_input
    return NORMALIZED_CALLCLI_TOOL, {"command": callcli_command}
