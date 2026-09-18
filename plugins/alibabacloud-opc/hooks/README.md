# Telemetry Hooks

Lifecycle hooks that record what this plugin does, so that Alibaba Cloud skill quality and
MCP integration problems can be diagnosed. Two independent channels: **remote telemetry**
(aggregate, de-identified, on by default) and a **local audit trace** (detailed, stays on
your machine, on by default).

This file documents the behaviour that matters when you install or audit the plugin. The
canonical implementation reference — event classification, status detection, span
hierarchy, the full JSONL field table, the concurrency model and the test harness — lives
with the upstream hook bundle in
[`aliyun/alibabacloud-agent-toolkit`](https://github.com/aliyun/alibabacloud-agent-toolkit),
under `plugins/alibabacloud-core/hooks/README.md`. The scripts here are a byte-identical
copy of that bundle.

## Subscribed events

| Event | Script | What it records |
|---|---|---|
| `UserPromptSubmit` | `scripts/prompt-trace.sh` | Turn start; the prompt is recorded locally only |
| `PreToolUse` | `scripts/pre-tool-trace.sh` | Tool name and inputs, span open |
| `PostToolUse` | `scripts/post-tool-trace.sh` | Status, duration, response, request id |
| `Stop` | `scripts/stop-turn-increment.sh` | Turn end, token counts, trace retention sweep |

Each client reads its own manifest: `hooks.json` (Claude Code), `codex-hooks.json` (Codex),
`qoderwork-hooks.json` (QoderWork).

## Remote telemetry

On by default. Scope is limited to Alibaba Cloud plugin activity — it does not observe
unrelated tool use.

Uploaded fields may include: event type, timestamp, client name, plugin or skill name, MCP
tool name, execution status, an anonymous session identifier, and the Alibaba Cloud OpenAPI
request id when one is present.

Additional operational context is collected **only after you opt in**, and may include
sanitized `aliyun` commands, sanitized MCP tool inputs, structured error types and token
counts.

Turn it off:

```bash
export ALIBABACLOUD_TELEMETRY=0
```

## Local audit trace

Written as JSONL under `~/.alibabacloud-agent-toolkit/telemetry/<client>/`. Not uploaded.
Intended for self-audit, troubleshooting and local visualisation.

Local records are more detailed than the remote ones and may include the user prompt for
turns that invoked an Alibaba Cloud tool, full tool inputs and responses, skill invocations
and span hierarchy, and turn lifecycle events. Responses larger than **64 KB** are
truncated and tagged `"truncated": true`. Light sanitization is applied even locally.

Trace files older than **90 days** are removed automatically at session stop, so the
directory does not grow without bound.

Turn it off:

```bash
export ALIBABACLOUD_TRACE=0
```

## Configuration

| Variable | Effect |
|---|---|
| `ALIBABACLOUD_TELEMETRY` | `0` disables remote upload |
| `ALIBABACLOUD_TRACE` | `0` disables the local JSONL trace |
| `ALIBABACLOUD_TRACE_DIR` | Overrides the local trace directory |
| `ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD` | Opts in to the additional operational context described above |
| `ALIBABACLOUD_TELEMETRY_STATE_DIR` | Overrides the per-session state directory |
| `ALIBABACLOUD_TELEMETRY_DEBUG` | Writes a debug log next to the trace files |
| `ALIBABACLOUD_TELEMETRY_DRY_RUN` | Runs the upload path without sending anything |

Queue and retry limits (`ALIBABACLOUD_TELEMETRY_MAX_QUEUE`, `_MAX_CONCURRENT`,
`_MAX_RETRIES`, `_UPLOAD_TIMEOUT`) exist for the same bundle; see the upstream reference
before changing them.

## Layout

```text
hooks/
├── hooks.json              # Claude Code manifest
├── codex-hooks.json        # Codex manifest
├── qoderwork-hooks.json    # QoderWork manifest
└── scripts/
    ├── pre-tool-trace.sh
    ├── post-tool-trace.sh
    ├── prompt-trace.sh
    ├── stop-turn-increment.sh
    └── lib/                # Python handlers, sanitizer, state, trace writer, uploader
```

## Requirements

**Python 3.10+** — the handlers run on the interpreter already present on most systems.
Remote upload additionally resolves the uploader through `uv`/`uvx`; if `uv` is absent the
upload is skipped (the local trace is unaffected). A hook that cannot run fails quietly:
telemetry is dropped, the agent turn is unaffected.
