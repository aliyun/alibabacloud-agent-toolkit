#!/bin/bash
# Stop hook — increments the per-session turn counter at end of agent turn.
# Turn number is consumed by post-tool-trace.sh to tag --turn on each event.
# Also bound to StopFailure for symmetry; both paths log identically.
# When the turn involved alibabacloud tools, stop_handler.py emits a
# user_prompt_turn_start event to stdout which we upload to remote telemetry.
# Delegates to lib/stop_handler.py which uses fcntl-locked per-session state.
set +e
umask 077


if [ "${ALIBABACLOUD_TELEMETRY}" = "false" ]; then
    exit 0
fi

if [ -t 0 ]; then
    # No piped stdin (e.g. manual run from terminal) — nothing to do.
    exit 0
fi

scriptDir="$(cd "$(dirname "$0")" && pwd)"

# Resolve client (mirrors detect_client_bash in pre/post wrappers) so the
# debug log lands in the right per-client bucket. Payload is read from
# stdin once and passed to python; sniff a small prefix here for client
# detection without consuming stdin twice.
detect_client_bash() {
    if [ "$COPILOT_CLI" = "1" ]; then echo "copilot-cli"; return; fi
    if [ "$CODEX_CLI" = "1" ]; then echo "codex"; return; fi
    if [ "$QODER_WORK" = "1" ]; then echo "qoderwork"; return; fi
    case "${1:-}" in *__vscode*) echo "vscode"; return ;; esac
    case "${1:-}" in *\"turn_id\":*) echo "codex"; return ;; esac
    echo "claude-code"
}

state_dir_for_client() {
    local base="${ALIBABACLOUD_TELEMETRY_STATE_DIR:-$HOME/.cache/alibabacloud-agent-toolkit/telemetry}"
    if mkdir -p "$base" 2>/dev/null && touch "$base/.probe" 2>/dev/null; then
        rm -f "$base/.probe"
    else
        local uid
        uid=$(id -u 2>/dev/null || echo 0)
        base="/tmp/alibabacloud-agent-toolkit-telemetry-$uid"
        mkdir -p "$base" 2>/dev/null
    fi
    local client="${1:-claude-code}"
    local safe_client
    safe_client=$(printf '%s' "$client" | LC_ALL=C tr -c 'A-Za-z0-9_-' '_' | head -c 64)
    local cdir="$base/$safe_client"
    mkdir -p "$cdir" 2>/dev/null
    printf '%s' "$cdir"
}

debug_log() {
    [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ] || return 0
    local cdir="$1"
    local msg="$2"
    [ -n "$cdir" ] || return 0
    printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$msg" >> "$cdir/debug.log" 2>/dev/null
}

# Extract --<key> value from a flat key/value args array. Bash 3.2-safe.
extract_arg() {
    local target="$1"; shift
    local prev=""
    for a in "$@"; do
        if [ "$prev" = "$target" ]; then echo "$a"; return 0; fi
        prev="$a"
    done
}

# Buffer stdin so we can sniff client and forward to python.
payload=$(head -c 65536)

client=$(detect_client_bash "$payload")
cdir=$(state_dir_for_client "$client")

# Dump raw payload to debug.log for diagnosis
if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    {
        printf '[%s] [stop] raw-payload (%d bytes):\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#payload}"
        printf '%s\n' "$payload" | head -c 4096
        printf '\n---end-payload---\n'
    } >> "$cdir/debug.log" 2>/dev/null
fi

if [ "${ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD}" = "1" ]; then
    payloadDir="$cdir/raw-payloads"
    mkdir -p "$payloadDir" 2>/dev/null && chmod 700 "$payloadDir" 2>/dev/null
    ts=$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null)
    fname="$payloadDir/stop-${ts}-$$.json"
    printf '%s' "$payload" > "$fname" 2>/dev/null && chmod 600 "$fname" 2>/dev/null
    # TTL cleanup: remove files older than 7 days; cap at 200 files
    find "$payloadDir" -type f -name "*.json" -mtime +7 -delete 2>/dev/null || \
        find "$payloadDir" -type f -name "*.json" -mtime +7 -exec rm -f {} + 2>/dev/null
    fileCount=$(find "$payloadDir" -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
    if [ "${fileCount:-0}" -gt 200 ]; then
        ls -1t "$payloadDir"/*.json 2>/dev/null | tail -n +201 | xargs rm -f 2>/dev/null
    fi
fi

# Run handler — outputs alternating --key / value lines when the turn
# involved alibabacloud tools. Empty output / non-zero exit = no upload needed.
if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    output=$(printf '%s' "$payload" | python3 "$scriptDir/lib/stop_handler.py" 2>>"$cdir/debug.log")
else
    output=$(printf '%s' "$payload" | python3 "$scriptDir/lib/stop_handler.py" 2>/dev/null)
fi
rc=$?

if [ "$rc" -ne 0 ] || [ -z "$output" ]; then
    debug_log "$cdir" "[stop] decision=no-upload"
    exit 0
fi

# Split output into lines preserving each whole line as one arg.
lines=()
while IFS= read -r line; do
    lines+=("$line")
done <<< "$output"

if [ "${#lines[@]}" -eq 0 ]; then
    exit 0
fi

# Build argv array (preserves quoting, no eval)
args=()
for line in "${lines[@]}"; do
    args+=("$line")
done

# Dry-run mode: log instead of upload
if [ "${ALIBABACLOUD_TELEMETRY_DRY_RUN}" = "1" ]; then
    {
        printf 'DRYRUN: uvx alibabacloud.mcp-proxy@latest plugin-telemetry'
        for a in "${args[@]}"; do
            printf ' %q' "$a"
        done
        printf '\n'
    } >> "$cdir/debug.log" 2>/dev/null
    debug_log "$cdir" "[stop] decision=dryrun event=$(extract_arg --event-type "${args[@]}")"
    exit 0
fi

# Fire-and-forget: detach so the agent loop never waits on uvx.
debug_log "$cdir" "[stop] decision=upload event=$(extract_arg --event-type "${args[@]}")"

if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    # Debug mode: capture uvx output for diagnosis instead of discarding
    {
        printf '[%s] [stop] upload-start cmd=uvx alibabacloud.mcp-proxy@latest plugin-telemetry' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        for a in "${args[@]}"; do printf ' %q' "$a"; done
        printf '\n'
    } >> "$cdir/debug.log" 2>/dev/null
    (
        uvx_out=$(uvx alibabacloud.mcp-proxy@latest plugin-telemetry "${args[@]}" </dev/null 2>&1)
        uvx_rc=$?
        {
            printf '[%s] [stop] upload-done rc=%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$uvx_rc"
            if [ -n "$uvx_out" ]; then
                printf '[%s] [stop] upload-output: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$uvx_out"
            fi
        } >> "$cdir/debug.log" 2>/dev/null
    ) &
    disown 2>/dev/null
else
    ( uvx alibabacloud.mcp-proxy@latest plugin-telemetry "${args[@]}" \
        </dev/null >/dev/null 2>&1 & ) >/dev/null 2>&1
    disown 2>/dev/null
fi

exit 0
