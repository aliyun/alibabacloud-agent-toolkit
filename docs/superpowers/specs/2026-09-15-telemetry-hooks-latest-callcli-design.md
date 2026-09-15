# Telemetry Hooks Latest Uploader and Wrapped CallCLI Design

## Goal

Restore remote telemetry delivery and consistently recognize Alibaba Cloud
operations across every supported hook client and each plugin that ships the
shared hooks implementation.

This change covers:

- `alibabacloud-core`
- `alibabacloud-spec-ops`
- `alibabacloud-ecs-ops`
- Claude Code, Codex, the Qoder/QwenWork family, and VS Code hook surfaces
- Qoder-family manifest validation for explicit agent Markdown files

The existing `ALIBABACLOUD_TELEMETRY_DRY_RUN` behavior for LLM-call events is
explicitly out of scope.

## Current Failures

### Uploader cannot start

The bounded telemetry worker pins `alibabacloud.mcp-proxy==0.5.1` and expects
an executable named `plugin-telemetry`. Version `0.5.1` is not published to
the package source, and `plugin-telemetry` is a subcommand of the package's
default CLI rather than a standalone executable. Events consequently remain
pending or move to the failed queue without reaching the backend.

Before the bounded-worker change, hooks used the valid evolving-package form:

```bash
uvx alibabacloud.mcp-proxy@latest plugin-telemetry
```

### Wrapped CallCLI operations are filtered

Some clients invoke Alibaba Cloud MCP Core through a connector command such
as `mcpx.py call CallCLI`. The outer hook event is a Bash call whose first
shell operation is not `aliyun`, while the actual CallCLI request contains an
`aliyun` command. Current Bash classification rejects it as
`bash-not-aliyun`, so the cloud operation is absent from telemetry.

### Spec Ops manifest prevents plugin loading

`alibabacloud-spec-ops/.qoder-plugin/plugin.json` declares
`"agents": "./agents/"`. QwenWork rejects that manifest with
`agents: Path must end with .md`, so the whole plugin manifest fails and its
hooks and MCP server are not registered. Repository validation currently
checks only JSON syntax and common required keys, so it did not catch this
host-level compatibility failure.

No other plugin currently declares an `agents` field or ships an `agents/`
directory, so the existing defect is isolated to `alibabacloud-spec-ops`.

## Design

### Latest uploader with bounded execution

Keep the current on-disk queue, single-worker lock, bounded batches, hard
upload timeout, retry budget, dead-letter queue, and process-group cleanup.
Remove the fixed virtualenv and pinned-version setup. The worker command
prefix becomes:

```bash
uvx alibabacloud.mcp-proxy@latest plugin-telemetry
```

Each upload remains a child of the bounded worker and is synchronously reaped
by it. This retains the safety properties introduced by the worker while
allowing the independently released MCP proxy to evolve. `uv` provides its
normal package cache; the hooks will not reintroduce detached per-event
processes or `disown`.

Uploader override behavior through `ALIBABACLOUD_TELEMETRY_UPLOADER` remains
available for tests. Documentation will describe `uv`/`uvx` as the runtime
prerequisite and will no longer describe a persistent pinned venv.

### Shared wrapped-CallCLI normalization

Add a deterministic normalization rule shared by pre- and post-tool handling.
It recognizes a wrapped CallCLI only when the Bash command contains all of:

- an invocation of the connector script `mcpx.py`;
- the `call` operation;
- the `CallCLI` tool name;
- an embedded word-bounded `aliyun` command.

No shell evaluation or execution is used during parsing. The extracted command
is passed through the existing credential sanitization and size limits.

The normalized event uses the same semantic shape as a direct MCP Core call:

```text
event_type = mcp_tool_use
mcp_tool   = AlibabaCloud___CallCLI
event_tag  = mcp_callcli
```

Direct Bash `aliyun` execution remains `cli_command_use`. Existing native MCP
tool and Qoder/QwenWork wrapper normalization remains unchanged.

Both pre and post handlers must recognize the same wrapped operation so start
timestamps, duration, span linkage, status, and request ID extraction remain
consistent.

### Qoder agent manifest paths

Replace the spec-ops directory-valued `agents` field with explicit Markdown
paths:

```json
"agents": [
  "./agents/code-quality-reviewer.md",
  "./agents/spec-reviewer.md"
]
```

This is a Qoder/QwenWork-only manifest correction. Keep the plugin-root
`agents/` directory and leave `.claude-plugin/plugin.json` unchanged so Claude
Code continues to auto-discover its standard `agents/*.md` components. Leave
`.codex-plugin/plugin.json` unchanged as well: the Codex compatibility manifest
does not declare Claude/Qoder-style agents, and Codex's packaged capabilities
remain its skills and MCP server. The three host manifests are validated using
their own schemas rather than forcing one host's path rule onto the others.

Extend repository validation for every `.qoder-plugin/plugin.json` that
declares `agents`. Accept a string or list of strings, but require each entry
to be a plugin-relative `.md` path that resolves to an existing regular file
inside the plugin directory. This catches directories, missing files, absolute
paths, and paths escaping the plugin root before release.

## Source and Synchronization

`plugins/alibabacloud-core/hooks/` remains the canonical source. After editing
and testing it, copy the complete hooks tree to `alibabacloud-spec-ops` and
`alibabacloud-ecs-ops` using the repository's synchronization workflow.
`tools/dev-hooks/verify-hooks.sh` must confirm byte identity and reject
symlinks or divergent copies.

All client hook JSON files continue to call the same shared shell and Python
handlers, so the behavior applies uniformly without client-specific patches.

## Tests

Add or update tests that prove:

1. The worker command uses `alibabacloud.mcp-proxy@latest plugin-telemetry`.
2. The worker remains bounded and reaps uploader processes on success,
   failure, and timeout.
3. Direct and compound shell invocations of `aliyun` retain current behavior.
4. A valid `mcpx.py call CallCLI` wrapper is normalized to
   `mcp_tool_use/AlibabaCloud___CallCLI` by both pre and post handlers.
5. Text that merely mentions `aliyun`, `CallCLI`, or `mcpx.py` does not match.
6. Wrapped command credentials are sanitized before local trace or remote
   telemetry serialization.
7. Hook copies in all three plugins are byte-identical.
8. Existing client detection and trace suites pass for every supported client
   payload shape.
9. The spec-ops Qoder manifest names both agent Markdown files explicitly.
10. Qoder manifest validation rejects agent directories, missing files,
    absolute paths, and paths outside the plugin root.

## Acceptance Criteria

- A queued event can reach the uploader through the current MCP proxy release.
- No hard-coded MCP proxy version remains in the telemetry worker or hook
  documentation.
- Wrapped CallCLI activity produces the same event semantics as native MCP
  CallCLI activity.
- Existing direct CLI and MCP telemetry remains compatible.
- All repository hook verification and telemetry tests pass.
- QwenWork can parse the spec-ops manifest and register its hooks and MCP
  declaration.
- Every declared Qoder agent path resolves to an in-plugin `.md` file.
- `plugins/alibabacloud-core.zip` remains untouched.
