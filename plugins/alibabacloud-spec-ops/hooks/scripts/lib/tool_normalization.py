#!/usr/bin/env python3
"""Normalize host-specific tool calls into stable telemetry tool shapes."""
from __future__ import annotations

import json
import os
import re
import shlex
from typing import Any


QODERWORK_MCP_WRAPPERS = (
    "qw_mcp_call",
    "qw_mcp_get",
    "CallMcpTool",
    "mcp_call",
    "mcp__qw-builtin__qw_mcp_call",
)
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


def _is_alibabacloud_inner_tool(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Recognize our tools without depending on a client's private wrapper name."""
    lowered = tool_name.lower()
    if "alibabacloud" in lowered or "alibaba_cloud" in lowered:
        return True
    if tool_name in {"Skill", "skill"}:
        skill = tool_input.get("skill") or ""
        return isinstance(skill, str) and skill.lower().startswith("alibabacloud")
    if tool_name in {"Agent", "agent"}:
        subagent = tool_input.get("subagent_type") or ""
        return (
            isinstance(subagent, str)
            and subagent.lower().startswith("alibabacloud")
        )
    if tool_name in {"Read", "view", "read_file"}:
        path = (
            tool_input.get("file_path")
            or tool_input.get("filePath")
            or tool_input.get("path")
            or ""
        )
        return (
            isinstance(path, str)
            and "alibabacloud" in path.lower()
            and "/skills/" in path.replace("\\", "/").lower()
        )
    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        if not isinstance(command, str):
            return False
        normalized_command = command.replace("\\", "/")
        return bool(
            ALIYUN_INVOCATION_RE.search(command)
            or (
                "alibabacloud" in normalized_command.lower()
                and "/skills/" in normalized_command.lower()
            )
        )
    return False


def _unwrap_client_tool(tool_name: str, tool_input: Any) -> tuple[str, Any]:
    """Unwrap known or structurally safe client tool-call wrappers."""
    if not isinstance(tool_input, dict):
        return tool_name, tool_input
    inner_name = tool_input.get("toolName") or tool_input.get("tool_name") or ""
    if not isinstance(inner_name, str) or not inner_name:
        return tool_name, tool_input
    raw_inner_input = tool_input.get("arguments")
    if tool_name not in QODERWORK_MCP_WRAPPERS:
        if (
            "alibabacloud" in tool_name.lower()
            or "alibaba_cloud" in tool_name.lower()
        ):
            return tool_name, tool_input
        # Metadata lookup wrappers are not actual invocations. Other wrapper
        # names are deliberately treated as opaque unless their inner payload
        # independently proves that the operation belongs to this plugin.
        if re.search(r"(?:^|__)qw_mcp_get$", tool_name, re.IGNORECASE):
            return tool_name, tool_input
        if not isinstance(raw_inner_input, dict):
            return tool_name, tool_input
        if not _is_alibabacloud_inner_tool(inner_name, raw_inner_input):
            return tool_name, tool_input
    inner_input = raw_inner_input if isinstance(raw_inner_input, dict) else {}
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


def _strip_shell_comments(command: str) -> str:
    """Remove unquoted shell comments without consuming their newline."""
    result: list[str] = []
    quote = ""
    at_word_start = True
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            result.append(char)
            if char == quote:
                quote = ""
            elif char == "\\" and quote == '"' and index + 1 < len(command):
                index += 1
                result.append(command[index])
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            at_word_start = False
            result.append(char)
        elif char == "\\" and index + 1 < len(command):
            at_word_start = False
            result.append(char)
            index += 1
            result.append(command[index])
        elif char == "#" and at_word_start:
            while index < len(command) and command[index] != "\n":
                index += 1
            continue
        else:
            result.append(char)
            at_word_start = char.isspace() or char in ";|&()<>"
        index += 1
    return "".join(result)


def _shell_tokens(command: str) -> list[str] | None:
    """Tokenize enough shell syntax to preserve comments and pipe direction."""
    lexer = shlex.shlex(
        _strip_shell_comments(command),
        posix=True,
        punctuation_chars="|&;<>()\n",
    )
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        raw_tokens = list(lexer)
    except ValueError:
        return None

    tokens: list[str] = []
    punctuation = re.compile(r"[|&;<>()\n]+")
    operators = re.compile(r"<<<|<<|>>|>&|<&|<>|>\||&&|\|\||\|&|[;&|()<>\n]")
    for token in raw_tokens:
        if punctuation.fullmatch(token):
            tokens.extend(operators.findall(token))
        else:
            tokens.append(token)
    return tokens


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
    if prefix and os.path.basename(prefix[0]) == "env":
        prefix = prefix[1:]
        while prefix and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", prefix[0]):
            prefix = prefix[1:]

    if not prefix:
        return True
    launcher = os.path.basename(prefix[0])
    if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", launcher):
        return all(re.fullmatch(r"-[bBdEiIOPqRsSuvx]+", arg) for arg in prefix[1:])
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


def _callcli_args(invocation: list[str], mcpx_index: int) -> list[str] | None:
    """Validate supported mcpx global options and return CallCLI arguments."""
    cursor = mcpx_index + 1
    while cursor < len(invocation):
        token = invocation[cursor]
        if token.startswith("--timeout="):
            cursor += 1
            continue
        if token == "--timeout" and cursor + 1 < len(invocation):
            cursor += 2
            continue
        break
    if invocation[cursor : cursor + 2] != ["call", "CallCLI"]:
        return None
    return invocation[cursor + 2 :]


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
            callcli_args = _callcli_args(invocation, local_index)
            if not callcli_args:
                continue
            direct_command = _json_command(callcli_args[:1])
            if direct_command:
                return direct_command

            has_stdin_marker = callcli_args[0] == "-"
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
    inner_name, inner_input = _unwrap_client_tool(tool_name, tool_input)
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
