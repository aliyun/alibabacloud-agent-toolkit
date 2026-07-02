---
name: alibabacloud-script-recommend
description: >
  Generate Alibaba Cloud MCP Core RunScript-compatible Python scripts 
  from natural-language cloud operation requests. Use when the user explicitly asks for
  RunScript scripts, MCP Core scripts, or sandbox-compatible cloud automation code.
  For standard SDK Python code with imports and credentials, use `alibabacloud-sdk-usage` instead.
triggers: >
  RunScript, RunScript脚本, MCP脚本, 沙箱脚本,
  generate RunScript, MCP Core script, script recommend
license: Apache-2.0
metadata:
  domain: aliyun-runscript
  owner: sdk-team
  contact: sdk-team@alibabacloud.com
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetApiDefinition,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListProducts"
---

# Alibaba Cloud Script Generator

Turn a natural-language Alibaba Cloud request into one RunScript-compatible Python script.
The script must use `await call_cli(...)`, assign the final value to `result`, and pass
python-safety validation before output. Do not execute the script unless the user asks.

## Scope Check Before You Start

- **RunScript sandbox scripts** (this skill): generates `call_cli()`-based Python for the
  RunScript sandbox — no SDK imports, no credentials, no local execution.
- **SDK project code** → `alibabacloud-sdk-usage`: generates typed/generic SDK code with
  imports, credential providers, and dependency management for user projects.
- **Operational patterns** (batch ops, audits, rotations) → `alibabacloud-find-skills` first.

## Workflow

1. Split the request into atomic cloud operations. For each operation, verify the product,
   API name, version, and required parameters using MCP tools — do not guess.

1. Search APIs for operations whose API you are uncertain about. Use
   `AlibabaCloud___SearchApis` with a natural language description. Keep to one parallel batch.

1. Read API definitions to confirm exact parameter names and types. Use
   `AlibabaCloud___GetApiDefinition` with product, action, and version. Do not skip this
   step for unfamiliar APIs.

1. Generate one Python script body following the Sandbox Contract and Script Patterns below.
   Only whitelisted modules may be imported. When multiple tool calls are needed, batch them in parallel. Never repeat
   the same tool call with the same arguments.

1. Write to `/tmp/aliyun-runscript.py` and validate with the local sandbox checker
   (`<SKILL_DIR>/script/check_sandbox.py`):

   ```bash
   cat > /tmp/aliyun-runscript.py <<'PYEOF'
   <script body here>
   PYEOF
   python3 <SKILL_DIR>/script/check_sandbox.py /tmp/aliyun-runscript.py
   ```

1. If validation fails, read the `→ fix` suggestion for each violation, fix ONLY the listed
   issues, and re-validate. Maximum 3 rounds. If violations persist, show them to the user.

1. After validation passes, output only the Python script body — no Markdown fences,
   headings, or explanatory text unless the user asks.

## Sandbox Contract

All rules below are enforced by `script/check_sandbox.py` (local pre-check) and remote validation.
See `references/runscript-contract.md` for full definitions with examples.

| Category | Rule |
|----------|------|
| **Imports** | Only whitelisted modules may be imported: `asyncio`, `collections`, `csv`, `dataclasses`, `datetime`, `decimal`, `enum`, `fractions`, `functools`, `itertools`, `json`, `math`, `re`, `statistics`, `string`, `time`, `typing`, `uuid`. Do NOT import `random`, `os`, `subprocess`, `requests`, or any module not in this list. `call_cli` is pre-injected — do NOT import or define it. |
| **API calls** | Use ONLY `call_cli(product, version, action, params)`. Pre-injected. No SDK clients, no HTTP requests, no subprocess. Parameter values must be plain strings/numbers — do NOT pass `aliyun ...` CLI command strings as parameter values. |
| **Param values** | Parameter values must NOT contain lowercase `aliyun` (triggers BLK-4001). E.g. use `"1.28.3"` not `"1.28.3-aliyun.1"`. Query APIs to fetch exact values when unsure. |
| **Output** | Assign final data to `result` (dict or list). No `print()`. |
| **Forbidden** | `os`, `subprocess`, `socket`, `requests`, `eval`, `exec`, `compile`, `getattr`, `setattr`, `globals`, `input`, `breakpoint`, `__import__`, dunder chains. |
| **Blocked APIs** | Credential-returning APIs (`ram.ListAccessKeys`, `sts.AssumeRole`, `kms.GetSecretValue`). CLI meta products (`configure`, `plugin`, `ossutil`). |
| **Structure** | `call_cli` must be reachable from module-level execution. Do NOT wrap all calls in an uninvoked `async def` — either write `await call_cli(...)` at top level, or define a function and call it: `async def main(): ... \n await main()`. |
| **Numbers** | Do NOT use leading zeros in numeric literals (e.g., `01`, `010`). Write `1`, `10` instead. IP addresses and CIDR blocks must be strings: `"10.0.0.0/8"`, not bare numbers. |
| **Strings** | Use f-strings or `.format()` only with constant format strings. Do NOT build `call_cli` arguments dynamically via `str.format(variable)` or `%` formatting with non-constant args. |
| **Sleep** | `time.sleep()` argument MUST be ≤ 30. For longer waits, use a loop: `for _ in range(N): time.sleep(30)`. |
| **Output format** | Output ONLY Python code. Do NOT output prose, explanations, or markdown before or after the code. If you must add context, use Python comments inside the script — but avoid comments unless absolutely necessary. |
| **Other** | Write/delete/update ops execute directly — the RunScript runtime intercepts write operations and presents them to the user for approval (HITL) before execution. The script itself should not add confirmation prompts. |

## Script Patterns

**Sequential** (dependent calls):

```python
vpc = await call_cli(product="Vpc", version="2016-04-28", action="CreateVpc", params={"RegionId": region_id, "CidrBlock": "10.0.0.0/8"})
vsw = await call_cli(product="Vpc", version="2016-04-28", action="CreateVSwitch", params={"VpcId": vpc["VpcId"], "CidrBlock": "10.0.0.0/16", "ZoneId": "cn-hangzhou-a"})
result = {"VpcId": vpc["VpcId"], "VSwitchId": vsw["VSwitchId"]}
```

**Pagination** (list tasks):

```python
items, page = [], 1
while True:
    resp = await call_cli(product="Ecs", version="2014-05-26", action="DescribeInstances", params={"RegionId": region_id, "PageNumber": page, "PageSize": 100})
    batch = resp.get("Instances", {}).get("Instance", [])
    items.extend(batch)
    if len(batch) < 100:
        break
    page += 1
result = items
```

**Parallel** (independent calls):

```python
responses = await asyncio.gather(*[
    call_cli(product="Ecs", version="2014-05-26", action="DescribeInstances", params={"RegionId": rid})
    for rid in region_ids
], return_exceptions=True)
result = {rid: r if isinstance(r, dict) else {"error": str(r)} for rid, r in zip(region_ids, responses)}
```

## Guardrails

- Do not execute the generated script unless the user explicitly asks.
- Do not use any MCP server except the local `alibabacloud-core` server for API discovery.
- Do not generate boilerplate, redundant error handling, or unused imports.
- Always validate before output. Do not skip validation.
- If the request is ambiguous but not dangerous, use placeholders instead of asking.

## References

- `references/runscript-contract.md` — full rule definitions and additional patterns.
  Read only when validation fails repeatedly.
