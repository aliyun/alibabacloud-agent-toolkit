#!/bin/bash
# Client-detection tests, focused on the host-declared markers (Qoder family,
# Codex, VS Code).
#
# qodercli / qoderIDE / QoderWork / QwenWork all install the same
# qoderwork-hooks.json, so the concrete client is resolved from the environment
# the host injects. Two independent implementations perform that resolution:
# the bash wrappers, which pick <state-dir>/<client>/, and the python handlers,
# which emit --client-name and the trace `client` field. The name-sanitizing
# rule is copied a third time into lib/state.py:client_dir(), which is what
# actually creates sessions/ and traces/. When any two of them disagree, one
# client's events split across two state buckets and uploads silently go
# missing — so these tests assert the detection results agree case by case, that
# the three copies of the sanitize rule agree byte for byte, that the whole
# family still gets its transcript parsed, and that a real hook fire lands every
# side's files in the one bucket both implementations computed.
#
# A marker only works if the manifest that installs it actually ships it, so the
# suite also reads every client hook manifest and asserts each command carries
# the marker its detection branch reads. VS Code regressed exactly that way:
# com.github.copilot/hooks/hooks.json declared no marker, so every VS Code event
# fell through to the claude-code default and was attributed to the wrong client.

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
    unset COPILOT_CLI CODEX_CLI VSCODE_AGENT \
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

# VS Code declares itself with VSCODE_AGENT=1, set in the env field of every
# command in com.github.copilot/hooks/hooks.json. A real VS Code payload carries
# no __vscode substring, so without the marker it fell through to the claude-code
# default and every VS Code event was attributed to the wrong client.
check_case "vscode agent marker"          "vscode"       VSCODE_AGENT=1
check_case "vscode marker on real payload" "vscode" \
    '{"session_id":"s1","tool_name":"runTerminalCommand"}' VSCODE_AGENT=1
check_case "vscode marker value not 1"    "claude-code"  VSCODE_AGENT=true

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

# VSCODE_AGENT is a default the manifest declares, so a marker the host itself
# injects is more specific and still wins.
check_case "qoder beats vscode marker"    "qoderwork"    QODER_WORK=1 VSCODE_AGENT=1
check_case "copilot beats vscode marker"  "copilot-cli"  COPILOT_CLI=1 VSCODE_AGENT=1
check_case "codex beats vscode marker"    "codex"        CODEX_CLI=1 VSCODE_AGENT=1

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

# --- 4. lib/state.py must sanitize by the same byte-wise rule ---------------

echo ""
echo "=== Test: client_dir() and sanitize_client_bash() agree byte for byte ==="

# client_dir() is the third copy of the sanitize rule. It names the bucket that
# holds sessions/ and traces/, while the wrappers name the bucket that holds
# debug.log and the upload queue. Production hands it an already-sanitized name,
# so a char-wise copy stays latent until something feeds it a raw non-ASCII
# client -- which is why the rule is compared directly here instead of relying
# on the end-to-end case below, where detection has sanitized the name already.
pyClientDir="$workDir/py_client_dir.py"
cat > "$pyClientDir" <<PYEOF
import sys

sys.path.insert(0, "$HOOKS_DIR/lib")
import state

print(state.client_dir(sys.argv[1]))
PYEOF

parityDir="$workDir/state-parity"
mkdir -p "$parityDir"

# check_dir_parity <description> <raw-client-name>
check_dir_parity() {
    local desc="$1" raw="$2"

    local want got
    want="$parityDir/$(. "$reference"; sanitize_client_bash "$raw")"
    got="$(ALIBABACLOUD_TELEMETRY_STATE_DIR="$parityDir" python3 "$pyClientDir" "$raw")"

    if [ "$got" != "$want" ]; then
        note_fail "client_dir: $desc -> '$got', wrapper rule gives '$want'"
        printf '    python: '; printf '%s' "${got##*/}" | od -An -tx1 | tr -d '\n'; echo
        printf '    bash:   '; printf '%s' "${want##*/}" | od -An -tx1 | tr -d '\n'; echo
    else
        echo "  ok: client_dir $desc -> ${got##*/}"
    fi
}

check_dir_parity "ascii"                 "claude-code"
check_dir_parity "spaces and slash"      "qwen work/cn"
check_dir_parity "non-ascii product"     "千问办公"
check_dir_parity "mixed ascii+non-ascii" "qwen办公cn"
# 63 ASCII bytes then a 3-byte character: the 64 cap lands inside that character.
check_dir_parity "cap splits multibyte"  "$(printf '%063d' 0 | tr '0' 'a')千问"
check_dir_parity "cap beyond 64 bytes"   "$(printf '%080d' 0 | tr '0' 'a')"

# --- 5. a real hook fire must land in the bucket both sides computed --------

echo ""
echo "=== Test: wrapper and handler agree on the state bucket (dry run) ==="

# e2e_case <description> <expected-client> [VAR=value ...]
e2e_case() {
    local desc="$1"; shift
    local expected="$1"; shift
    # Snapshot so the ok line reflects this case only, not the whole run.
    local failBefore="$fail"

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

    # One bucket only. A disagreement between the two implementations shows up
    # as a second directory, and the events in it never reach the uploader.
    local bucketCount
    bucketCount="$(find "$e2eDir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
    if [ "$bucketCount" != "1" ]; then
        note_fail "e2e $desc: expected 1 state bucket, found $bucketCount"
        find "$e2eDir" -mindepth 1 -maxdepth 2 | sed "s|^$e2eDir|    |"
    fi

    # Compare the name the fire actually produced, not a path assembled from the
    # expectation, so a non-ASCII client has to match byte for byte.
    local actual
    actual="$(find "$e2eDir" -mindepth 1 -maxdepth 1 -type d | head -1)"
    if [ "${actual##*/}" != "$expected" ]; then
        note_fail "e2e $desc: bucket '${actual##*/}' != '$expected'"
        printf '    got:      '; printf '%s' "${actual##*/}" | od -An -tx1 | tr -d '\n'; echo
        printf '    expected: '; printf '%s' "$expected" | od -An -tx1 | tr -d '\n'; echo
    fi

    local log="$e2eDir/$expected/debug.log"
    if [ ! -f "$log" ]; then
        note_fail "e2e $desc: no debug.log under $e2eDir/$expected/"
        ls -la "$e2eDir"
    elif ! grep -q "^DRYRUN: queue telemetry event --client-name $expected --event-type skill_invocation" "$log"; then
        note_fail "e2e $desc: debug.log has no --client-name $expected event"
        cat "$log"
    fi

    # debug.log is written by the wrapper; sessions/ and traces/ are created by
    # lib/state.py through the handlers. All three living in the same bucket is
    # what proves the two sides resolved one identical directory.
    local side
    for side in sessions traces; do
        if [ ! -d "$e2eDir/$expected/$side" ]; then
            note_fail "e2e $desc: no $side/ next to debug.log in $expected/"
        fi
    done

    if [ "$fail" = "$failBefore" ]; then
        echo "  ok: e2e $desc -> $expected/"
    fi

    rm -rf "$e2eDir"
    reset_client_env
}

e2e_case "no client env"        "claude-code"
# This is what a fire from com.github.copilot/hooks/hooks.json looks like: the
# manifest sets the marker in each command's env, so the whole VS Code surface
# has to land in one vscode/ bucket instead of the claude-code default.
e2e_case "vscode agent marker"  "vscode"      VSCODE_AGENT=1
e2e_case "legacy qoderwork"     "qoderwork"   QODER_WORK=1
e2e_case "qwenworkcn product"   "qwenworkcn" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_MODE=1 QODER_WORK_INTEGRATION_PRODUCT=qwenworkcn
e2e_case "qoder agent cli"      "qoder_cli_0" \
    QODER_AGENT=true QODER_HOOK_SOURCE=cli QODER_IDE=0
# The whole point of the byte-wise rule: 千问办公 is 4 characters but 12 UTF-8
# bytes, so a char-wise copy would write debug.log to ____________ while the
# handlers created sessions/ and traces/ under ____.
e2e_case "non-ascii product"    "____________" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT='千问办公'
e2e_case "mixed ascii product"  "qwen______cn" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT='qwen办公cn'
e2e_case "product capped at 64" "$(printf '%064d' 0 | tr '0' 'a')" \
    QODER_WORK=1 QODER_WORK_INTEGRATION_PRODUCT="$(printf '%080d' 0 | tr '0' 'a')"

echo ""
echo "=== Test: client hook manifests declare the marker detection reads ==="

# Sections 1-5 prove the two implementations agree with each other, but they
# cannot see a marker nobody ever sets: with no VSCODE_AGENT in the environment
# both sides returned claude-code, agreed perfectly, and reported every VS Code
# event as the wrong client. So assert the pairing from the manifest side too —
# each client-specific hooks file must declare the marker its detection branch
# reads. hooks/hooks.json (the Claude format) is skipped on purpose: it declares
# no marker because claude-code is the fall-through default.
pluginsDir="$(cd "$HOOKS_DIR/../../.." && pwd)"

manifestCheckFailed=0
python3 - <<PYEOF || manifestCheckFailed=1
import json
import os
import sys

plugins_dir = "$pluginsDir"

# Only a directory carrying the root Agent Plugins manifest is a real plugin.
# plugins/alibabacloud-agent and plugins/alibabacloud-data-analytics hold
# nothing but .gitkeep today, and a placeholder must not be required to ship
# three client hook manifests.
PLUGIN_MARKER = "plugin.json"

# How each manifest declares its marker. VS Code's hook schema documents an
# 'env' field, so com.github.copilot/ uses it: that reaches the hook process
# whether or not the host shell-parses the command string. An inline "VAR=1"
# prefix would become argv[0] under a quote-aware tokenizer and break the hook
# outright. Codex and QoderWork bake the prefix straight into the committed
# command string instead.
MANIFESTS = {
    "com.github.copilot/hooks/hooks.json": ("env", "VSCODE_AGENT", "1"),
    "hooks/codex-hooks.json": ("prefix", "CODEX_CLI=1", None),
    "hooks/qoderwork-hooks.json": ("prefix", "QODER_WORK=1", None),
}


def hook_entries(hooks):
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if isinstance(hook, dict):
                    yield hook


def declares(hook, kind, key, value):
    if kind == "env":
        env = hook.get("env")
        return isinstance(env, dict) and env.get(key) == value
    command = hook.get("command")
    return isinstance(command, str) and command.startswith(key + " ")


def label(kind, key, value):
    return "env %s=%s" % (key, value) if kind == "env" else "prefix %s" % key


failed = 0
scanned = 0
for plugin in sorted(os.listdir(plugins_dir)):
    plugin_dir = os.path.join(plugins_dir, plugin)
    if not os.path.isdir(plugin_dir):
        continue
    if not os.path.isfile(os.path.join(plugin_dir, PLUGIN_MARKER)):
        continue
    scanned += 1
    for rel, (kind, key, value) in MANIFESTS.items():
        path = os.path.join(plugin_dir, rel)
        if not os.path.isfile(path):
            print("FAIL: %s ships no %s, so that client's hooks never run"
                  % (plugin, rel))
            failed = 1
            continue
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        entries = list(hook_entries(data.get("hooks", {})))
        if not entries:
            print("FAIL: %s/%s declares no hook command" % (plugin, rel))
            failed = 1
            continue
        missing = [e for e in entries if not declares(e, kind, key, value)]
        if missing:
            print("FAIL: %s/%s has %d of %d hook(s) without %s:"
                  % (plugin, rel, len(missing), len(entries),
                     label(kind, key, value)))
            for e in missing:
                print("        %s" % e.get("command"))
            failed = 1
        else:
            print("  ok: %s/%s -> all %d hook(s) declare %s"
                  % (plugin, rel, len(entries), label(kind, key, value)))

if not scanned:
    print("FAIL: no plugin carrying a root %s found under %s"
          % (PLUGIN_MARKER, plugins_dir))
    failed = 1

sys.exit(failed)
PYEOF

if [ "$manifestCheckFailed" -ne 0 ]; then
    note_fail "client hook manifests declare the marker their detection branch reads"
fi

echo ""
if [ "$fail" -ne 0 ]; then
    echo "=== Client detection tests FAILED ==="
    exit 1
fi
echo "=== All client detection tests passed ==="
