#!/bin/bash
# Verifies plugins/alibabacloud-core/hooks/ is a real directory holding the
# canonical hook implementation, and that no plugin re-introduces a symlink
# or maintains a divergent copy.
#
# Regression guard for the previous broken layout where plugins/*/hooks
# was a git symlink to ../../tools/hooks — Claude Code's marketplace did
# not preserve the cross-directory link, so end users got an empty hooks/.
#
# Returns: 0 on PASS, 1 on FAIL.
set -e

repoRoot="$(cd "$(dirname "$0")/../.." && pwd)"
canonical="$repoRoot/plugins/alibabacloud-core/hooks"

fail=0

# 1. Canonical hooks/ must be a real directory.
if [ -L "$canonical" ]; then
    echo "FAIL: $canonical must be a real directory, not a symlink"
    fail=1
elif [ ! -d "$canonical" ]; then
    echo "FAIL: $canonical does not exist"
    fail=1
fi

# 2. Required runtime files must be present.
required=(
    "hooks.json"
    "codex-hooks.json"
    "qoderwork-hooks.json"
    "scripts/pre-tool-trace.sh"
    "scripts/post-tool-trace.sh"
    "scripts/prompt-trace.sh"
    "scripts/stop-turn-increment.sh"
    "scripts/lib/pre_handler.py"
    "scripts/lib/post_handler.py"
    "scripts/lib/prompt_handler.py"
    "scripts/lib/stop_handler.py"
    "scripts/lib/sanitize.py"
    "scripts/lib/state.py"
    "scripts/lib/token_recorder.py"
    "scripts/lib/trace_writer.py"
)
for f in "${required[@]}"; do
    if [ ! -f "$canonical/$f" ]; then
        echo "FAIL: missing $canonical/$f"
        fail=1
    fi
done

# 3. No plugin under plugins/*/ may have a hooks symlink.
for plugin in "$repoRoot"/plugins/*/; do
    link="$plugin/hooks"
    if [ -L "$link" ]; then
        echo "FAIL: $(basename "$plugin")/hooks is a symlink — must be a real directory or absent"
        fail=1
    fi
done

# 4. Any non-core plugin with a hooks/ dir must be byte-identical to canonical.
for plugin in "$repoRoot"/plugins/*/; do
    name=$(basename "$plugin")
    [ "$name" = "alibabacloud-core" ] && continue
    if [ -d "$plugin/hooks" ]; then
        diffOut=$(diff -r -x __pycache__ -x '*.pyc' "$canonical" "$plugin/hooks" 2>&1 || true)
        if [ -n "$diffOut" ]; then
            echo "FAIL: $name/hooks diverged from canonical alibabacloud-core/hooks:"
            echo "$diffOut"
            fail=1
        fi
    fi
done

# 5. The VS Code hook manifest follows the same canonical-copy rule.
canonicalCopilot="$repoRoot/plugins/alibabacloud-core/com.github.copilot/hooks/hooks.json"
if [ -f "$canonicalCopilot" ]; then
    for plugin in "$repoRoot"/plugins/*/; do
        name=$(basename "$plugin")
        [ "$name" = "alibabacloud-core" ] && continue
        copilot="$plugin/com.github.copilot/hooks/hooks.json"
        if [ -d "$plugin/hooks" ] && [ ! -f "$copilot" ]; then
            echo "FAIL: $name ships hooks/ but no com.github.copilot/hooks/hooks.json — VS Code would load no hooks"
            fail=1
        elif [ -f "$copilot" ] && ! cmp -s "$canonicalCopilot" "$copilot"; then
            echo "FAIL: $name/com.github.copilot/hooks/hooks.json diverged from canonical alibabacloud-core copy"
            fail=1
        fi
    done
fi

if [ "$fail" -eq 0 ]; then
    echo "PASS: hooks layout OK (canonical: plugins/alibabacloud-core/hooks)"
fi
exit $fail
