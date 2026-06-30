---
name: mcp-core-best-practices
description: >
  Shared reference for using Alibaba Cloud OpenAPI MCP Server Core effectively.
  Covers tool usage patterns, API exploration workflow, CLI command generation,
  scripted execution, async task polling, Infrastructure as Code (RunIaC),
  cross-account access, and safety policy
  configuration. Referenced by other alibabacloud-core skills as the canonical
  guide for MCP Core interactions.
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___RunIaC,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetPresignedUrl,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetApiDefinition,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListProductRegions,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GenerateCLICommand,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListProducts,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchDocuments,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetDocument,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetDocumentTree,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GrepDocuments,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___RunScript,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetTask"
---

# Alibaba Cloud MCP Core Best Practices

This skill documents the canonical patterns for using the `alibabacloud-core` MCP
server — the generalized OpenAPI MCP Server Core that covers all Alibaba Cloud
APIs without requiring pre-selection of specific operations.

## Available Tools

| Tool | Purpose |
|------|---------|
| `AlibabaCloud___SearchApis` | Natural language search for APIs matching a requirement |
| `AlibabaCloud___CallCLI` | Execute a single CLI command remotely |
| `AlibabaCloud___GetApiDefinition` | Get full API definition (params, response, errors) by product/version/name |
| `AlibabaCloud___ListApis` | List all APIs for a product, optionally filtered |
| `AlibabaCloud___ListProductRegions` | List regions where a product is available |
| `AlibabaCloud___GenerateCLICommand` | Generate a CLI command from API definition + parameters |
| `AlibabaCloud___ListProducts` | List all Alibaba Cloud products |
| `AlibabaCloud___SearchDocuments` | Search Alibaba Cloud official documentation by keyword, with optional product/language/site filters |
| `AlibabaCloud___GetDocument` | Get full Markdown content of a document by `doc_id` (preferred) or URL |
| `AlibabaCloud___GetDocumentTree` | Browse a product's document directory tree to discover available docs |
| `AlibabaCloud___GrepDocuments` | Search within a specific product's documents by keyword pattern |
| `AlibabaCloud___RunScript` | Start a restricted Python task with structured Alibaba Cloud OpenAPI access |
| `AlibabaCloud___GetTask` | Long-poll a `RunScript` task until approval, execution, or failure reaches a terminal state |
| `AlibabaCloud___RunIaC` | Run Terraform / IaC (`action`=plan/apply/destroy) to provision or tear down a multi-resource stack; plan-before-apply, sync or async, HITL approval |
| `AlibabaCloud___GetPresignedUrl` | Get a time-limited OSS presigned URL (default upload) + `presignToken` to feed `RunIaC`; no credentials exposed |

## Standard Workflow

### 1. API Discovery

When the target API is unknown, use `AlibabaCloud___SearchApis` with a natural
language description of the requirement. Each query should be granular enough to
map to a single API call.

For known products, use `AlibabaCloud___ListApis` with a filter keyword to browse
available operations.

### 2. API Inspection

Once the target API is identified, use `AlibabaCloud___GetApiDefinition` to
retrieve the full definition including:

- Required and optional parameters
- Request/response schemas
- Authentication requirements
- Error codes

### 3. Command Generation

Use `AlibabaCloud___GenerateCLICommand` to produce a correct CLI command from the
API definition and user-provided parameters. This avoids manual CLI syntax errors.

### 4. Execution Choice

Use `AlibabaCloud___CallCLI` for one known `aliyun ...` command when no later
call depends on its response. Verified example:
`AlibabaCloud___CallCLI(command="aliyun ecs DescribeRegions --region cn-hangzhou")`.

Use `AlibabaCloud___RunScript` when the answer needs structured OpenAPI
`call_cli(...)`: pagination, List-to-Describe enrichment, cross-resource
comparison, multi-region/multi-product collection, permission checks, OSS
body/bytes handling, response-driven follow-up calls, or custom result shaping.
Example: fetch identity, list resources, and perform follow-up Describe/Get
calls in one script instead of separate tool round-trips.

Do not split one user task across multiple `RunScript` submissions just to
inspect intermediate data. Put discovery, pagination, filtering, and follow-up
Describe/Get calls in one self-contained script and return via `result`.

### 5. Single-Call Execution

Use `AlibabaCloud___CallCLI` to execute the generated command. Key constraints:

- Commands must start with `aliyun`
- No shell pipes, redirections, or operators
- No shell variables or command substitution
- No local file path references (MCP server is remote)

### 6. Scripted Multi-Call Execution

`AlibabaCloud___RunScript` starts a sandboxed Python task and waits up to 20
seconds. It may return `result` directly; otherwise use the returned `processID`
and `nextAction` with `AlibabaCloud___GetTask`. The script's OpenAPI access goes
through injected `call_cli()` only:

```python
identity = await call_cli(product='Sts', action='GetCallerIdentity',
                          params={}, version='2015-04-01')
result = {'has_account_id': 'AccountId' in identity}
```

RunScript essentials:

- `call_cli()` is structured OpenAPI, not CLI text. Never pass `aliyun ...`.
- Before unfamiliar APIs, OSS APIs, body/object params, array params, or
  parameter retries, call `AlibabaCloud___GetApiDefinition` separately.
- Top-level `params` keys must match OpenMeta `parameters[].name`. RPC APIs
  often use `RegionId`; OSS APIs often use `bucket`, `max-keys`, `x-oss-acl`,
  or `body`.
- Arrays/objects stay as Python lists/dicts unless the API parameter itself is
  JSON text.
- For OSS object bytes, `PutObject` accepts bytes in `params['body']` and
  `GetObject` returns bytes in `Body`.
- `version`, `region`, and `endpoint` are optional; still pass API region fields
  such as `RegionId` when the API defines them.
- Assign final output to `result`. Do not pass credentials, profiles, shell
  flags, or host file paths. Use `/tmp` only for small sandbox scratch files.
- The script must have a reachable module-level `call_cli()`; pure Python
  payloads fail validation.
- Do not write `import` or comments. Safe modules such as `asyncio`, `json`,
  `math`, `re`, `time`, and `uuid` are pre-imported.
- Do not use sensitive names such as `eval`, `exec`, `compile`, `__import__`,
  `globals`, `locals`, `getattr`, `setattr`, or `vars`; do not use private or
  dunder attributes, dynamic `.format()` tricks, subprocesses, or network code.
- Do not target CLI meta products such as `configure`, `plugin`, `ossutil`,
  `ossutil64`, `upgrade`, or `mock`. Some OSS APIs are unsupported; if the
  validator returns `UnsupportedOssApi`, choose a supported OSS OpenAPI action
  or another tool.
- Discover IDs inside the script, paginate every list call, and never sample or
  truncate complete inventory/compliance answers.
- List APIs are not enough for attribute checks. Follow List with Describe/Get
  and feature-specific APIs for every resource.
- Verify response shape before saying "0 found"; list responses often wrap arrays
  twice, e.g. `{"Instances":{"Instance":[...]}}`.
- Use `asyncio.gather(..., return_exceptions=True)` for parallel calls. Treat
  expected NotFound as "not configured" for optional features.
- Do exact aggregation in Python; return raw fields for judgment calls such as
  "misconfigured" or "risky".

OSS object read/write example (use a user-approved temporary bucket/key):

```python
bucket = '<approved-bucket>'
key = 'run-script-probe/example.txt'
content = b'hello-from-run-script\n'
put = await call_cli(product='Oss', action='PutObject',
                     params={'bucket': bucket, 'key': key, 'body': content},
                     version='2019-05-17', region='cn-hangzhou')
got = await call_cli(product='Oss', action='GetObject',
                     params={'bucket': bucket, 'key': key},
                     version='2019-05-17', region='cn-hangzhou')
result = {'put_ok': isinstance(put, dict), 'round_trip_ok': got.get('Body') == content}
```

### 7. RunScript Task Polling

After `AlibabaCloud___RunScript`, inspect `nextAction`:

| `nextAction` | Meaning | Agent action |
|--------------|---------|--------------|
| `None` | Task succeeded | Use `result` |
| `CallGetTask` | Initial call is not terminal | Call `AlibabaCloud___GetTask` with the same `processID` |
| `CallGetTaskAgain` | Poll timed out and task is still not terminal | Call `AlibabaCloud___GetTask` again with the same `processID` |
| `Stop` | Validation failed, approval rejected/expired, task expired, or process missing | Stop; do not retry automatically |
| `InspectError` | Execution failed | Inspect `error`; failed OpenAPI calls appear in `error.failedCall` when available |

`AlibabaCloud___GetTask` parameters:

- `processID`: required, from `RunScript`.
- `waitTimeoutSeconds`: optional, capped at 30 seconds by the server. Use `0`
  for an immediate status check.
- `pollIntervalSeconds`: optional polling interval, between 1 and 10 seconds.

Human approval handling:

- `ApprovalPending` with `approvalReqId` means external approval is required.
  Ask the user to complete approval or rejection out of band, then call
  `AlibabaCloud___GetTask` again with the same `processID`.
- Do not call `AlibabaCloud___RunScript` again while waiting for approval or
  execution; that creates a new process instead of continuing the current one.
- `ApprovalRejected` and `ApprovalExpired` are terminal. Stop and report the
  approval result.

### 8. Cross-Account Execution

**IMPORTANT**: For any operation involving member accounts, cross-account queries,
or Resource Directory account resolution, you MUST first load the
`multi-account-query` skill (invoke it via the Skill tool) before proceeding.
That skill contains the complete workflow for alias-to-UID resolution, pagination
handling, and proper use of `x_assume_account_id`. Do not attempt cross-account
operations without reading it first.

For Resource Directory member accounts, pass additional parameters to
`AlibabaCloud___CallCLI`:

| Parameter | Usage |
|-----------|-------|
| `x_assume_account_id` | Target member account UID |
| `x_assume_role_name` | Custom role name (default: `ResourceDirectoryAccountAccessRole`) |
| `x_assume_role_arn` | Full role ARN (highest priority) |

Priority: `x_assume_role_arn` > `x_assume_account_id` + `x_assume_role_name` >
default configuration.

## Infrastructure as Code (RunIaC)

`AlibabaCloud___RunIaC` runs Terraform/IaC so a single call can stand up several
interdependent resources, then later tear them down. It takes `action`
(`plan` default / `apply` / `destroy`), `code` (only on `plan`) or `presignToken`,
and `previousProcessId`. Prefer it over `CallCLI` whenever the request is more than
a one-off read or single mutation.

### When to use RunIaC vs CallCLI

| Use `RunIaC` | Use `CallCLI` |
|--------------|---------------|
| Multiple resources at once (e.g. VPC + vSwitch + ECS) | A single, one-shot query or describe |
| Resources have dependencies / ordering | A stateless mutation that needs no rollback |
| You want a destroyable, tracked stack | No lifecycle to manage afterward |
| Repeatable, idempotent provisioning | Quick fact lookup or `--region` check |

If you find yourself chaining several `CallCLI` create calls and worrying about
cleanup, switch to `RunIaC`.

### Plan, apply, destroy

1. **Plan**: send `action=plan` with `code` (or `presignToken`). It returns a
   `processId` plus the diff and `status=Planned`. Surface the diff to the user.
2. **Apply**: send `action=apply` with `previousProcessId` (no `code`) to run the
   exact plan that was reviewed; template and state stay identical. If the plan has
   changes, the call may return `ApprovalPending` + `approvalReqId` — wait for
   approval, do not retry. **Remind the user to review the plan first** when
   resources involve cost, data deletion, or security-sensitive config.
3. **Destroy**: send `action=destroy` with `previousProcessId` to release the
   resources from that plan.

### Async execution + polling

`RunIaC` returns a `processId` immediately and runs the task in the background.
Use `nextAction` to drive follow-up: `CallGetTask` / `CallGetTaskAgain` means poll
`AlibabaCloud___GetTask` with that `processID` until a terminal state. Plan rests
at `Planned`; apply ends at `Succeeded` (or `Failed`). Read the structured outputs
from the apply / `GetTask` result — do not block waiting on the first call.

### Tearing down

To release resources, call `RunIaC` with `action=destroy` and the
`previousProcessId` of the plan that created them.

### Long-running / timeout handling

For complex or slow code, keep polling `AlibabaCloud___GetTask` by `processID`
until terminal instead of one long blocking wait; do not loop aggressively (a
few-second cadence is enough).

### Reading structured outputs

Both plan and apply emit structured output. Read the plan to confirm the resource
set before applying, and read the apply / `GetTask` result outputs (e.g. region,
zone, instance name, public IP) to report results — do not guess at IDs/addresses;
pull them from the returned outputs.

## CLI Command Constraints

When using `AlibabaCloud___CallCLI`, the following are NOT supported:

- Bash/zsh pipes (`|`) or shell operators
- `grep`, `awk`, `sed`, or other shell tools
- Shell redirection (`>`, `>>`, `<`)
- Command substitution (`$()`)
- Shell variables or environment variables
- Local file paths (`file://`, `fileb://`)

For commands that need local file access (e.g., `ossutil cp`), use the Bash tool
directly instead of MCP.

## File Operations

The MCP server is remote, so `CallCLI` rejects local paths (`file://`, `fileb://`)
and tools never see your filesystem. To move bytes in — IaC bundles or large
script inputs — stage them in OSS with `AlibabaCloud___GetPresignedUrl`.
It defaults to upload (`PUT`) against a platform-managed bucket and returns a
`presignToken`; the URL carries its own auth, so credentials are never embedded in
commands. Download (`GET`) is only for the user's own OSS bucket.

Typical flow:

1. Call `GetPresignedUrl` (default upload) to get an upload URL + `presignToken`.
2. `PUT` the local bundle to that URL.
3. Pass the `presignToken` to `RunIaC` instead of inlining `code`.

## Region Handling

- Use `AlibabaCloud___ListProductRegions` to check product availability in a
  specific region before making calls.
- Always include `--region` when operating across regions or when the default
  region may not match the target.

## Documentation Access

- `AlibabaCloud___SearchDocuments`: Find relevant docs by keyword. Supports
  `product`, `limit`, `website`, and `language` filters.
- `AlibabaCloud___GetDocument`: Read full content by `doc_id` (preferred) or
  URL. Supports `max_length` to cap response size, plus `website` and `language`.
- `AlibabaCloud___GetDocumentTree`: Browse a product's doc tree by alias
  (e.g. `ecs`, `oss`). Use to discover what documents exist, then fetch via
  `GetDocument`.
- `AlibabaCloud___GrepDocuments`: Search within a specific product's docs by
  keyword pattern (matches title/description). Useful when you know the product
  but not the exact document name.

Use these to verify behavior, understand quotas, or find configuration guides
that are not captured in API definitions alone.

## Error Handling Patterns

- **InvalidParameter**: Check parameter names and values against
  `GetApiDefinition` output.
- **AccessDenied / Forbidden**: Verify RAM permissions for the current identity.
- **Throttling**: Retry with backoff; do not loop aggressively.
- **RegionNotSupported**: Use `ListProductRegions` to find valid regions.
- **RunIaC apply fails**: Read the returned `status` and result; fix the HCL, plan
  again, and apply the new `previousProcessId`. To roll back, `action=destroy` with
  the prior `previousProcessId` rather than chaining manual `CallCLI` cleanup.
- **RunIaC long-running timeout**: Poll `AlibabaCloud___GetTask` by `processID`
  until terminal; do not retry the whole apply (re-bind via `previousProcessId`).
- **RunScript ValidationFailed**: Fix unsafe or invalid Python authoring patterns
  before submitting a new `RunScript`.
- **RunScript BLK-4002**: Add a reachable module-level `call_cli()`; pure Python
  scripts are rejected.
- **RunScript Failed / InspectError**: Inspect `error`; if the script needs
  correction, submit one new corrected `RunScript`.

## Skill Discovery (Fallback)

The in-plugin skills (`alibabacloud-sdk-usage`, `alibabacloud-cli-guidance`,
`alibabacloud-terraform-code-generation`, `multi-account-query`) cover SDK
codegen, CLI guidance, Terraform HCL, and cross-account queries. They do not cover
purpose-built operational solutions, less common products, or end-to-end
workflows that the Alibaba Cloud team publishes as standalone skills.

When the user's request falls outside the in-plugin coverage, defer to
`alibabacloud-find-skills` instead of forcing a generic SDK or CLI synthesis.

### Invoke `alibabacloud-find-skills` when ANY of the following is true

- The user explicitly asks to search, browse, install, or discover an
  Alibaba Cloud skill (e.g., "有没有 RDS 备份的 skill", "find an OSS skill",
  "帮我装一个阿里云 skill")
- The request describes an **operational solution pattern** likely already
  packaged — batch operations, automated audits, key/credential rotation,
  scheduled cleanup, disaster recovery setup, incident response runbooks
- The target product or feature is not covered by any in-plugin skill —
  examples: MaxCompute, PAI, Quick BI, Function Compute lifecycle ops,
  CloudMonitor automation, custom service-linked workflows
- A first-cut SDK/CLI synthesis would require **3+ chained API calls plus
  retry/pagination/error semantics** — a packaged skill usually captures the
  pattern more reliably than ad-hoc code

### Do NOT invoke `alibabacloud-find-skills` when

- The task is a single `CallCLI` / `GetApiDefinition` / one-shot SDK call
  (use the in-plugin skills directly)
- The user explicitly wants generated SDK code, raw CLI commands, or
  Terraform HCL (those map cleanly to in-plugin skills)
- The same workflow already triggered `find-skills` earlier in this
  conversation and returned no match — don't re-search the same intent

### Handoff pattern

1. Briefly tell the user you're searching the official catalog for a
   purpose-built skill
2. Invoke `alibabacloud-find-skills` via the Skill tool — it handles
   search, presentation, and install in its own workflow
3. After install, follow the installed skill's instructions to complete
   the request; do not fall back to ad-hoc SDK/CLI synthesis once a
   matching skill is loaded

## Integration Guidance

When building stable workflows:

1. Use `SearchApis` to identify the correct API during development.
2. Use `GenerateCLICommand` to produce validated commands.
3. Use `RunScript` for workflows that require complete pagination,
   List-to-Describe enrichment, or multi-call analysis.
4. Capture the stable command or script patterns into a dedicated Skill.
5. Configure a safety policy to restrict the MCP connection to only the commands
   the Skill needs (for production use).

This progression — explore, validate, codify, restrict — ensures both flexibility
during development and safety in production.
