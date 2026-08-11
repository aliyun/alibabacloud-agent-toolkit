# Static Checks

Use the script instead of copying shell snippets:

```bash
scripts/static_checks.sh provider <target-dir>
scripts/static_checks.sh deprecated <target-dir>
scripts/static_checks.sh all <target-dir>
```

Rules:

- Provider check must emit `OK_VERSION`, `OK_CFG_SOURCE`, and `OK_REGION_VAR`.
- Deprecated check must emit only `OK:` lines. Any `DEPRECATED:` line must be
  fixed using `references/deprecated-fields.md`, then the script must be rerun.
- Execute from the skill repository root so relative reference paths resolve.
