# Telemetry Hooks Latest Uploader and Wrapped CallCLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore telemetry delivery, recognize Bash-wrapped MCP Core `CallCLI` operations consistently, and make the spec-ops Qoder manifest loadable.

**Architecture:** Keep `plugins/alibabacloud-core/hooks/` as the canonical implementation and copy it byte-for-byte to spec-ops and ecs-ops after tests pass. Replace the broken pinned virtualenv uploader with `uvx alibabacloud.mcp-proxy@latest plugin-telemetry` while retaining the bounded worker. Put Qoder wrapper and Bash-wrapped CallCLI normalization in one shared Python module imported by both pre and post handlers.

**Tech Stack:** Python 3 stdlib, Bash hook harnesses, JSON plugin manifests, `unittest`, `uvx`.

---

### Task 1: Restore the latest MCP proxy uploader command

**Files:**
- Modify: `tests/test_telemetry_bounded_upload.py`
- Modify: `plugins/alibabacloud-core/hooks/scripts/lib/telemetry_worker.py`
- Modify: `plugins/alibabacloud-core/hooks/README.md`

- [ ] **Step 1: Replace the pinned-command tests with the required latest command**

```python
def test_get_upload_cmd_uses_latest_uvx(self):
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.dict(os.environ, {}, clear=True):
            cmd = telemetry_worker._get_upload_cmd(tmp)
    self.assertEqual(cmd, [
        "uvx", "alibabacloud.mcp-proxy@latest", "plugin-telemetry",
    ])

def test_worker_has_no_pinned_version_or_venv_bootstrap(self):
    source = Path(telemetry_worker.__file__).read_text(encoding="utf-8")
    self.assertNotIn("MCP_PROXY_PINNED_VERSION", source)
    self.assertNotIn("_ensure_venv", source)
```

- [ ] **Step 2: Run the focused tests and verify they fail on the current pinned command**

Run: `python3 -m unittest tests.test_telemetry_bounded_upload.TestUploadCommand -v`

Expected: FAIL because `_get_upload_cmd` returns `uvx --from alibabacloud.mcp-proxy==0.5.1 plugin-telemetry` or a venv executable.

- [ ] **Step 3: Remove pinned-version and venv installation logic**

```python
MCP_PROXY_UVX_SPEC = "alibabacloud.mcp-proxy@latest"

def _get_upload_cmd(state_dir):
    override = os.environ.get("ALIBABACLOUD_TELEMETRY_UPLOADER")
    if override:
        return override.split()
    return ["uvx", MCP_PROXY_UVX_SPEC, "plugin-telemetry"]
```

Delete `MCP_PROXY_PINNED_VERSION`, `MCP_PROXY_PIN`, `_ensure_venv`, and fixed-venv selection. Do not change queue locking, retries, timeout, or process-group cleanup.

- [ ] **Step 4: Update hook documentation**

Replace the pinned package and persistent `.venv/bin/plugin-telemetry` instructions with `uvx alibabacloud.mcp-proxy@latest plugin-telemetry`. Retain documentation for `ALIBABACLOUD_TELEMETRY_UPLOADER`, queue bounds, retry limits, and cleanup.

- [ ] **Step 5: Run the uploader suite**

Run: `python3 -m unittest tests.test_telemetry_bounded_upload -v`

Expected: PASS.

### Task 2: Normalize Bash-wrapped CallCLI in one shared module

**Files:**
- Create: `plugins/alibabacloud-core/hooks/scripts/lib/tool_normalization.py`
- Create: `tests/test_telemetry_tool_normalization.py`
- Modify: `plugins/alibabacloud-core/hooks/scripts/lib/pre_handler.py`
- Modify: `plugins/alibabacloud-core/hooks/scripts/lib/post_handler.py`

- [ ] **Step 1: Add failing normalization tests using observed QwenWork command forms**

```python
def test_normalizes_mcpx_callcli_json_argument(self):
    command = (
        "cd /tmp/plugin && uv run --python 3.11 scripts/mcpx.py "
        "call CallCLI '{\"command\":\"aliyun ecs DescribeInstances "
        "--RegionId cn-hangzhou\"}' 2>&1 | tail -30"
    )
    self.assertEqual(
        normalization.normalize_tool_call("Bash", {"command": command}),
        ("AlibabaCloud___CallCLI", {
            "command": "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        }),
    )

def test_does_not_match_mentions_without_valid_callcli_payload(self):
    for command in (
        "echo mcpx.py CallCLI aliyun",
        "python scripts/mcpx.py schema CallCLI",
        "python scripts/not-mcpx.py call CallCLI '{\"command\":\"aliyun ecs DescribeInstances\"}'",
    ):
        self.assertEqual(
            normalization.normalize_tool_call("Bash", {"command": command}),
            ("Bash", {"command": command}),
        )
```

Also test Qoder `qw_mcp_call` compatibility, options before `call`, piped JSON input, malformed JSON, non-string input, and credential-bearing commands.

- [ ] **Step 2: Run the new suite and verify import/behavior failure**

Run: `python3 -m unittest tests.test_telemetry_tool_normalization -v`

Expected: FAIL because `tool_normalization.py` does not exist.

- [ ] **Step 3: Implement non-evaluating shared parsing**

```python
import json
import os
import shlex

QODERWORK_MCP_WRAPPERS = ("qw_mcp_call", "qw_mcp_get", "CallMcpTool")
NORMALIZED_CALLCLI_TOOL = "AlibabaCloud___CallCLI"

def normalize_tool_call(tool_name, tool_input):
    qoder = _unwrap_qoder(tool_name, tool_input)
    if qoder != (tool_name, tool_input):
        return qoder
    if tool_name != "Bash" or not isinstance(tool_input, dict):
        return tool_name, tool_input
    command = tool_input.get("command")
    inner = extract_wrapped_callcli(command) if isinstance(command, str) else None
    return (NORMALIZED_CALLCLI_TOOL, {"command": inner}) if inner else (tool_name, tool_input)
```

Use `shlex.split` only for tokenization. Require a token whose basename is exactly `mcpx.py`, a later `call` followed by `CallCLI`, a JSON object token containing a string `command`, and an actual word-bounded `aliyun` invocation. Never execute or expand shell text.

- [ ] **Step 4: Import the same normalizer from pre and post handlers**

```python
from tool_normalization import normalize_tool_call
```

Remove the duplicated wrapper constants/functions. Keep start-marker keys based on the normalized tool name in both handlers.

- [ ] **Step 5: Prove pre/post classification and sanitization**

Add assertions that `pre_handler.is_ours_tool` accepts the normalized tool; `post_handler.classify_with_reason` produces `mcp_tool_use`, `AlibabaCloud___CallCLI`, and sanitized `cli_command`; false positives remain `bash-not-aliyun`.

Run: `python3 -m unittest tests.test_telemetry_tool_normalization -v`

Expected: PASS.

### Task 3: Validate and fix Qoder agent paths

**Files:**
- Modify: `tools/test_validate.py`
- Modify: `tools/validate.py`
- Modify: `plugins/alibabacloud-spec-ops/.qoder-plugin/plugin.json`

- [ ] **Step 1: Add failing Qoder-specific validator tests**

```python
def test_qoder_agents_accept_explicit_markdown_files(self):
    self.write("agents/reviewer.md", "---\nname: reviewer\n---\n")
    self.write(".qoder-plugin/plugin.json", {"agents": ["./agents/reviewer.md"]})
    self.assertEqual([], self.errors_from("validate_qoder_manifest"))

def test_qoder_agents_reject_directory(self):
    (self.plugin_dir / "agents").mkdir(exist_ok=True)
    self.write(".qoder-plugin/plugin.json", {"agents": "./agents/"})
    self.assertTrue(any("must end with .md" in error for error in self.errors_from("validate_qoder_manifest")))
```

Add cases for a missing file, absolute path, `../` escape, and non-string entries.

- [ ] **Step 2: Run the validator tests and verify the missing-validator failure**

Run: `python3 -m unittest tools.test_validate.QoderManifestTests -v`

Expected: FAIL because `validate_qoder_manifest` does not exist.

- [ ] **Step 3: Implement Qoder-only path validation**

```python
def validate_qoder_manifest(plugin_dir: Path) -> None:
    path = plugin_dir / ".qoder-plugin/plugin.json"
    if not path.exists():
        return
    data = validate_json(path, ["name"])
    if data is None or "agents" not in data:
        return
    raw = data["agents"]
    entries = raw if isinstance(raw, list) else [raw]
    for entry in entries:
        if not isinstance(entry, str):
            error(f"'agents' entries must be strings in {rel(path)}")
            continue
        if not entry.startswith("./") or Path(entry).is_absolute():
            error(f"Qoder agent path must be plugin-relative in {rel(path)}: {entry}")
            continue
        if Path(entry).suffix.lower() != ".md":
            error(f"Qoder agent path must end with .md in {rel(path)}: {entry}")
            continue
        resolved = (plugin_dir / entry).resolve()
        root = plugin_dir.resolve()
        if not resolved.is_relative_to(root):
            error(f"Qoder agent path escapes plugin root in {rel(path)}: {entry}")
        elif not resolved.is_file():
            error(f"Qoder agent path is not an existing file in {rel(path)}: {entry}")
```

Call it from `validate_plugin`. Its rules must not apply to `.claude-plugin` or `.codex-plugin`.

- [ ] **Step 4: Change only the spec-ops Qoder manifest**

```json
"agents": [
  "./agents/code-quality-reviewer.md",
  "./agents/spec-reviewer.md"
]
```

- [ ] **Step 5: Run focused and repository validation**

Run: `python3 -m unittest tools.test_validate.QoderManifestTests -v`

Expected: PASS.

Run: `python3 tools/validate.py --plugin alibabacloud-spec-ops`

Expected: `All validations passed.`

### Task 4: Synchronize all hook-shipping plugins and verify end to end

**Files:**
- Modify: `plugins/alibabacloud-spec-ops/hooks/**`
- Modify: `plugins/alibabacloud-ecs-ops/hooks/**`

- [ ] **Step 1: Copy the canonical tree to both consumers**

Run:

```bash
rsync -a --delete plugins/alibabacloud-core/hooks/ plugins/alibabacloud-spec-ops/hooks/
rsync -a --delete plugins/alibabacloud-core/hooks/ plugins/alibabacloud-ecs-ops/hooks/
```

- [ ] **Step 2: Verify byte identity**

Run: `bash tools/dev-hooks/verify-hooks.sh`

Expected: `PASS: hooks layout OK`.

- [ ] **Step 3: Run hook behavior suites**

Run:

```bash
bash tools/dev-hooks/dry-run.sh --all
bash tools/dev-hooks/test-client-detection.sh
bash tools/dev-hooks/test-trace.sh
bash tools/dev-hooks/test-trace-codex.sh
python3 -m unittest tests.test_telemetry_bounded_upload tests.test_telemetry_tool_normalization tools.test_validate -v
python3 tools/validate.py
```

Expected: every command exits 0; all tests and validations pass.

- [ ] **Step 4: Confirm scope and inspect the final diff**

Run: `git status --short && git diff --check && git diff --stat`

Expected: only planned source, tests, manifests, docs, and synchronized hook copies are changed; `plugins/alibabacloud-core.zip` remains untracked and untouched.

- [ ] **Step 5: Commit the implementation**

```bash
git add tests tools plugins/alibabacloud-core/hooks plugins/alibabacloud-spec-ops/hooks plugins/alibabacloud-ecs-ops/hooks plugins/alibabacloud-spec-ops/.qoder-plugin/plugin.json docs/superpowers/plans/2026-09-15-telemetry-hooks-latest-callcli.md
git commit -m "fix: restore plugin telemetry delivery"
```
