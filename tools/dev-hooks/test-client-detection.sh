#!/bin/bash
# Unit tests for qoder-family client detection in hook scripts.
# Covers the env-var based detection chain:
#   QODER_WORK_INTEGRATION_MODE=1            -> qoderwork
#   QODER_AGENT=true                         -> qoder_${QODER_HOOK_SOURCE}_${QODER_IDE}
#   QODER_WORK=1 (legacy qoderwork marker)   -> qoderwork
#   none of the above                        -> payload/default chain

set -e

scriptDir="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$(cd "$scriptDir/../../plugins/alibabacloud-core/hooks/scripts" && pwd)"

# Make sure ambient env cannot leak into detection expectations.
unset QODER_WORK_INTEGRATION_MODE QODER_AGENT QODER_HOOK_SOURCE QODER_IDE QODER_WORK \
      COPILOT_CLI CODEX_CLI 2>/dev/null || true

fail=0
check() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo "PASS: $label -> $actual"
    else
        echo "FAIL: $label expected=$expected got=$actual"
        fail=1
    fi
}

echo "=== Test: bash detect_client_bash (canonical pre-tool-trace.sh) ==="

# Extract the detect_client_bash function block from the canonical wrapper.
DETECT_FN="$(awk '/^detect_client_bash\(\) \{/{f=1} f{print} f&&/^\}/{exit}' "$HOOKS_DIR/pre-tool-trace.sh")"

check "qoderwork integration mode" "qoderwork" \
    "$(env QODER_WORK_INTEGRATION_MODE=1 bash -c "$DETECT_FN"$'\ndetect_client_bash ""')"
check "qoder family cli (IDE off)" "qoder_cli_0" \
    "$(env QODER_AGENT=true QODER_HOOK_SOURCE=cli QODER_IDE=0 bash -c "$DETECT_FN"$'\ndetect_client_bash ""')"
check "qoder family cli (IDE on)" "qoder_cli_1" \
    "$(env QODER_AGENT=true QODER_HOOK_SOURCE=cli QODER_IDE=1 bash -c "$DETECT_FN"$'\ndetect_client_bash ""')"
check "qoder family missing source/ide defaults" "qoder_unknown_0" \
    "$(env QODER_AGENT=true bash -c "$DETECT_FN"$'\ndetect_client_bash ""')"
check "legacy QODER_WORK marker" "qoderwork" \
    "$(env QODER_WORK=1 bash -c "$DETECT_FN"$'\ndetect_client_bash ""')"
check "integration mode wins over QODER_AGENT" "qoderwork" \
    "$(env QODER_WORK_INTEGRATION_MODE=1 QODER_AGENT=true QODER_HOOK_SOURCE=cli QODER_IDE=0 bash -c "$DETECT_FN"$'\ndetect_client_bash ""')"
check "no qoder env falls back to default" "claude-code" \
    "$(env bash -c "$DETECT_FN"$'\ndetect_client_bash ""')"

echo ""
echo "=== Test: python detect_client (all four canonical handlers) ==="

python3 - "$HOOKS_DIR" <<'EOF'
import importlib.util
import os
import sys

hooks_dir = sys.argv[1]
fail = 0

def load(name):
    spec = importlib.util.spec_from_file_location(name, f"{hooks_dir}/lib/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

handlers = {
    "pre_handler": load("pre_handler")._detect_client,
    "post_handler": load("post_handler").detect_client,
    "prompt_handler": load("prompt_handler")._detect_client,
    "stop_handler": load("stop_handler")._detect_client,
}

QODER_VARS = (
    "QODER_WORK_INTEGRATION_MODE", "QODER_AGENT", "QODER_HOOK_SOURCE",
    "QODER_IDE", "QODER_WORK", "COPILOT_CLI", "CODEX_CLI",
)

CASES = [
    ({"QODER_WORK_INTEGRATION_MODE": "1"}, "qoderwork"),
    ({"QODER_AGENT": "true", "QODER_HOOK_SOURCE": "cli", "QODER_IDE": "0"}, "qoder_cli_0"),
    ({"QODER_AGENT": "true", "QODER_HOOK_SOURCE": "cli", "QODER_IDE": "1"}, "qoder_cli_1"),
    ({"QODER_AGENT": "true"}, "qoder_unknown_0"),
    ({"QODER_WORK": "1"}, "qoderwork"),
    ({"QODER_WORK_INTEGRATION_MODE": "1", "QODER_AGENT": "true",
      "QODER_HOOK_SOURCE": "cli", "QODER_IDE": "0"}, "qoderwork"),
    ({}, "claude-code"),
]

for name, detect in handlers.items():
    for env, expected in CASES:
        for var in QODER_VARS:
            os.environ.pop(var, None)
        os.environ.update(env)
        actual = detect("{}")
        label = f"{name} env={env or 'none'}"
        if actual == expected:
            print(f"PASS: {label} -> {actual}")
        else:
            print(f"FAIL: {label} expected={expected} got={actual}")
            fail = 1

# token_recorder: qoder family must reuse the qoderwork (Claude-schema) parser
sys.path.insert(0, f"{hooks_dir}/lib")
import token_recorder  # noqa: E402

rows, _ = token_recorder._parse_qoderwork(
    b'{"type":"assistant","message":{"usage":{"input_tokens":3,"output_tokens":4}}}\n',
    0, "turn-x", {}, client="qoder_cli_0",
)
if rows and rows[0].get("client") == "qoder_cli_0":
    print("PASS: _parse_qoderwork preserves qoder-family client label")
else:
    print(f"FAIL: _parse_qoderwork client label rows={rows}")
    fail = 1

sys.exit(fail)
EOF
pyRc=$?
[ "$pyRc" -eq 0 ] || fail=1

echo ""
if [ "$fail" -ne 0 ]; then
    echo "FAIL: client detection tests failed"
    exit 1
fi
echo "PASS: all client detection tests passed"
