#!/bin/bash
# Client-detection tests, focused on the Qoder family.
#
# qodercli / qoderIDE / QoderWork / QwenWork all install the same
# qoderwork-hooks.json, so the concrete client is resolved from the environment
# the host injects. Two independent implementations perform that resolution:
# the bash wrappers, which pick <state-dir>/<client>/, and the python handlers,
# which emit --client-name and the trace `client` field. When they disagree,
# one client's events split across two state buckets and uploads silently go
# missing — so these tests assert the two agree case by case, that the whole
# family still gets its transcript parsed, and that a real hook fire lands in
# the bucket both sides computed.

set -e

scriptDir="$(cd "$(dirname "$0")" && pwd)"
# Resolve the canonical hooks scripts dir (single source of truth).
HOOKS_DIR="$(cd "$scriptDir/../../plugins/alibabacloud-core/hooks/scripts" && pwd)"
fixturesDir="$scriptDir/test-fixtures/claude-code"

wrappers=(pre-tool-trace.sh post-tool-trace.sh prompt-trace.sh stop-turn-increment.sh)
handlers=(pre_handler post_handler prompt_handler stop_handler)

workDir="$(mktemp -d)"
trap 'rm -rf "$workDir"' EXIT

fail=0

note_fail() {
    echo "FAIL: $1"
    fail=1
}

reset_client_env() {
    unset COPILOT_CLI CODEX_CLI \
        QODER_WORK QODER_WORK_INTEGRATION_MODE QODER_WORK_INTEGRATION_PRODUCT \
        QODER_AGENT QODER_HOOK_SOURCE QODER_IDE
}

# --- 1. the four wrappers must carry an identical detection block -----------

echo "=== Test: detection block is identical across the 4 wrappers ==="

# Lifts sanitize_client_bash + qoder_family_client_bash + detect_client_bash
# out of a wrapper so they can be sourced without running the wrapper itself.
# Comment lines are dropped: a wrapper may explain its own copy (the stop
# wrapper does), and only the executable code has to match.
extract_block() {
    awk '
        /^sanitize_client_bash\(\) \{$/ { inblock = 1 }
        inblock { print }
        /^detect_client_bash\(\) \{$/ { indetect = 1 }
        indetect && /^\}$/ { exit }
    ' "$1" | sed '/^[[:space:]]*#/d'
}

reference="$workDir/block-reference.sh"
extract_block "$HOOKS_DIR/${wrappers[0]}" > "$reference"

if [ ! -s "$reference" ]; then
    note_fail "could not extract a detection block from ${wrappers[0]}"
else
    echo "  ok: extracted $(wc -l < "$reference" | tr -d ' ') lines from ${wrappers[0]}"
fi

candidate="$workDir/block-candidate.sh"
blockDiff="$workDir/block.diff"
for w in "${wrappers[@]:1}"; do
    extract_block "$HOOKS_DIR/$w" > "$candidate"
    if diff -u "$reference" "$candidate" > "$blockDiff" 2>&1; then
        echo "  ok: $w matches ${wrappers[0]}"
    else
        note_fail "$w carries a different detection block than ${wrappers[0]}"
        cat "$blockDiff"
    fi
done

# --- 2. bash and python must resolve the same client ------------------------

echo ""
echo "=== Test: bash and python resolve the same client ==="

pyDetect="$workDir/py_detect.py"
cat > "$pyDetect" <<PYEOF
import importlib
import sys

sys.path.insert(0, "$HOOKS_DIR/lib")
module = importlib.import_module(sys.argv[1])
detect = getattr(module, "_detect_client", None) or getattr(module, "detect_client")
print(detect(sys.argv[2] if len(sys.argv) > 2 else ""))
PYEOF

bash_detect() {
    ( . "$reference"; detect_client_bash "${1:-}" )
}

# check_case <description> <expected-client> [payload] [VAR=value ...]
check_case() {
    local desc="$1"; shift
    local expected="$1"; shift
    local payload=""
    if [ "$#" -gt 0 ]; then
        case "$1" in
            *=*) ;;
            *) payload="$1"; shift ;;
        esac
    fi

    reset_client_env
    local kv
    for kv in "$@"; do
        export "$kv"
    done

    local b
    b="$(bash_detect "$payload")"
    if [ "$b" != "$expected" ]; then
        note_fail "bash: $desc -> '$b', expected '$expected'"
    fi

    local h p
    for h in "${handlers[@]}"; do
        p="$(python3 "$pyDetect" "$h" "$payload")"
        if [ "$p" != "$expected" ]; then
            note_fail "python $h: $desc -> '$p', expected '$expected'"
        elif [ "$p" != "$b" ]; then
            note_fail "parity: $desc -> bash '$b' vs $h '$p'"
        fi
    done

    if [ "$b" = "$expected" ]; then
        echo "  ok: $desc -> $expected"
    fi
    reset_client_env
}

# Non-Qoder clients keep working exactly as before.
check_case "no client env"                "claude-code"
check_case "copilot-cli marker"           "copilot-cli"  COPILOT_CLI=1
check_case "codex marker"                 "codex"        CODEX_CLI=1
check_case "vscode payload"               "vscode"       '{"__vscode":true}'
check_case "codex turn_id payload"        "codex"        '{"turn_id":"t1"}'

# Legacy Qoder marker still means plain qoderwork.
check_case "QODER_WORK=1 only"            "qoderwork"    QODER_WORK=1
check_case "integration mode only"        "qoderwork"    QODER_WORK_INTEGRATION_MODE=1

# QODER_WORK_INTEGRATION_PRODUCT names the concrete product.
check_case "product qwenworkcn"           "qwenworkcn" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_MODE=1 QODER_WORK_INTEGRATION_PRODUCT=qwenworkcn
check_case "product wins over agent"      "qwenworkcn" \
    QODER_AGENT=true QODER_HOOK_SOURCE=cli QODER_IDE=0 QODER_WORK_INTEGRATION_PRODUCT=qwenworkcn
check_case "empty product falls through"  "qoderwork" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT=
check_case "qoder beats vscode payload"   "qoderwork" \
    '{"__vscode":true}' QODER_WORK=1

# QODER_AGENT needs both QODER_HOOK_SOURCE and QODER_IDE.
check_case "agent cli + ide"              "qoder_cli_0" \
    QODER_AGENT=true QODER_HOOK_SOURCE=cli QODER_IDE=0
check_case "agent without ide"            "qoderwork" \
    QODER_AGENT=true QODER_HOOK_SOURCE=cli
check_case "agent without source"         "qoderwork" \
    QODER_AGENT=true QODER_IDE=0
check_case "agent flag not true"          "claude-code" \
    QODER_AGENT=1 QODER_HOOK_SOURCE=cli QODER_IDE=0

# Non-qoder markers outrank the whole family.
check_case "copilot beats qoder"          "copilot-cli" \
    COPILOT_CLI=1 QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT=qwenworkcn
check_case "codex beats qoder"            "codex" \
    CODEX_CLI=1 QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT=qwenworkcn

# The resolved name doubles as a directory name, so it is sanitized and capped
# identically on both sides — byte-wise, so non-ASCII cannot split a bucket.
check_case "product with space and slash" "qwen_work_cn" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT='qwen work/cn'
# 千问办公 is 4 characters but 12 UTF-8 bytes, hence 12 underscores.
check_case "non-ascii product"            "____________" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT='千问办公'
longProduct="$(printf '%080d' 0 | tr '0' 'a')"
check_case "product capped at 64"         "${longProduct:0:64}" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT="$longProduct"

# --- 3. every Qoder-family transcript must still be parsed ------------------

echo ""
echo "=== Test: token_recorder parses the whole Qoder family ==="

python3 - <<PYEOF
import json
import os
import sys
import tempfile

sys.path.insert(0, "$HOOKS_DIR/lib")
import token_recorder as tr

record = {
    "type": "assistant",
    "sessionId": "s1",
    "message": {
        "id": "m1",
        "model": "qwen3",
        "usage": {
            "input_tokens": 11,
            "output_tokens": 7,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    },
}
fd, transcript = tempfile.mkstemp(suffix=".jsonl")
with os.fdopen(fd, "w") as handle:
    handle.write(json.dumps(record) + "\n")

QODER_KEYS = (
    "QODER_WORK", "QODER_WORK_INTEGRATION_MODE", "QODER_WORK_INTEGRATION_PRODUCT",
    "QODER_AGENT", "QODER_HOOK_SOURCE", "QODER_IDE",
)


def rows_for(client, env):
    for key in QODER_KEYS:
        os.environ.pop(key, None)
    os.environ.update(env)
    rows, _, _, _ = tr.process_stop(client, transcript, 0, 0, {}, "turn-fb")
    return rows


cases = [
    ("qoderwork", {"QODER_WORK": "1"}, 1, "qoderwork"),
    ("qwenworkcn", {
        "QODER_WORK": "1",
        "QODER_WORK_INTEGRATION_MODE": "1",
        "QODER_WORK_INTEGRATION_PRODUCT": "qwenworkcn",
    }, 1, "qwenworkcn"),
    ("qoder_cli_0", {
        "QODER_AGENT": "true",
        "QODER_HOOK_SOURCE": "cli",
        "QODER_IDE": "0",
    }, 1, "qoder_cli_0"),
    ("claude-code", {}, 1, "claude-code"),
    # A host outside the family must keep falling through to _parse_unknown.
    ("some-other-host", {}, 0, None),
]

failed = 0
for client, env, want_rows, want_label in cases:
    rows = rows_for(client, env)
    labels = sorted({row.get("client") for row in rows})
    want_labels = [want_label] if want_label else []
    if len(rows) != want_rows or labels != want_labels:
        print("FAIL: token_recorder client=%s rows=%d labels=%s, expected rows=%d labels=%s"
              % (client, len(rows), labels, want_rows, want_labels))
        failed = 1
    else:
        print("  ok: token_recorder %s -> %d row(s) labelled %s"
              % (client, len(rows), labels or "-"))

os.unlink(transcript)
sys.exit(failed)
PYEOF

# --- 4. a real hook fire must land in the bucket both sides computed --------

echo ""
echo "=== Test: wrapper and handler agree on the state bucket (dry run) ==="

# e2e_case <description> <expected-client> [VAR=value ...]
e2e_case() {
    local desc="$1"; shift
    local expected="$1"; shift

    reset_client_env
    local kv
    for kv in "$@"; do
        export "$kv"
    done

    local e2eDir
    e2eDir="$(mktemp -d)"
    ALIBABACLOUD_TELEMETRY_STATE_DIR="$e2eDir" \
    ALIBABACLOUD_TELEMETRY_DEBUG=1 \
    ALIBABACLOUD_TELEMETRY_DRY_RUN=1 \
        bash "$HOOKS_DIR/post-tool-trace.sh" \
        < "$fixturesDir/post-skill-success.json" > /dev/null 2>&1 || true

    local log="$e2eDir/$expected/debug.log"
    if [ ! -f "$log" ]; then
        note_fail "e2e $desc: no debug.log under $e2eDir/$expected/"
        ls -la "$e2eDir"
    elif ! grep -q "^DRYRUN: queue telemetry event --client-name $expected --event-type skill_invocation" "$log"; then
        note_fail "e2e $desc: debug.log has no --client-name $expected event"
        cat "$log"
    else
        echo "  ok: e2e $desc -> $expected/"
    fi

    rm -rf "$e2eDir"
    reset_client_env
}

e2e_case "no client env"        "claude-code"
e2e_case "legacy qoderwork"     "qoderwork"   QODER_WORK=1
e2e_case "qwenworkcn product"   "qwenworkcn" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_MODE=1 QODER_WORK_INTEGRATION_PRODUCT=qwenworkcn
e2e_case "qoder agent cli"      "qoder_cli_0" \
    QODER_AGENT=true QODER_HOOK_SOURCE=cli QODER_IDE=0

echo ""
if [ "$fail" -ne 0 ]; then
    echo "=== Client detection tests FAILED ==="
    exit 1
fi
echo "=== All client detection tests passed ==="
