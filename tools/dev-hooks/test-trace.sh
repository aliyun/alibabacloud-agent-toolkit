#!/bin/bash
# Integration test for local JSONL trace feature.
# Simulates a full turn: prompt → pre (tool_start) → post (tool_end) → stop (backfill + turn_end)
# Verifies the trace JSONL file contains all expected events with correct span hierarchy.

set -e

scriptDir="$(cd "$(dirname "$0")" && pwd)"
# Resolve the canonical hooks scripts dir (single source of truth).
HOOKS_DIR="$(cd "$scriptDir/../../plugins/alibabacloud-core/hooks/scripts" && pwd)"
fixturesDir="$scriptDir/test-fixtures/trace"

# Isolated state + trace dir
stateDir="$(mktemp -d)"
traceDir="$(mktemp -d)"
trap 'rm -rf "$stateDir" "$traceDir"' EXIT

export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir"
export ALIBABACLOUD_TRACE_DIR="$traceDir"
export ALIBABACLOUD_TELEMETRY="true"
export ALIBABACLOUD_TRACE="true"

echo "=== Test: Full trace flow ==="

# 1. Prompt (stores prompt in state, no trace yet)
python3 "$HOOKS_DIR/lib/prompt_handler.py" < "$fixturesDir/prompt-basic.json" > /dev/null 2>&1 || true

# 2. Pre (writes tool_start, marks turn_has_trace)
python3 "$HOOKS_DIR/lib/pre_handler.py" < "$fixturesDir/pre-mcp-call.json" > /dev/null 2>&1 || true

# 3. Post (writes tool_end with response)
# Need to seed start marker first
python3 "$HOOKS_DIR/lib/state.py" seed-marker \
    --client claude-code \
    --session trace-test-session \
    --key toolu_test_001 \
    --ms 1716100000000

python3 "$HOOKS_DIR/lib/post_handler.py" < "$fixturesDir/post-mcp-success.json" > /dev/null 2>&1 || true

# 4. Stop (backfills prompt, writes turn_end)
python3 "$HOOKS_DIR/lib/stop_handler.py" < "$fixturesDir/stop-basic.json" > /dev/null 2>&1 || true

# Verify trace file exists
traceFile="$traceDir/trace-test-session.jsonl"
if [ ! -f "$traceFile" ]; then
    echo "FAIL: trace file not created at $traceFile"
    echo "Contents of trace dir:"
    ls -la "$traceDir"
    exit 1
fi

# Verify event count (expect: tool_start + tool_end + prompt + turn_end = 4)
lineCount=$(wc -l < "$traceFile" | tr -d ' ')
if [ "$lineCount" -ne 4 ]; then
    echo "FAIL: expected 4 trace events, got $lineCount"
    cat "$traceFile"
    exit 1
fi

# Verify each event type exists
for event in "tool_start" "tool_end" "prompt" "turn_end"; do
    if ! grep -q "\"event\": \"$event\"" "$traceFile" && ! grep -q "\"event\":\"$event\"" "$traceFile"; then
        echo "FAIL: missing event type '$event'"
        cat "$traceFile"
        exit 1
    fi
done

# Verify span hierarchy: tool events have parent_span_id matching prompt's span_id
promptSpan=$(python3 -c "
import json
for line in open('$traceFile'):
    r = json.loads(line)
    if r['event'] == 'prompt':
        print(r['span_id'])
        break
")
toolParent=$(python3 -c "
import json
for line in open('$traceFile'):
    r = json.loads(line)
    if r['event'] == 'tool_start':
        print(r.get('parent_span_id', ''))
        break
")
if [ "$promptSpan" != "$toolParent" ]; then
    echo "FAIL: span hierarchy broken. prompt span_id=$promptSpan, tool parent_span_id=$toolParent"
    cat "$traceFile"
    exit 1
fi

echo "PASS: Full trace flow"

echo ""
echo "=== Test: Trace disabled ==="

export ALIBABACLOUD_TRACE="false"
traceDir2="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir2"

python3 "$HOOKS_DIR/lib/prompt_handler.py" < "$fixturesDir/prompt-basic.json" > /dev/null 2>&1 || true
python3 "$HOOKS_DIR/lib/pre_handler.py" < "$fixturesDir/pre-mcp-call.json" > /dev/null 2>&1 || true
python3 "$HOOKS_DIR/lib/stop_handler.py" < "$fixturesDir/stop-basic.json" > /dev/null 2>&1 || true

if [ -f "$traceDir2/trace-test-session.jsonl" ]; then
    echo "FAIL: trace file created when ALIBABACLOUD_TRACE=false"
    exit 1
fi
echo "PASS: Trace disabled"
rm -rf "$traceDir2"

echo ""
echo "=== Test: Non-alibabacloud turn produces no trace ==="

export ALIBABACLOUD_TRACE="true"
traceDir3="$(mktemp -d)"
stateDir3="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir3"
export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir3"

# Only prompt + stop (no alibabacloud tool call in between)
python3 "$HOOKS_DIR/lib/prompt_handler.py" < "$fixturesDir/prompt-basic.json" > /dev/null 2>&1 || true
python3 "$HOOKS_DIR/lib/stop_handler.py" < "$fixturesDir/stop-basic.json" > /dev/null 2>&1 || true

if [ -f "$traceDir3/trace-test-session.jsonl" ]; then
    echo "FAIL: trace file created for non-alibabacloud turn"
    exit 1
fi
echo "PASS: Non-alibabacloud turn produces no trace"
rm -rf "$traceDir3" "$stateDir3"

echo ""
echo "=== Test: Sanitization ==="

export ALIBABACLOUD_TRACE="true"
traceDir4="$(mktemp -d)"
stateDir4="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir4"
export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir4"

# Prompt with sensitive data (AK in Chinese context — tests CJK-compatible sanitization)
echo '{"session_id":"trace-sanitize","prompt":"用LTAItestFAKEnotREAL1234这个key查询ECS","hook_event_name":"UserPromptSubmit"}' | \
    python3 "$HOOKS_DIR/lib/prompt_handler.py" > /dev/null 2>&1 || true

# Trigger alibabacloud tool to mark turn
echo '{"session_id":"trace-sanitize","tool_name":"mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI","tool_use_id":"toolu_san_001","tool_input":{"command":"aliyun ecs DescribeInstances"},"hook_event_name":"PreToolUse"}' | \
    python3 "$HOOKS_DIR/lib/pre_handler.py" > /dev/null 2>&1 || true

# Stop to trigger backfill
echo '{"session_id":"trace-sanitize","hook_event_name":"Stop"}' | \
    python3 "$HOOKS_DIR/lib/stop_handler.py" > /dev/null 2>&1 || true

traceFile4="$traceDir4/trace-sanitize.jsonl"
if grep -q "LTAItestFAKEnotREAL1234" "$traceFile4" 2>/dev/null; then
    echo "FAIL: AK not sanitized in trace"
    cat "$traceFile4"
    exit 1
fi
if grep -q '\*\*\*' "$traceFile4" 2>/dev/null; then
    echo "PASS: Sanitization"
else
    echo "FAIL: No sanitization markers found"
    cat "$traceFile4"
    exit 1
fi
rm -rf "$traceDir4" "$stateDir4"

echo ""
echo "=== Test: Response truncation >64KB ==="

export ALIBABACLOUD_TRACE="true"
traceDir5="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir5"

# Generate a fixture with a huge response (>64KB)
bigResponse=$(python3 -c "print('x' * 100000)")
tmpFixture="$(mktemp)"
cat > "$tmpFixture" <<FIXTURE
{
  "session_id": "trace-truncate",
  "tool_name": "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI",
  "tool_use_id": "toolu_big_001",
  "tool_input": {"command": "aliyun ecs DescribeInstances"},
  "tool_response": [{"type": "text", "text": "$bigResponse"}],
  "hook_event_name": "PostToolUse"
}
FIXTURE

# Prompt + pre + post + stop
echo '{"session_id":"trace-truncate","prompt":"big response test","hook_event_name":"UserPromptSubmit"}' | \
    python3 "$HOOKS_DIR/lib/prompt_handler.py" > /dev/null 2>&1 || true
echo '{"session_id":"trace-truncate","tool_name":"mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI","tool_use_id":"toolu_big_001","tool_input":{"command":"aliyun ecs DescribeInstances"},"hook_event_name":"PreToolUse"}' | \
    python3 "$HOOKS_DIR/lib/pre_handler.py" > /dev/null 2>&1 || true

# Seed start marker
python3 "$HOOKS_DIR/lib/state.py" seed-marker --client claude-code --session trace-truncate --key toolu_big_001 --ms 1716100000000

python3 "$HOOKS_DIR/lib/post_handler.py" < "$tmpFixture" > /dev/null 2>&1 || true
echo '{"session_id":"trace-truncate","hook_event_name":"Stop"}' | \
    python3 "$HOOKS_DIR/lib/stop_handler.py" > /dev/null 2>&1 || true

traceFile5="$traceDir5/trace-truncate.jsonl"
if ! grep -q '"truncated": true' "$traceFile5" 2>/dev/null && ! grep -q '"truncated":true' "$traceFile5" 2>/dev/null; then
    echo "FAIL: truncated flag not set for >64KB response"
    if [ -f "$traceFile5" ]; then
        python3 -c "
import json
for line in open('$traceFile5'):
    r = json.loads(line)
    if r.get('event') == 'tool_end':
        print(f'truncated={r.get(\"truncated\")}')
        print(f'response_len={len(json.dumps(r.get(\"tool_response\", \"\")))}')
" 2>/dev/null || cat "$traceFile5"
    fi
    exit 1
fi
echo "PASS: Response truncation >64KB"
rm -rf "$traceDir5"
rm -f "$tmpFixture"

echo ""
echo "=== Test: Stop emits user_prompt_turn_start to stdout ==="

export ALIBABACLOUD_TRACE="true"
traceDir6="$(mktemp -d)"
stateDir6="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir6"
export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir6"

# Simulate a full turn: prompt → pre (sets turn_has_trace) → stop
echo '{"session_id":"trace-emit-test","prompt":"test prompt","hook_event_name":"UserPromptSubmit"}' | \
    python3 "$HOOKS_DIR/lib/prompt_handler.py" > /dev/null 2>&1 || true

echo '{"session_id":"trace-emit-test","tool_name":"mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI","tool_use_id":"toolu_emit_001","tool_input":{"command":"aliyun ecs DescribeInstances"},"hook_event_name":"PreToolUse"}' | \
    python3 "$HOOKS_DIR/lib/pre_handler.py" > /dev/null 2>&1 || true

# Stop should emit user_prompt_turn_start to stdout
stopOutput=$(echo '{"session_id":"trace-emit-test","hook_event_name":"Stop"}' | \
    python3 "$HOOKS_DIR/lib/stop_handler.py" 2>/dev/null)
stopRc=$?

if [ "$stopRc" -ne 0 ]; then
    echo "FAIL: stop_handler exited with code $stopRc (expected 0 for emit)"
    exit 1
fi
if [ -z "$stopOutput" ]; then
    echo "FAIL: stop_handler produced no stdout (expected user_prompt_turn_start)"
    exit 1
fi
if ! echo "$stopOutput" | grep -q "user_prompt_turn_start"; then
    echo "FAIL: stdout missing event-type user_prompt_turn_start"
    echo "Got: $stopOutput"
    exit 1
fi
if ! echo "$stopOutput" | grep -q "\-\-span-id"; then
    echo "FAIL: stdout missing --span-id"
    echo "Got: $stopOutput"
    exit 1
fi
if ! echo "$stopOutput" | grep -q "\-\-start-timestamp"; then
    echo "FAIL: stdout missing --start-timestamp"
    echo "Got: $stopOutput"
    exit 1
fi
echo "PASS: Stop emits user_prompt_turn_start to stdout"
rm -rf "$traceDir6" "$stateDir6"

echo ""
echo "=== Test: Stop does NOT emit when no alibabacloud tools used ==="

traceDir7="$(mktemp -d)"
stateDir7="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir7"
export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir7"

# Only prompt + stop (no alibabacloud pre_handler call)
echo '{"session_id":"trace-noemit-test","prompt":"hello world","hook_event_name":"UserPromptSubmit"}' | \
    python3 "$HOOKS_DIR/lib/prompt_handler.py" > /dev/null 2>&1 || true

stopOutput2=$(echo '{"session_id":"trace-noemit-test","hook_event_name":"Stop"}' | \
    python3 "$HOOKS_DIR/lib/stop_handler.py" 2>/dev/null) && stopRc2=0 || stopRc2=$?

if [ "$stopRc2" -eq 0 ] && [ -n "$stopOutput2" ]; then
    echo "FAIL: stop_handler emitted for non-alibabacloud turn"
    echo "Got: $stopOutput2"
    exit 1
fi
echo "PASS: Stop does NOT emit when no alibabacloud tools used"
rm -rf "$traceDir7" "$stateDir7"

echo ""
echo "=== Test: Slash-skill prompt records skill_invocation event ==="

export ALIBABACLOUD_TRACE="true"
traceDir8="$(mktemp -d)"
stateDir8="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir8"
export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir8"

# Simulate: /alibabacloud-core:alibabacloud-sdk-usage prompt → pre (MCP tool) → stop
echo '{"session_id":"trace-skill-inv","prompt":"/alibabacloud-core:alibabacloud-sdk-usage give me an ECS example","hook_event_name":"UserPromptSubmit"}' | \
    python3 "$HOOKS_DIR/lib/prompt_handler.py" > /dev/null 2>&1 || true

echo '{"session_id":"trace-skill-inv","tool_name":"mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI","tool_use_id":"toolu_sk_001","tool_input":{"command":"aliyun ecs DescribeInstances"},"hook_event_name":"PreToolUse"}' | \
    python3 "$HOOKS_DIR/lib/pre_handler.py" > /dev/null 2>&1 || true

echo '{"session_id":"trace-skill-inv","hook_event_name":"Stop"}' | \
    python3 "$HOOKS_DIR/lib/stop_handler.py" > /dev/null 2>&1 || true

traceFile8="$traceDir8/trace-skill-inv.jsonl"
if [ ! -f "$traceFile8" ]; then
    echo "FAIL: trace file not created"
    exit 1
fi

# Verify skill_invocation event exists
if ! grep -q '"event": "skill_invocation"' "$traceFile8" && ! grep -q '"event":"skill_invocation"' "$traceFile8"; then
    echo "FAIL: missing skill_invocation event in trace"
    cat "$traceFile8"
    exit 1
fi

# Verify skill_invocation has tool_name "Skill"
if ! grep '"skill_invocation"' "$traceFile8" | grep -q '"tool_name": "Skill"\|"tool_name":"Skill"'; then
    echo "FAIL: skill_invocation event missing tool_name=Skill"
    cat "$traceFile8"
    exit 1
fi

# Verify skill_invocation has correct parent_span_id (same as prompt's span_id)
promptSpan8=$(python3 -c "
import json
for line in open('$traceFile8'):
    r = json.loads(line)
    if r['event'] == 'prompt':
        print(r['span_id'])
        break
")
skillParent8=$(python3 -c "
import json
for line in open('$traceFile8'):
    r = json.loads(line)
    if r['event'] == 'skill_invocation':
        print(r.get('parent_span_id', ''))
        break
")
if [ "$promptSpan8" != "$skillParent8" ]; then
    echo "FAIL: skill_invocation parent_span_id=$skillParent8 != prompt span_id=$promptSpan8"
    cat "$traceFile8"
    exit 1
fi

echo "PASS: Slash-skill prompt records skill_invocation event"
rm -rf "$traceDir8" "$stateDir8"

echo ""
echo "=== Test: namespaced QoderWork MCP wrapper records inner MCP tool ==="

export ALIBABACLOUD_TRACE="true"
traceDir9="$(mktemp -d)"
stateDir9="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir9"
export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir9"
export QODER_WORK="1"

echo '{"session_id":"trace-qw-mcp","prompt":"用 qoderwork mcp 查 ECS skill","hook_event_name":"UserPromptSubmit"}' | \
    python3 "$HOOKS_DIR/lib/prompt_handler.py" > /dev/null 2>&1 || true

echo '{"session_id":"trace-qw-mcp","tool_name":"mcp__qw-builtin__qw_mcp_call","tool_use_id":"toolu_qw_mcp_trace","tool_input":{"toolName":"mcp__alibabacloud-core__AlibabaCloud___CallCLI","arguments":{"command":"aliyun agentexplorer search-skills --keyword ECS --max-results 30 --region cn-hangzhou --user-agent AlibabaCloud-Agent-Skills/alibabacloud-find-skills"},"timeout":120},"hook_event_name":"PreToolUse"}' | \
    python3 "$HOOKS_DIR/lib/pre_handler.py" > /dev/null 2>&1 || true

echo '{"session_id":"trace-qw-mcp","tool_name":"mcp__qw-builtin__qw_mcp_call","tool_use_id":"toolu_qw_mcp_trace","tool_input":{"toolName":"mcp__alibabacloud-core__AlibabaCloud___CallCLI","arguments":{"command":"aliyun agentexplorer search-skills --keyword ECS --max-results 30 --region cn-hangzhou --user-agent AlibabaCloud-Agent-Skills/alibabacloud-find-skills"},"timeout":120},"tool_response":[{"type":"text","text":"{\"requestId\":\"AC9002D7-6855-56DA-B39E-FA0B8E90B0D0\",\"data\":[]}"}],"hook_event_name":"PostToolUse"}' | \
    python3 "$HOOKS_DIR/lib/post_handler.py" > /dev/null 2>&1 || true

traceFile9="$traceDir9/trace-qw-mcp.jsonl"
if [ ! -f "$traceFile9" ]; then
    echo "FAIL: qoderwork MCP wrapper trace file not created"
    ls -la "$traceDir9"
    exit 1
fi

if ! grep -q '"event": "tool_start"' "$traceFile9" || ! grep -q '"event": "tool_end"' "$traceFile9"; then
    echo "FAIL: qoderwork MCP wrapper missing tool_start/tool_end"
    cat "$traceFile9"
    exit 1
fi

if ! grep -q '"tool_name": "mcp__alibabacloud-core__AlibabaCloud___CallCLI"' "$traceFile9"; then
    echo "FAIL: qoderwork MCP wrapper did not normalize tool_name"
    cat "$traceFile9"
    exit 1
fi

if ! grep -q '"skill_tag": "alibabacloud:alibabacloud-find-skills"' "$traceFile9"; then
    echo "FAIL: qoderwork MCP wrapper did not preserve skill_tag"
    cat "$traceFile9"
    exit 1
fi

echo "PASS: namespaced QoderWork MCP wrapper records inner MCP tool"
unset QODER_WORK
rm -rf "$traceDir9" "$stateDir9"

echo ""
echo "=== Test: New Qoder mcp_call records inner MCP tool ==="

traceDir10="$(mktemp -d)"
stateDir10="$(mktemp -d)"
export ALIBABACLOUD_TRACE_DIR="$traceDir10"
export ALIBABACLOUD_TELEMETRY_STATE_DIR="$stateDir10"
export QODER_WORK="1"
export QODER_PRODUCT_ID="qoder"

echo '{"session_id":"trace-new-qoder-mcp","prompt":"用 New Qoder 查询 ECS 实例","hook_event_name":"UserPromptSubmit"}' | \
    python3 "$HOOKS_DIR/lib/prompt_handler.py" > /dev/null 2>&1 || true

echo '{"session_id":"trace-new-qoder-mcp","tool_name":"mcp_call","tool_use_id":"toolu_new_qoder_mcp_trace","tool_input":{"toolName":"mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud_CallCLI","arguments":{"command":"aliyun ecs DescribeInstances --RegionId cn-hangzhou"}},"hook_event_name":"PreToolUse"}' | \
    python3 "$HOOKS_DIR/lib/pre_handler.py" > /dev/null 2>&1 || true

echo '{"session_id":"trace-new-qoder-mcp","tool_name":"mcp_call","tool_use_id":"toolu_new_qoder_mcp_trace","tool_input":{"toolName":"mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud_CallCLI","arguments":{"command":"aliyun ecs DescribeInstances --RegionId cn-hangzhou"}},"tool_response":[{"type":"text","text":"{\"RequestId\":\"new-qoder-request\",\"Instances\":{\"Instance\":[]}}"}],"hook_event_name":"PostToolUse"}' | \
    python3 "$HOOKS_DIR/lib/post_handler.py" > /dev/null 2>&1 || true

traceFile10="$traceDir10/trace-new-qoder-mcp.jsonl"
if [ ! -f "$traceFile10" ]; then
    echo "FAIL: New Qoder mcp_call trace file not created"
    ls -la "$traceDir10"
    exit 1
fi

if ! grep -q '"event": "tool_start"' "$traceFile10" || ! grep -q '"event": "tool_end"' "$traceFile10"; then
    echo "FAIL: New Qoder mcp_call missing tool_start/tool_end"
    cat "$traceFile10"
    exit 1
fi

if ! grep -q '"tool_name": "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud_CallCLI"' "$traceFile10"; then
    echo "FAIL: New Qoder mcp_call did not unwrap the inner tool_name"
    cat "$traceFile10"
    exit 1
fi

if ! grep -q '"duration_ms":' "$traceFile10"; then
    echo "FAIL: New Qoder mcp_call did not pair pre/post duration"
    cat "$traceFile10"
    exit 1
fi

echo "PASS: New Qoder mcp_call records inner MCP tool"
unset QODER_WORK QODER_PRODUCT_ID
rm -rf "$traceDir10" "$stateDir10"

echo ""
echo "=== All trace tests passed ==="
