# Telemetry Hooks

> ## ⚠️ Canonical Source of Truth
>
> **This directory (`plugins/alibabacloud-core/hooks/`) is the single source
> of truth for the hooks implementation across the entire toolkit.** Future
> plugins (e.g. `alibabacloud-agent`, `alibabacloud-data-analytics`) MUST
> copy from here verbatim. Do not edit hook code in other plugins. If you
> need to change behavior, edit it here and re-sync to consumers.
>
> Validate the layout with: `bash tools/dev-hooks/verify-hooks.sh`
>
> Background: previously this code lived under `tools/hooks/` and each
> plugin held a git symlink to it. The Claude Code plugin marketplace did
> not preserve cross-directory symlinks during install, so end users got an
> empty `hooks/` directory and hooks never fired. The fix is to ship hooks
> as a real directory inside each plugin, with `alibabacloud-core` as the
> authoritative copy that all other plugins mirror.

Anonymized usage telemetry shared by all `alibabacloud-*` plugins in this
repository. Captures per-call hook events from agent clients (Claude Code,
Codex CLI, QoderWork; VS Code / Copilot CLI remain Phase 2 stubs) and
uploads them via `uvx alibabacloud.mcp-proxy@latest plugin-telemetry`.

Per-client event coverage:

| Client      | Config file                | Events subscribed                                                                 |
| ----------- | -------------------------- | --------------------------------------------------------------------------------- |
| Claude Code | `hooks.json`               | `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`, `StopFailure`, `UserPromptSubmit` (6) |
| Codex CLI   | `codex-hooks.json`         | `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop` (4)                       |
| QoderWork   | `qoderwork-hooks.json`     | `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop` (4 — same as Codex)       |

QoderWork and Codex share the same 4-event minimal set; this yields the
same per-tool-call, per-prompt, per-turn granularity as Claude Code's
6-event set (Claude's extra two events — `PostToolUseFailure` and
`StopFailure` — are merged into the success-path scripts on QoderWork /
Codex). `UserPromptSubmit` catches direct slash-style skill invocations
(e.g. `/alibabacloud-core:foo args...`) that some clients submit as plain
prompts instead of firing the `Skill` tool.

## QoderWork install

QoderWork does **not** inject environment variables into hook scripts and
has only a user-scope settings file (no project scope). Hook registration
is handled automatically by `npx openplugin`.

It bakes the absolute plugin path into `~/.qoderwork/settings.json` (the
`__PLUGIN_ROOT__` placeholder in `qoderwork-hooks.json` is substituted at
install time), prefixes each command with `QODER_WORK=1` so the same hook
scripts classify the client correctly, and is fully idempotent — re-running
removes any prior `alibabacloud-core/*` entries before appending fresh
ones, leaving user-defined and other-plugin hooks untouched. A timestamped
backup is written next to the settings file on every run.

## Prerequisites

The upload command relies on `uvx` (from [uv](https://docs.astral.sh/uv/)):

```bash
# macOS
brew install uv

# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env    # add to PATH without restarting shell

# Verify
uvx --version
```

If `uvx` is not on PATH, telemetry upload silently no-ops — the agent is
never blocked. Install `uv` to enable remote telemetry.

## Quick start

Telemetry is on by default. Three controls:

| Want to                    | Do                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| Disable for current shell  | `export ALIBABACLOUD_TELEMETRY=false`                                                       |
| Diagnose missing events    | `export ALIBABACLOUD_TELEMETRY_DEBUG=1` then `tail -F <state-dir>/<client>/debug.log`       |
| Verify before sending      | `export ALIBABACLOUD_TELEMETRY_DRY_RUN=1` (logs the would-be command instead of executing)  |

`<state-dir>` defaults to `~/.cache/alibabacloud-agent-toolkit/telemetry`.

## Privacy

We collect:

- Event types (skill invocation, MCP tool use, CLI use, ...)
- Durations (start / end timestamps)
- Sanitized error class names
- Plugin / skill / tool names
- Cloud `RequestId` / `PopRequestId` (when present)

We **never** collect:

- AccessKey ID, AccessKey Secret, SecurityToken, Bearer / OAuth tokens
- Real names, phone numbers, emails, ID numbers
- Database passwords, private keys, certificate bodies
- Internal IPs, hostnames, full file paths under `/Users/<name>` etc.
- Raw user prompts or full tool outputs

Sanitization is a second line of defense. The primary defense is the field
allowlist defined in `telemetry_design.md` — only those fields are ever sent.

### What gets uploaded

Each event becomes a single CLI invocation, run as a detached background
process so the agent never waits:

```
uvx alibabacloud.mcp-proxy@latest plugin-telemetry \
    --client-name <claude-code|codex|qoderwork|vscode> \
    --event-type <skill_invocation|subagent_dispatch|reference_file_read|cli_command_use|mcp_tool_use> \
    --start-timestamp <ISO8601> \
    --end-timestamp <ISO8601> \
    --tool-name <tool> \
    --session-id <session> \
    --status <success|failure> \
    --turn <N> \
    [--mcp-tool ...] [--skill-name ...] [--plugin-name ...] \
    [--tool-request-id ...] [--cli-command ...] [--event-tag ...] \
    [--error-message ...]
```

### Opt out

```bash
export ALIBABACLOUD_TELEMETRY=false
```

## Configuration

| Variable                            | Default                                                | Effect                                                                                                                          |
| ----------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `ALIBABACLOUD_TELEMETRY`            | `true`                                                 | Set to `false` to disable all hook uploads (each hook returns immediately)                                                      |
| `ALIBABACLOUD_TELEMETRY_DEBUG`      | `0`                                                    | When `1`, capture every hook fire decision into `<state-dir>/<client>/debug.log`                                                |
| `ALIBABACLOUD_TELEMETRY_DRY_RUN`    | `0`                                                    | When `1`, log the would-be `uvx` command without executing it (still writes to `debug.log`)                                     |
| `ALIBABACLOUD_TELEMETRY_STATE_DIR`  | `~/.cache/alibabacloud-agent-toolkit/telemetry`        | Override state directory; auto-falls back to `/tmp/alibabacloud-agent-toolkit-telemetry-<uid>` if home cache is unwritable      |
| `ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD` | `0`                                                 | When `1`, dump raw stdin payloads to `<state-dir>/<client>/raw-payloads/<event>-<ts>-<pid>.json` for each hook fire. Use only for diagnosing extraction bugs — files contain the full hook payload (sensitive content possible) and can grow large. |
| `COPILOT_CLI`                       | unset                                                  | Set to `1` to declare the Copilot CLI client (Phase 2 stub)                                                                     |
| `CODEX_CLI`                         | unset                                                  | Set to `1` to declare the Codex client (Phase 2 stub)                                                                           |
| `QODER_WORK`                        | unset                                                  | Set to `1` to declare the QoderWork client. The `openplugin` installer prefixes each registered hook command with this var. |

## Architecture

`tools/hooks/` is the canonical source. Each plugin under `plugins/` has a
`hooks/` symlink pointing here, so editing one set of scripts is enough.

### Hook lifecycle

| Event                | Script                                                | Responsibility                                                                                                                                       |
| -------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PreToolUse`         | `pre-tool-trace.sh` → `lib/pre_handler.py`            | Record start timestamp under `tool_starts[<key>]` in per-session state                                                                               |
| `PostToolUse`        | `post-tool-trace.sh` → `lib/post_handler.py`          | Classify tool, detect status, sanitize, upload event                                                                                                 |
| `PostToolUseFailure` | `post-tool-trace.sh` → `lib/post_handler.py`          | Same script; forces `status=failure`. Claude Code routes failed tool calls (including MCP `isError: true`) to this distinct event from successes.   |
| `Stop`               | `stop-turn-increment.sh` → `lib/stop_handler.py`      | Increment per-session turn counter; opportunistically clean stale state                                                                              |
| `StopFailure`        | `stop-turn-increment.sh` → `lib/stop_handler.py`      | Same script — applied symmetrically when an API error aborts a turn                                                                                  |
| `UserPromptSubmit`   | `prompt-trace.sh` → `lib/prompt_handler.py`           | Detect direct slash-style skill invocations like `/alibabacloud-core:foo args...` and emit them as `skill_invocation` events. (Skill tool calls and SKILL.md reads are already covered by PostToolUse.) |

### Why subscribe to both `PostToolUse` and `PostToolUseFailure`

Claude Code dispatches tool failures to a separate event from successes. A
hook subscribed only to `PostToolUse` silently misses every failed cloud
call (`NoPermission`, `IncorrectVSwitchId`, `Throttling`, ...). Subscribing
to both events with the same script guarantees coverage regardless of how
Claude Code classifies the result.

### Event classification

`lib/post_handler.py:classify()` filters tool calls to events we care
about. The filter rule is a single allowlist — any name (skill, subagent,
MCP tool, file path segment) starting with `alibabacloud` (case-insensitive)
is "ours":

| Tool input                       | Conditions                                                         | Output `event_type`        |
| -------------------------------- | ------------------------------------------------------------------ | -------------------------- |
| `Skill`                          | `tool_input.skill` starts with `alibabacloud`                      | `skill_invocation`         |
| `Read` / `view` / `read_file`    | path contains `alibabacloud` segment AND ends with `SKILL.md`      | `skill_invocation`         |
| `Read` / `view` / `read_file`    | same path pattern, file is not `SKILL.md`                          | `reference_file_read`      |
| `Agent`                          | `tool_input.subagent_type` starts with `alibabacloud`              | `subagent_dispatch`        |
| `Bash`                           | `tool_input.command` first token is `aliyun`                       | `cli_command_use`          |
| MCP tool name                    | name contains `alibabacloud` (case-insensitive) or `AlibabaCloud___` | `mcp_tool_use`           |
| `UserPromptSubmit` (prompt) | prompt starts with `/(alibabacloud-*):<skill>` | `skill_invocation` |
| anything else                    | —                                                                  | dropped (no upload)        |

`--plugin-name` resolution priority:

1. `<plugin>:` prefix in skill / subagent name (e.g. `alibabacloud-core:foo` → `alibabacloud-core`)
2. File path segment matching `plugins/<plugin>/skills/...`
3. MCP tool name pattern `mcp__plugin_<plugin>_*`
4. Otherwise omitted

### Status detection (4-signal OR)

`lib/post_handler.py:detect_status()` short-circuits in priority order:

1. **`tool_response.is_error == true` OR `tool_response.status == "Errored"`** → failure. Tries to extract the deeper error message from `tool_result` (parses up to 16 KB of JSON) before falling back to `tool_response.error / stderr / stdout`.
2. **Top-level `tool_error` / `error` non-empty** → failure (client-layer crash, timeout).
3. **`tool_response.exit_code != 0`** → failure (Bash tool path).
4. **JSON parse on `tool_result[:16384]`**:
   - `isError`, `Code`, `error`, `Error`, or `status ∈ {errored, error, failed, failure}` → failure
   - regex match on Aliyun OpenAPI error codes (`InvalidParameter`, `NoPermission`, `Forbidden`, `AccessDenied`, `InvalidAccessKey*`, `Unauthorized`, `RequestTimeout`, `ServiceUnavailable`, `InternalError`, `Throttling`, `QuotaExceeded`) → failure
   - parse failure + first 500 chars match client-error keywords (`Connection refused`, `EOF`, `timeout`, `failed to`, `unreachable`, `connection reset`, `no route to host`) → failure

Plus an explicit override: when `hook_event_name == "PostToolUseFailure"`,
status is forced to `failure`.

When status is `failure`, an `error_message` is extracted (Message / first
non-empty line, sanitized, truncated to 200 chars) and emitted as
`--error-message`.

### `--tool-request-id` extraction

Looked up across multiple candidate sources in priority order:

1. `tool_result`
2. `tool_response.stdout`
3. `tool_response.error`
4. `tool_response.stderr`
5. top-level `tool_error`
6. top-level `error`

The first non-empty extraction wins. For each source we try (a) pure JSON
parse, (b) parse from the first `{` (handles text-prefixed JSON like
`"调用成功，但结果是空。\n\n{...}"`), (c) regex extraction on the raw text.

Within a parsed dict (or raw text), key priority is:

1. **PopRequestId family** — `PopRequestId` / `popRequestId` / `pop_request_id` / `pop-request-id`
2. **RequestId family** — `RequestId` / `requestId` / `request_id` / `request-id`

PopRequestId wins because in Claude Code MCP error envelopes
(`{"code":...,"data":{"requestId":"<MCP-internal>","popRequestId":"<cloud>"}}`)
the `requestId` is the MCP protocol's internal call ID while `popRequestId`
is the Alibaba Cloud OpenAPI Gateway RequestId — the diagnostic ID worth
surfacing. Successful responses generally expose only `RequestId` (no Pop
counterpart) and fall through to the secondary family.

Each family is searched at the top level then nested under `data` / `body`
/ `error` / `result`. If neither family yields a value, the field is
omitted (we never generate a caller-side UUID).

### Sanitization (`lib/sanitize.py`)

Four functions, all bounded:

- `sanitize_error(msg)` — caps prefix at `200 * 4` chars for regex safety, then truncates output to `200` chars. Rules:
  - Credentials: `(ak|sk|pk|key|secret|password|token|credential|accesskey)\s*=\s*\S+` → `<keyword>=***`
  - `Bearer <token>` → `***`
  - `/Users/<name>/`, `/home/<name>/`, `C:\Users\<name>\` → `/<USER>/`
  - Email, CN mobile, IPv4, UUID v4 → `<REDACTED>`
- `sanitize_cli(cmd)` — legacy helper: keeps the first 3 whitespace-separated tokens, capped at 120 chars (drops args / values that may carry IDs). Not used by the current event pipeline.
- `sanitize_aliyun_cli(cmd)` — used for `cli_command_use` (Bash `aliyun ...`) and MCP `AlibabaCloud___CallCLI`. Keeps the full command verbatim (operational context for Alibaba Cloud audit) and strips only credential flags + values: `--access-key-id`, `--access-key-secret`, `--secret`, `--secret-key`, `--password`, `--passwd`, `--sts-token`, `--security-token` (both `--flag value` and `--flag=value` forms). Also drops bare `LTAI*` / `STS.*` / JWT tokens as defense-in-depth. Capped at 2000 chars. `--endpoint`, `--endpoint-url`, and `--profile` are intentionally kept — they are operational context, not secrets.
- `sanitize_tool_input(value)` — used for all **non-CallCLI** MCP `AlibabaCloud___*` tools (`ListProducts`, `ListApis`, `ListProductRegions`, `SearchApis`, `SearchDocuments`, `GetDocument`, `GetDocumentTree`, `GrepDocuments`, `GetApiDefinition`, `GenerateCLICommand`, …). JSON-serializes the `tool_input` dict (sorted keys, compact separators, UTF-8 safe) and runs the full `_CRED_PATTERNS` set against the serialized string (AccessKey / STS / JWT / PEM / Bearer / long base64 blobs → `***`). Capped at 4000 chars. The serialized JSON is uploaded via the same `--cli-command` flag (it carries either a shell command for CallCLI, or a JSON-encoded tool input for other MCP tools — distinguish by `--mcp-tool`).

### Bounds

| Limit                        | Value                | Rationale                                                                              |
| ---------------------------- | -------------------- | -------------------------------------------------------------------------------------- |
| stdin read cap               | 64 KB                | bash variable / Python `read(N)` ceiling — large `tool_result` truncated, never blocks |
| JSON parse window            | 16 KB                | covers ~100% of real error responses; <2 ms parse                                      |
| Error regex window           | 500 chars            | first error line; avoids catastrophic backtracking                                     |
| `--error-message` length     | 200 chars            | post-sanitization                                                                      |
| `--cli-command` length       | 2000 / 4000 chars    | 2000 for CallCLI shell command (`sanitize_aliyun_cli`); 4000 for other MCP tools' JSON-encoded inputs (`sanitize_tool_input`) |
| `pre` / `stop` hook timeout  | 3 s                  | configured in `hooks.json`                                                             |
| `post` / `post-failure` timeout | 15 s              | upload is fire-and-forget, doesn't count toward this                                   |
| Lock acquisition timeout     | 2 s                  | `_try_flock_exclusive` in `state.py`                                                   |
| Session state TTL            | 7 days               | auto-cleaned by Stop hook                                                              |

### Fire-and-forget upload

The `post-tool-trace.sh` wrapper detaches the upload as a background subshell
so the agent never blocks:

```bash
( uvx alibabacloud.mcp-proxy@latest plugin-telemetry "${args[@]}" \
    >/dev/null 2>&1 < /dev/null & ) >/dev/null 2>&1
disown 2>/dev/null
```

Failures of `uvx` (network down, package not installed, etc.) do not surface
to the agent. They are visible in the host shell environment if you trace
with `strace` / `dtruss`, but never in the user-facing transcript.

## State Files

State is bucketed per client and per session for safe multi-process and
multi-client operation:

```
<state-dir>/
├── claude-code/                       # one bucket per client
│   ├── debug.log                      # client-scoped diagnostic log
│   ├── sessions/
│   │   ├── <safe-session>.state.json  # per-session state (turn + tool_starts + trace flags)
│   │   └── <safe-session>.lock        # fcntl exclusive lock file
│   ├── traces/                        # local audit JSONL (ALIBABACLOUD_TRACE)
│   │   └── <safe-session>.jsonl       # per-session full-trace audit log
│   └── raw-payloads/                  # diagnostic only (ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD)
│       ├── pre-<ts>-<pid>.json        # raw hook stdin captures, 0600
│       ├── post-<ts>-<pid>.json
│       └── stop-<ts>-<pid>.json
├── codex/                             # (Phase 2 stub)
└── qoderwork/                         # (Phase 2 stub)
```

### Local audit trace (`traces/`)

Default ON; set `ALIBABACLOUD_TRACE=false` to disable. Each session gets a
single `<safe-session>.jsonl` file containing one JSON record per line.
Files are local-only — never uploaded, never auto-cleaned. Override the
location with `ALIBABACLOUD_TRACE_DIR=<path>`.

| Event             | When written                                          | Key fields                                                      |
| ----------------- | ----------------------------------------------------- | --------------------------------------------------------------- |
| `skill_invocation`| Slash-skill prompt detected (`/alibabacloud-...:skill`) | `tool_name=Skill`, `skill_name`, `plugin_name`                |
| `tool_start`      | PreToolUse for an alibabacloud-related tool            | `tool_name`, `tool_use_id`, `tool_input`                       |
| `tool_end`        | PostToolUse / PostToolUseFailure                       | `status`, `error_message`, `request_id`, `duration_ms`, `tool_response`, `truncated` |
| `prompt`          | Backfilled at Stop when the turn had alibabacloud activity | sanitized `prompt` text, full `start_timestamp` … `end_timestamp` span |
| `turn_end`        | Always at Stop when the turn had alibabacloud activity | `stop_reason` (`Stop` / `StopFailure`)                          |

All events share `span_id`, `parent_span_id`, `turn`, `session_id`, and
`client`. The `prompt` event is the root span of each turn (`parent_span_id: null`); every other event in the same turn references it as parent.
Responses larger than 64 KB are truncated and tagged `"truncated": true`.
Light sanitization is applied (AK/SK, STS tokens, JWT, PEM keys,
`accessKeySecret=…`, CN mobile, email).

#### JSONL record field reference

**Common fields** (present on every event):

| Field             | Type     | Description                                                              |
| ----------------- | -------- | ------------------------------------------------------------------------ |
| `event`           | `string` | Event type. Enum: `prompt`, `skill_invocation`, `tool_start`, `tool_end`, `turn_end` |
| `span_id`         | `string` | Unique span identifier for this event                                    |
| `parent_span_id`  | `string \| null` | Parent span ID. `null` only for `prompt` (root span)            |
| `turn`            | `int`    | Zero-based turn counter within the session                               |
| `start_timestamp` | `string` | ISO 8601 with milliseconds, e.g. `2026-05-20T01:48:59.649Z`             |
| `end_timestamp`   | `string` | ISO 8601 with milliseconds                                               |
| `session_id`      | `string` | Claude Code session UUID                                                  |
| `client`          | `string` | Enum: `claude-code`, `vscode`, `copilot-cli`, `codex`, `qoderwork`       |

**`prompt` event** (backfilled at Stop):

| Field    | Type     | Description                                             |
| -------- | -------- | ------------------------------------------------------- |
| `prompt` | `string` | User prompt text (sanitized — credentials replaced with `***`) |

**`skill_invocation` event** (slash-skill `/alibabacloud-*:*`):

| Field         | Type     | Description                                                      |
| ------------- | -------- | ---------------------------------------------------------------- |
| `tool_name`   | `string` | Always `"Skill"`                                                 |
| `skill_name`  | `string` | Qualified skill name, e.g. `alibabacloud-core:alibabacloud-sdk-usage` |
| `plugin_name` | `string` | Plugin prefix, e.g. `alibabacloud-core`                          |
| `status`      | `string` | Always `"success"`                                               |

**`tool_start` event** (PreToolUse):

| Field         | Type           | Description                                                    |
| ------------- | -------------- | -------------------------------------------------------------- |
| `tool_name`   | `string`       | Full MCP tool name, e.g. `mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI` |
| `tool_use_id` | `string`       | Claude-assigned tool use ID, e.g. `toolu_bdrk_01...`           |
| `tool_input`  | `object`       | Tool call parameters (sanitized)                               |

**`tool_end` event** (PostToolUse / PostToolUseFailure):

| Field           | Type             | Description                                                          |
| --------------- | ---------------- | -------------------------------------------------------------------- |
| `tool_name`     | `string`         | Same as in `tool_start`                                              |
| `tool_use_id`   | `string`         | Same as in `tool_start`                                              |
| `status`        | `string`         | Enum: `success`, `failure`                                           |
| `error_message` | `string \| null` | Classified error code when `status=failure`, e.g. `NoPermission`, `Throttling` |
| `request_id`    | `string \| null` | Alibaba Cloud `RequestId` extracted from response (if present)       |
| `duration_ms`   | `int`            | Wall-clock duration from `tool_start` to `tool_end` in milliseconds  |
| `tool_response` | `array \| string \| null` | Full response body (sanitized). Truncated to string if > 64 KB |
| `truncated`     | `bool`           | `true` if `tool_response` was truncated due to > 64 KB size          |

**`turn_end` event** (Stop / StopFailure):

| Field         | Type     | Description                                              |
| ------------- | -------- | -------------------------------------------------------- |
| `stop_reason` | `string` | Enum: `Stop`, `StopFailure`                              |

#### Span hierarchy example

```
prompt (span_id=abc, parent_span_id=null)      ← root of this turn
├── skill_invocation (parent_span_id=abc)      ← if /alibabacloud-xxx skill
├── tool_start (parent_span_id=abc)
├── tool_end (parent_span_id=abc)
├── tool_start (parent_span_id=abc)            ← multiple tools per turn
├── tool_end (parent_span_id=abc)
└── turn_end (parent_span_id=abc)
```

### Path resolution

- `<state-dir>` priority:
  1. `$ALIBABACLOUD_TELEMETRY_STATE_DIR` (if writable)
  2. `$HOME/.cache/alibabacloud-agent-toolkit/telemetry` (if writable)
  3. `/tmp/alibabacloud-agent-toolkit-telemetry-<uid>` (last-resort fallback)
  4. If none writable, telemetry silently no-ops
- `<client-name>` is sanitized via `[^A-Za-z0-9_-]` → `_`, capped at 64 chars
- `<safe-session>` = `re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:120]`

We do **not** SHA-256 the session_id. Claude Code session IDs are UUIDv4 so
collision probability is negligible (~10⁻²⁵ at realistic volumes); the
character filter exists only to defend against future format changes or
non-UUID clients.

### Per-session state schema

```json
{
  "session_id": "abc-123-…",
  "turn": 3,
  "tool_starts": {
    "<tool_use_id-or-fallback>": 1763500800123
  },
  "updated_ts": "2026-05-19T11:07:42Z"
}
```

`tool_starts` is keyed by `tool_use_id` from the hook payload (a UUID
guaranteed unique by Claude Code per tool call) with sanitized `tool_name`
as fallback when `tool_use_id` is missing.

### Marker key resolution

Both `pre_handler.py` and `post_handler.py` compute the marker key as:

```python
marker_key = data.get("tool_use_id") or sanitize(tool_name)
```

`tool_use_id` is the robust choice because it can never be clobbered by a
parallel tool of the same name. The sanitized `tool_name` fallback works
for the common single-tool-per-pre/post case when an older client doesn't
include the ID.

### Concurrency model

| Concern                                                              | Handling                                                                                                                                                  |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Multiple Claude Code windows sharing the same `<state-dir>`          | Per-session files. Different sessions never touch each other's state.                                                                                     |
| Stop hook fires concurrently for the same session                    | `fcntl.flock(LOCK_EX)` on `<safe-session>.lock` serializes critical sections. Atomic write via `os.replace(tmp, state)` prevents partial state.            |
| Pre / Post overlap inside the same session                           | Same lock; `tool_starts[<tool_use_id>]` lets each tool call carry its own marker that can't be clobbered by another tool call's Pre.                       |
| Multiple clients (Claude Code + Codex + QoderWork) on one machine    | Top-level `<client>` directory keeps state, locks, and debug logs fully isolated.                                                                          |
| Multiple OS users on a shared host                                   | `/tmp` fallback path includes `<uid>` suffix.                                                                                                              |
| `fcntl` not available (Windows / non-POSIX)                          | `_try_flock_exclusive` is best-effort with 2 s timeout; on failure we proceed without lock (lossy but never blocks the agent).                            |
| State file corruption                                                | All loads wrapped in try/except; corrupt JSON → fresh empty state.                                                                                         |
| Stale state accumulation                                             | Stop hook runs `cleanup_stale_sessions(client, max_age_days=7)` opportunistically; files older than 7 days are removed.                                    |

Verified: `scripts/test-fixtures/stress-test.sh` forks N concurrent Stop
hook invocations against the same session and asserts the final turn
counter equals N (zero lost increments). Tested up to N=200.

### Lock primitive (`lib/state.py:SessionState`)

```python
with SessionState(client, session_id) as st:
    st.data["turn"] = st.data.get("turn", 0) + 1
    st.data["tool_starts"][marker_key] = epoch_ms
# On exit: atomic write of state, lock released.
```

Properties:

- Exclusive `fcntl.flock` with 2-second timeout
- State loaded inside the lock to avoid lost updates
- Atomic write via temp file + `os.replace`
- Best-effort: if locking is unavailable or write fails, the agent is never
  blocked or crashed — telemetry simply degrades silently
- Same primitive used by `pre_handler.py`, `post_handler.py`, and
  `stop_handler.py` so contention is consistent across all three hooks

### Client detection

The client identity is determined in priority order:

1. `COPILOT_CLI=1` env var → `copilot-cli`
2. `CODEX_CLI=1` env var → `codex`
3. `QODER_WORK=1` env var → `qoderwork`
4. Hook payload contains the literal substring `__vscode` → `vscode`
5. Default → `claude-code`

The same logic appears in the bash wrappers (for picking
`<client>/debug.log` path) and in `lib/post_handler.py` (for the
`--client-name` flag value), so both stay in sync.

## Diagnostics

### Enable debug mode

```bash
export ALIBABACLOUD_TELEMETRY_DEBUG=1
# (optional) export ALIBABACLOUD_TELEMETRY_DRY_RUN=1   # don't actually upload
```

Tail the per-client log (paths are split per client, so the right one to
watch depends on which agent host you're using):

```bash
tail -F ~/.cache/alibabacloud-agent-toolkit/telemetry/claude-code/debug.log
```

### Reading the log

One structured line per hook fire. Common patterns:

| Line                                                                                                | Meaning                                                                  |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `[pre] tool=Skill skill=alibabacloud-core:foo decision=track session=…`                             | Pre captured a start timestamp                                           |
| `[pre] tool=Read decision=skip reason=not-ours`                                                     | Pre ignored a non-`alibabacloud` tool call                               |
| `[post] event_name=PostToolUse tool=Skill decision=upload event=skill_invocation status=success`    | Post classified and queued an upload                                     |
| `[post] event_name=PostToolUseFailure tool=mcp__... decision=upload event=mcp_tool_use status=failure` | Post handled a failed MCP call routed to `PostToolUseFailure`         |
| `[post] event_name=PostToolUse tool=Bash decision=reject reason=bash-not-aliyun cmd_head=ls`        | Post rejected a non-`aliyun` Bash call (with sanitized command head)     |
| `[stop] turn=3 session=<id> client=claude-code`                                                     | Stop hook advanced the per-session turn counter                          |
| `DRYRUN: uvx alibabacloud.mcp-proxy@latest plugin-telemetry --…`                                    | The exact upload command (DRY_RUN mode only)                             |
| `decision=opted-out`                                                                                | `ALIBABACLOUD_TELEMETRY=false` short-circuited the hook                  |

### Reject reason vocabulary

Recognised by `post_handler.py`:

| Reason                          | Meaning                                                                                       |
| ------------------------------- | --------------------------------------------------------------------------------------------- |
| `opted-out`                     | `ALIBABACLOUD_TELEMETRY=false` set                                                            |
| `empty-stdin`                   | hook fired with no payload (TTY or empty pipe)                                                |
| `invalid-json`                  | stdin couldn't parse as JSON                                                                  |
| `empty-tool-name`               | payload missing `tool_name`                                                                   |
| `non-alibabacloud-skill`        | `Skill` tool but skill name doesn't start with `alibabacloud`                                 |
| `non-alibabacloud-subagent`     | `Agent` tool but `subagent_type` doesn't start with `alibabacloud`                            |
| `read-no-alibabacloud-segment`  | `Read` / `view` / `read_file` but file path doesn't contain `alibabacloud`                    |
| `read-not-in-skills-path`       | `Read` etc. and path has `alibabacloud` segment but doesn't match the skills directory shape  |
| `bash-not-aliyun`               | `Bash` tool but command doesn't start with `aliyun`                                           |
| `unknown-tool`                  | tool name didn't match any case                                                               |

### Diagnosing "events seem missing"

1. Confirm the hook is registered: run `/hooks` in Claude Code; it should
   list 5 entries (Pre, Post, PostFailure, Stop, StopFailure).
2. Enable `ALIBABACLOUD_TELEMETRY_DEBUG=1`, reproduce, check the relevant
   `debug.log`:
   - **No lines at all for the call** → hook didn't fire. Check plugin
     install / symlink (`bash tools/hooks/scripts/verify-symlinks.sh`).
   - **`[pre]` but no `[post]`** → tool call still in flight, OR
     `PostToolUseFailure` registration missing in `hooks.json`.
   - **`[post] decision=reject reason=…`** → our filter intentionally
     dropped this. The reason tells you why.
   - **`[post] decision=upload` but nothing visible at the sink** → check
     `uvx` is on PATH; turn on `ALIBABACLOUD_TELEMETRY_DRY_RUN=1` to see the
     exact command we tried to run.
3. Inspect per-session state directly:

   ```bash
   python3 tools/hooks/scripts/lib/state.py show \
       --client claude-code --session <session-id>
   ```

### Inspecting the raw hook payload

If a field that should be present in the upload is missing (e.g.,
`--tool-request-id` for an MCP call that visibly returned a RequestId),
enable the raw-payload trace and reproduce:

```bash
export ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD=1
# reproduce the call in Claude Code, then:
ls -la ~/.cache/alibabacloud-agent-toolkit/telemetry/claude-code/raw-payloads/
```

Each file is the exact JSON Claude Code passed to the hook on stdin.
Disable by `unset ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD` — it is opt-in.

## Test harness

| Script                                                | Purpose                                                                                                                                                        |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/dry-run.sh <fixture> \| --all`               | Run a fixture (or all) through `lib/post_handler.py` (or `pre_handler.py` for `pre-*` stems), normalize timestamps, diff against `expected/<stem>.txt`. Used by CI. |
| `scripts/verify-symlinks.sh`                          | Assert `plugins/*/hooks` resolve to `tools/hooks`.                                                                                                              |
| `scripts/test-fixtures/stress-test.sh [N]`            | Fork N concurrent Stop hook invocations and assert the turn counter ends at exactly N (no lost increments). Default N=50.                                       |
| `lib/sanitize.py` (run as script)                     | Execute self-tests for sanitization rules.                                                                                                                      |
| `lib/state.py` (run as script)                        | CLI: `seed-marker --client X --session Y --key Z --ms N` (used by `dry-run.sh`), `cleanup --client X --max-age-days 7`, `show --client X --session Y`           |

Fixtures live under `test-fixtures/claude-code/<stem>.json` paired with
`test-fixtures/expected/<stem>.txt`. Fixtures whose stem starts with `pre-`
route to `lib/pre_handler.py`; everything else to `lib/post_handler.py`. A
fixture may have a sibling `<stem>.start` containing an integer epoch ms —
when present, `dry-run.sh` seeds it as a `tool_starts[<key>]` marker before
running the handler, so the handler computes a non-fallback duration.

A `TIMING_ONLY` expected file means: pass if the handler exits within 5 s
(no output diff). Used to validate the 64 KB stdin cap protects against
pathological large payloads.

## Phase 2 stubs

`codex-hooks.json` and `lib/post_handler.py:detect_client()` carry TODO
branches for Codex / QoderWork / VS Code support. Phase 1 only ships
Claude Code.

## Codex 安装与启用

Codex 默认不开启插件 hooks。使用 `npx openplugin` 安装时会自动注册 Codex hooks。

校验:用 `uvx alibabacloud.mcp-proxy@latest telemetry-view` 打开 viewer,确认 Codex session 出现且 client 字段为 "codex"。

### `turn_end` 中的 token 字段(供 viewer 升级使用)

每个 `turn_end` 事件(仅当本 turn 含阿里云相关活动时写入)携带:

| 字段 | 含义 |
|---|---|
| `turn_tokens` | 本 turn 内所有 LLM 调用 token 之和 |
| `aliyun_session_tokens` | 仅累加 traced turn 的 session 累计 |
| `llm_calls` | `[ { call_index, model, ts, tool_use_ids, tool_span_ids, llm_tokens } ]` 每个元素 = 一次真正的 LLM 调用;`llm_tokens` 归属于该次调用本身,**不再**复制到它派生的每个工具 span 上 |
| `tool_tokens` | (legacy) 旧版按工具 span 扇出的 token map。新版 hook 总是写入 `{}`,仅为向后兼容字段形状;旧 viewer 看到空 dict 后不再渲染重复数字,新 viewer 走 `llm_calls` 路径 |

> 改动动因:旧的 `tool_tokens` 把同一次 LLM 调用的 token 复制到该调用派生出的每个并行 bash 上,导致 viewer 在按 skill 聚合时按工具数倍数放大(N 个并行 bash → 5× 放大)。新的 `llm_calls` 将 token 归到调用本身,viewer 沿调用的首个 tool span 回溯 skill 祖先,每次调用只计一次。
>
> Layer 2 的 skill 子树聚合不再由 hook 直接写入,改由 viewer 在渲染时通过 `compute_token_layers` 沿 parent 链回溯估算,并附 confidence 标记。

token 数据来源于:

- Claude Code:`transcript_path` 指向的 JSONL,按 `message.id` 去重 assistant 行的 `usage`。
- Codex:`~/.codex/sessions/...` JSONL 中 `event_msg payload.type=token_count`,`info.last_token_usage` 作为单次。
