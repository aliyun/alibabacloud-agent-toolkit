#!/usr/bin/env bash
# Validate that README.md declares support for qoder and qoderwork series agents.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
README="$REPO_ROOT/README.md"

fail() { echo "FAIL: $1" >&2; exit 1; }

[ -f "$README" ] || fail "README.md not found"

# Check Current Status section mentions qoder and qoderwork
grep -q "Qoder" "$README" || fail "README missing 'Qoder'"
grep -q "QoderWork" "$README" || fail "README missing 'QoderWork'"

# Check one-command install lists both Qoder and QoderWork
grep -q "Qoder, QoderWork" "$README" || fail "README missing Qoder+QoderWork in install client list"

# Check clientName enum includes qoder and qoderwork (English)
grep -q '`qoder`' "$README" || fail "README missing 'qoder' in clientName enum"
grep -q '`qoderwork`' "$README" || fail "README missing 'qoderwork' in clientName enum"

# Check manual install section has Qoder heading
grep -q '#### Qoder' "$README" || fail "README missing Qoder manual install section"

echo "PASS: README declares qoder + qoderwork series agent support"
