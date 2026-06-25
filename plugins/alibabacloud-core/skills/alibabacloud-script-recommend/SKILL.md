---
name: alibabacloud-script-recommend
description: >
  Generate Alibaba Cloud RunScript-compatible Python scripts from natural-language cloud
  operation requests. Use when the user asks to write Python code that calls Alibaba Cloud APIs,
  generate scripts for cloud resource management, or produce a validated script that should pass
  python-safety static validation.
triggers: >
  生成Python脚本, Python脚本, 阿里云脚本, RunScript, 云资源脚本,
  generate Python script, write Python code, cloud automation script,
  Python代码推荐, script recommend
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetApiDefinition,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListProducts"
---

# Alibaba Cloud Script Generator

Turn a natural-language Alibaba Cloud request into one RunScript-compatible Python script.
The script must use `await call_cli(...)`, assign the final value to `result`, and pass
python-safety validation before output. Do not execute the script unless the user asks.

## Scope Check Before You Start

This skill generates **single-purpose Python scripts for the RunScript sandbox**. If the
request is an **operational pattern** — batch ops, audits, rotations, scheduled cleanup —
invoke `alibabacloud-find-skills` first. Fall back only after `find-skills` returns no match.

## Workflow

1. Split the request into atomic cloud operations. For well-known products (ECS, VPC, SLB,
   RDS, OSS, CDN, RAM, STS, NAS, ESS, DNS, KMS, ACK/CS), choose APIs from model knowledge.
   Skip to step 4 if all APIs and parameters are known.

2. Search APIs only for operations whose API you do not know — not as a confirmation step
   for known APIs. Use `AlibabaCloud___SearchApis`. Keep to one parallel batch.

3. Read API definitions only for APIs whose parameters you are unsure about. Use
   `AlibabaCloud___GetApiDefinition` with product, action, and version.

4. Generate one Python script body following the Sandbox Contract and Script Patterns below.
   Prefer model knowledge over tool calls. When multiple tool calls are needed, batch them in
   parallel. Never repeat the same tool call with the same arguments.

5. Write to `/tmp/aliyun-runscript.py` and validate via remote API:

```bash
curl -X POST https://troubleshoot-server.example.com/api/script-recommend/validate \
  -H "Content-Type: application/json" \
  -d "{\"source\": $(cat /tmp/aliyun-runscript.py | jq -Rs .)}"
```

Response: `{"passed": true, "violations": []}` or `{"passed": false, "violations": [{"rule_id": "SEC-4001", "line": 1, "message": "..."}]}`.

6. If validation fails, fix ONLY the listed violations and re-validate. Maximum 3 rounds.
   If violations persist, show them to the user.

7. After validation passes, output only the Python script body — no Markdown fences,
   headings, or explanatory text unless the user asks.

## Sandbox Contract

All rules below are enforced by the remote validation API. See `references/runscript-contract.md`
for full definitions with examples.

| Category | Rule |
|----------|------|
| **Imports** | Do not write `import` statements. Sandbox pre-imports: `asyncio`, `collections`, `csv`, `dataclasses`, `datetime`, `decimal`, `enum`, `fractions`, `functools`, `itertools`, `json`, `math`, `re`, `statistics`, `string`, `time`, `typing`, `uuid`. |
| **API calls** | Use ONLY `call_cli(product, action, params, version=None, region=None)`. Pre-injected. No SDK clients, no HTTP requests, no subprocess. |
| **Output** | Assign final data to `result` (dict or list). No `print()`. |
| **Forbidden** | `os`, `subprocess`, `socket`, `requests`, `eval`, `exec`, `compile`, `getattr`, `setattr`, `globals`, `input`, `breakpoint`, `__import__`, dunder chains. |
| **Blocked APIs** | Credential-returning APIs (`ram.ListAccessKeys`, `sts.AssumeRole`, `kms.GetSecretValue`). CLI meta products (`configure`, `plugin`, `ossutil`). |
| **Other** | `time.sleep()` ≤ 30s. No comments. Write ops are fine — HITL handled by runtime. |

## Script Patterns

**Sequential** (dependent calls):

```python
vpc = await call_cli(product="Vpc", action="CreateVpc", params={"RegionId": region_id, "CidrBlock": "10.0.0.0/8"})
vsw = await call_cli(product="Vpc", action="CreateVSwitch", params={"VpcId": vpc["VpcId"], "CidrBlock": "10.0.0.0/16", "ZoneId": "cn-hangzhou-a"})
result = {"VpcId": vpc["VpcId"], "VSwitchId": vsw["VSwitchId"]}
```

**Pagination** (list tasks):

```python
items, page = [], 1
while True:
    resp = await call_cli(product="Ecs", action="DescribeInstances", params={"RegionId": region_id, "PageNumber": page, "PageSize": 100})
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
    call_cli(product="Ecs", action="DescribeInstances", params={"RegionId": rid})
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
