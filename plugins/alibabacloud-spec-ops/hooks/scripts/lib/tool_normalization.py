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


def _shell_tokens(command: str) -> list[str] | None:
    """Tokenize enough shell syntax to preserve comments and pipe direction."""
    lexer = shlex.shlex(
        command,
        posix=True,
        punctuation_chars="|&;<>()\n",
    )
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        return list(lexer)
    except ValueError:
        return None


def _command_segments(tokens: list[str]) -> tuple[list[list[str]], list[str]]:
    """Split shell tokens and retain the operator between adjacent commands."""
    boundaries = {"&&", "||", ";", "&", "|", "|&", "(", ")", "\n"}
    segments: list[list[str]] = [[]]
    separators: list[str] = []
    for token in tokens:
        if token in boundaries:
            separators.append(token)
            segments.append([])
        else:
            segments[-1].append(token)
    return segments, separators


def _is_mcpx_executable(invocation: list[str], index: int) -> bool:
    """Return whether ``mcpx.py`` occupies a supported command position."""
    prefix = invocation[:index]
    while prefix and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", prefix[0]):
        prefix = prefix[1:]
    if prefix and prefix[0] == "env":
        prefix = prefix[1:]
        while prefix and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", prefix[0]):
            prefix = prefix[1:]

    if not prefix:
        return True
    launcher = os.path.basename(prefix[0])
    if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", launcher):
        return len(prefix) == 1
    if launcher != "uv" or len(prefix) < 2 or prefix[1] != "run":
        return False

    uv_args = prefix[2:]
    while uv_args:
        option = uv_args.pop(0)
        if option in {"--isolated", "--no-project", "--offline"}:
            continue
        if option == "--python" and uv_args:
            uv_args.pop(0)
            continue
        return False
    return True


def extract_wrapped_callcli(command: str) -> str | None:
    """Extract a CallCLI command from a Bash-invoked ``mcpx.py`` connector.

    Parsing is data-only: shell text is tokenized with :mod:`shlex` and JSON is
    decoded with :mod:`json`; no part of the input is evaluated or executed.
    """
    tokens = _shell_tokens(command)
    if tokens is None:
        return None
    # Correct heredoc parsing requires associating delimiters with raw lines.
    # Prefer missing one telemetry event over treating heredoc data as execution.
    if "<<" in tokens:
        return None

    segments, separators = _command_segments(tokens)
    for segment_index, invocation in enumerate(segments):
        for local_index, token in enumerate(invocation):
            if (
                os.path.basename(token) != "mcpx.py"
                or not _is_mcpx_executable(invocation, local_index)
            ):
                continue
            try:
                call_index = invocation.index("call", local_index + 1)
            except ValueError:
                continue
            if (
                call_index + 1 >= len(invocation)
                or invocation[call_index + 1] != "CallCLI"
            ):
                continue

            callcli_args = invocation[call_index + 2 :]
            direct_command = _json_command(callcli_args)
            if direct_command:
                return direct_command

            has_stdin_marker = "-" in callcli_args
            is_piped_from_previous = (
                segment_index > 0
                and separators[segment_index - 1] in {"|", "|&"}
            )
            if has_stdin_marker and is_piped_from_previous:
                piped_command = _json_command(segments[segment_index - 1])
                if piped_command:
                    return piped_command
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
