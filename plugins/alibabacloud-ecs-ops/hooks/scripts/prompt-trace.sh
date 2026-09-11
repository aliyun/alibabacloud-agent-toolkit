#!/bin/bash
# UserPromptSubmit hook wrapper. Detects slash-style skill invocations
# (`/alibabacloud-*:<skill> ...`) submitted directly to Claude Code as
# prompts. Delegates classification to lib/prompt_handler.py, then queues
# the event for bounded background upload.
# Always returns success to the agent.
set +e
umask 077


return_success() {
    echo '{"continue":true}'
    exit 0
}

# Same rule as the python handlers' _sanitize_client(): [^A-Za-z0-9_-] -> '_',
# capped at 64 bytes. Byte-wise on purpose, so a non-ASCII product name lands in
# the identical per-client state directory that the python side computes.
sanitize_client_bash() {
    printf '%s' "$1" | LC_ALL=C tr -c 'A-Za-z0-9_-' '_' | head -c 64
}

# Echoes the concrete Qoder-family client, or nothing when the host is not one.
# qodercli / qoderIDE / qoderwork / qwenwork all install the same
# qoderwork-hooks.json, so they are told apart by the environment the host
# injects. Mirrors _qoder_family_client() in the python handlers.
qoder_family_client_bash() {
    if [ "${QODER_WORK:-}" != "1" ] \
        && [ "${QODER_WORK_INTEGRATION_MODE:-}" != "1" ] \
        && [ "${QODER_AGENT:-}" != "true" ]; then
        return 0
    fi
    local product="${QODER_WORK_INTEGRATION_PRODUCT:-}"
    if [ -n "$product" ]; then
        sanitize_client_bash "$product"
        return 0
    fi
    if [ "${QODER_AGENT:-}" = "true" ]; then
        local hookSource="${QODER_HOOK_SOURCE:-}"
        local ide="${QODER_IDE:-}"
        if [ -n "$hookSource" ] && [ -n "$ide" ]; then
            sanitize_client_bash "qoder_${hookSource}_${ide}"
            return 0
        fi
    fi
    echo "qoderwork"
}

detect_client_bash() {
    if [ "$COPILOT_CLI" = "1" ]; then echo "copilot-cli"; return; fi
    if [ "$CODEX_CLI" = "1" ]; then echo "codex"; return; fi
    local qoder
    qoder=$(qoder_family_client_bash)
    if [ -n "$qoder" ]; then echo "$qoder"; return; fi
    # com.github.copilot/hooks/hooks.json is the VS Code surface and sets
    # VSCODE_AGENT=1 in each command's env, so the namespace alone names the client.
    if [ "$VSCODE_AGENT" = "1" ]; then echo "vscode"; return; fi
    case "${1:-}" in *__vscode*) echo "vscode"; return ;; esac
    case "${1:-}" in *\"turn_id\":*) echo "codex"; return ;; esac
    echo "claude-code"
}

# Resolve <state-dir>/<client>/ creating it if needed; falls back to
# /tmp/alibabacloud-agent-toolkit-telemetry-<uid>/<client> when the cache
# dir is unwritable. Mirrors lib/state.py:client_dir() in shell.
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
    safe_client=$(sanitize_client_bash "$client")
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

# Resolve client + per-client dir up-front (best-effort; no payload yet).
# We refine after we read stdin so vscode / __vscode patterns can be detected.
clientGuess=$(detect_client_bash "")
cdirGuess=$(state_dir_for_client "$clientGuess")

if [ "${ALIBABACLOUD_TELEMETRY}" = "false" ]; then
    debug_log "$cdirGuess" "decision=opted-out"
    return_success
fi

if [ -t 0 ]; then
    debug_log "$cdirGuess" "decision=no-stdin"
    return_success
fi

scriptDir="$(cd "$(dirname "$0")" && pwd)"

# Buffer stdin so the python handler can read it. Cap at 64 KB to avoid
# bash variable bloat on huge prompts.
payload=$(head -c 65536)

# Refine client from the payload (handles vscode case).
client=$(detect_client_bash "$payload")
cdir=$(state_dir_for_client "$client")

# Dump raw payload to debug.log for diagnosis
if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    {
        printf '[%s] [prompt] raw-payload (%d bytes):\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#payload}"
        printf '%s\n' "$payload" | head -c 4096
        printf '\n---end-payload---\n'
    } >> "$cdir/debug.log" 2>/dev/null
fi

# Optional raw-payload trace: dump full stdin to a file so future bugs
# can be diagnosed without guessing at the payload shape.
if [ "${ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD}" = "1" ]; then
    payloadDir="$cdir/raw-payloads"
    mkdir -p "$payloadDir" 2>/dev/null && chmod 700 "$payloadDir" 2>/dev/null
    ts=$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null)
    fname="$payloadDir/prompt-${ts}-$$.json"
    printf '%s' "$payload" > "$fname" 2>/dev/null && chmod 600 "$fname" 2>/dev/null
    # TTL cleanup: remove files older than 7 days; cap at 200 files
    find "$payloadDir" -type f -name "*.json" -mtime +7 -delete 2>/dev/null || \
        find "$payloadDir" -type f -name "*.json" -mtime +7 -exec rm -f {} + 2>/dev/null
    fileCount=$(find "$payloadDir" -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
    if [ "${fileCount:-0}" -gt 200 ]; then
        ls -1t "$payloadDir"/*.json 2>/dev/null | tail -n +201 | xargs rm -f 2>/dev/null
    fi
fi

# Run handler — outputs alternating --key / value lines on success.
# Capture stdout in a variable (avoids bash 3.2 PIPESTATUS quirks with
# process substitution). Empty output means the prompt didn't match the
# slash-skill pattern. When DEBUG=1, forward python's stderr (structured
# decision lines) to debug.log so missing-event problems can be diagnosed
# offline.
if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    output=$(printf '%s' "$payload" | python3 "$scriptDir/lib/prompt_handler.py" 2>>"$cdir/debug.log")
else
    output=$(printf '%s' "$payload" | python3 "$scriptDir/lib/prompt_handler.py" 2>/dev/null)
fi
rc=$?

if [ "$rc" -ne 0 ] || [ -z "$output" ]; then
    debug_log "$cdir" "decision=filtered"
    return_success
fi

# Split output into lines preserving each whole line as one arg.
# Use a while-read loop instead of `mapfile` so this works on bash 3.2 (macOS).
lines=()
while IFS= read -r line; do
    lines+=("$line")
done <<< "$output"

if [ "${#lines[@]}" -eq 0 ]; then
    return_success
fi

# Build argv array (preserves quoting, no eval)
args=()
for line in "${lines[@]}"; do
    args+=("$line")
done

# Dry-run mode: log instead of upload
if [ "${ALIBABACLOUD_TELEMETRY_DRY_RUN}" = "1" ]; then
    {
        printf 'DRYRUN: queue telemetry event'
        for a in "${args[@]}"; do
            printf ' %q' "$a"
        done
        printf '\n'
    } >> "$cdir/debug.log" 2>/dev/null
    debug_log "$cdir" "decision=dryrun skill=$(extract_arg --skill-name "${args[@]}")"
    return_success
fi

# Queue-based upload: write event args to a JSON queue file and start
# the bounded worker. Replaces the old fire-and-forget
# `uvx alibabacloud.mcp-proxy@latest` pattern that spawned one
# unbounded process per event, causing orphan process accumulation.
debug_log "$cdir" "decision=upload skill=$(extract_arg --skill-name "${args[@]}")"

if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    {
        printf '[%s] [prompt] enqueue skill=%s\n' \
            "$(date -u +%Y%m%dT%H%M%SZ)" \
            "$(extract_arg --skill-name "${args[@]}")"
    } >> "$cdir/debug.log" 2>/dev/null
fi

printf '%s\n' "${args[@]}" | python3 "$scriptDir/lib/telemetry_enqueue.py" "$cdir" 2>/dev/null

return_success
