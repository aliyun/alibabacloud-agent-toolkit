#!/bin/bash
# Pre-tool-use hook wrapper. Delegates to lib/pre_handler.py.
# Always exits 0 to avoid blocking the agent.
set +e
umask 077


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

clientGuess=$(detect_client_bash "")
cdirGuess=$(state_dir_for_client "$clientGuess")

if [ "${ALIBABACLOUD_TELEMETRY}" = "false" ]; then
    debug_log "$cdirGuess" "decision=opted-out (pre)"
    exit 0
fi

if [ -t 0 ]; then
    debug_log "$cdirGuess" "decision=no-stdin (pre)"
    exit 0
fi

scriptDir="$(cd "$(dirname "$0")" && pwd)"

# Buffer stdin so we can sniff client and forward to python.
payload=$(head -c 65536)
client=$(detect_client_bash "$payload")
cdir=$(state_dir_for_client "$client")

# Dump raw payload to debug.log for diagnosis
if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    {
        printf '[%s] [pre-tool] raw-payload (%d bytes):\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#payload}"
        printf '%s\n' "$payload" | head -c 4096
        printf '\n---end-payload---\n'
    } >> "$cdir/debug.log" 2>/dev/null
fi

if [ "${ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD}" = "1" ]; then
    payloadDir="$cdir/raw-payloads"
    mkdir -p "$payloadDir" 2>/dev/null && chmod 700 "$payloadDir" 2>/dev/null
    ts=$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null)
    fname="$payloadDir/pre-${ts}-$$.json"
    printf '%s' "$payload" > "$fname" 2>/dev/null && chmod 600 "$fname" 2>/dev/null
    # TTL cleanup: remove files older than 7 days; cap at 200 files
    find "$payloadDir" -type f -name "*.json" -mtime +7 -delete 2>/dev/null || \
        find "$payloadDir" -type f -name "*.json" -mtime +7 -exec rm -f {} + 2>/dev/null
    fileCount=$(find "$payloadDir" -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
    if [ "${fileCount:-0}" -gt 200 ]; then
        ls -1t "$payloadDir"/*.json 2>/dev/null | tail -n +201 | xargs rm -f 2>/dev/null
    fi
fi

if [ "${ALIBABACLOUD_TELEMETRY_DEBUG}" = "1" ]; then
    printf '%s' "$payload" | python3 "$scriptDir/lib/pre_handler.py" >/dev/null 2>>"$cdir/debug.log" || true
else
    printf '%s' "$payload" | python3 "$scriptDir/lib/pre_handler.py" >/dev/null 2>&1 || true
fi

exit 0
