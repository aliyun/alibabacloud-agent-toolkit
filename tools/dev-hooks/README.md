# Dev Hooks Tooling

Internal scripts for testing the canonical hook implementation living at
`plugins/alibabacloud-core/hooks/`. **Nothing in this directory is shipped to
end users** — these are dev-only fixtures, dry-run harness, and integration
tests.

| Script | Purpose |
|--------|---------|
| `verify-hooks.sh` | Asserts canonical layout exists; no plugin re-introduces a symlink; any non-core plugin holding a `hooks/` directory must be byte-identical to canonical. |
| `dry-run.sh [<stem> \| --all]` | Runs each fixture under `test-fixtures/claude-code/` through the canonical handlers and diffs against `test-fixtures/expected/`. |
| `test-trace.sh` | Integration test for the local JSONL trace flow (prompt → pre → post → stop, sanitization, truncation, opt-out, slash-skill detection). |
| `test-client-detection.sh` | Parity test for client-name resolution: the detection block must be identical across the four wrappers, bash and python must agree on the resolved client, `token_recorder` must parse the whole Qoder family, and the wrapper's state bucket must match the handler's `--client-name`. |
| `stress-test.sh` | Load test for the hook handlers. |

## How dev scripts find the canonical implementation

All scripts here resolve the canonical hooks scripts directory at runtime:

```bash
HOOKS_DIR="$(cd "$scriptDir/../../plugins/alibabacloud-core/hooks/scripts" && pwd)"
```

If you ever move or rename `alibabacloud-core`, update that single line in
`dry-run.sh`, `test-trace.sh` and `test-client-detection.sh`.

## Adding hooks to a new plugin

Per the canonical-source-of-truth convention (see
`plugins/alibabacloud-core/hooks/README.md`), do NOT hand-write hooks for a
new plugin. Copy the canonical directory:

```bash
cp -R plugins/alibabacloud-core/hooks plugins/<new-plugin>/hooks
bash tools/dev-hooks/verify-hooks.sh   # confirms no divergence
```

If divergence is intentional (e.g. a plugin needs a different MCP allowlist
in its own `hooks.json`), discuss before splitting — divergence makes
upstream fixes harder to roll out to every consumer.
