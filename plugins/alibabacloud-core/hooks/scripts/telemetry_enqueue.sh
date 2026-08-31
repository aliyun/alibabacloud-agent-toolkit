#!/bin/bash
# Shared telemetry enqueue helper.
#
# Replaces the old fire-and-forget ``( uvx ... @latest ... & ) ; disown``
# pattern.  Writes the event to a file-based queue and ensures the bounded
# Python worker daemon is running.  The daemon enforces concurrency limits,
# hard timeouts, and pinned tool versions — eliminating orphan processes
# and unbounded UV cache growth.
#
# Usage (from a hook script that already has ``args=()``):
#   source "$scriptDir/lib/telemetry_enqueue.sh"
#   telemetry_enqueue "${args[@]}"
#
# The function always returns 0 so the agent loop is never blocked.

telemetry_enqueue() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local worker_py="$script_dir/lib/telemetry_worker.py"

    if [ ! -f "$worker_py" ]; then
        return 0
    fi

    python3 -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath('$worker_py')))
from telemetry_worker import enqueue_and_start
args = sys.argv[1:]
enqueue_and_start(args)
" -- "$@" 2>/dev/null || true
}
