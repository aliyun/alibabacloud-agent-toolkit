---
name: alibabacloud-suggest-cli
description: >
  Suggest Alibaba Cloud `aliyun` CLI command strings from natural-language cloud operation
  requests, ready to pass as the `command` argument of the MCP `CallCLI` tool. Use when the user
  asks for the CLI command to do something, wants to manage cloud resources via aliyun, or asks
  "how do I do X with the aliyun CLI". Use `unifiedCli` from GenerateCLICommand (fallback to
  `cli` when empty) verbatim as the CallCLI command — no manual rewriting. Passes check_cli.py
  static validation. Suggest only — do not execute unless asked.
triggers: >
  推荐CLI命令, 生成CLI命令, 给我命令行, 用CLI怎么做, aliyun命令怎么写, CLI怎么写,
  命令行怎么做, suggest cli, suggest CLI command, give me the aliyun command,
  what's the cli command, how do I ... with aliyun, generate aliyun command, CLI command for
license: Apache-2.0
metadata:
  domain: aliyun-cli
  owner: sdk-team
  contact: sdk-team@alibabacloud.com
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetApiDefinition,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GenerateCLICommand,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListProducts"
---

# Alibaba Cloud CLI Command Suggester

Turn a natural-language Alibaba Cloud request into one or more `aliyun` CLI command strings,
each ready to be passed as the `command` argument of the MCP **`CallCLI`** tool. After calling
`GenerateCLICommand`, take the returned **`unifiedCli`** field verbatim; if `unifiedCli` is empty,
fall back to **`cli`**. Do not manually rewrite either field. Commands must satisfy CallCLI's
constraints, must pass `check_cli.py` validation before output, and are **suggested only** —
do not run them unless the user explicitly asks.

## Scope Check Before You Start

- **CLI command suggestions** (this skill): produce `aliyun ...` command strings (from
  GenerateCLICommand) for the MCP `CallCLI` tool. No execution, no SDK code.
- **CLI syntax & troubleshooting reference** → `alibabacloud-cli-guidance`: the knowledge base
  for plugin vs built-in routing, `--biz-` naming, auth, install, and error fixes. Read it when
  you need rules; this skill is the *generation + validation* loop on top of those rules.

## Workflow

1. Split the request into atomic cloud operations. For each, verify the product, API/action
   name, version, and required parameters using MCP tools — do not guess.

2. Search APIs for operations whose action you are unsure about. Use
   `AlibabaCloud___SearchApis` with a natural-language description. Keep to one parallel batch.

3. Read API definitions to confirm exact parameter names, types, and which are required. Use
   `AlibabaCloud___GetApiDefinition` with product, action, and version. Do not skip this step
   for unfamiliar APIs.

4. Build `jsonApiParameters` from the API definition before generating the command. Prefer
   user-provided values. For missing values needed to make a useful suggestion, create reasonable
   mock values from the parameter structure returned by `GetApiDefinition`:

   - Use exact OpenMeta parameter names; never invent names from CLI flags or memory.
   - Include parameters marked required, plus small harmless shaping parameters for list/query APIs
     when useful (for example `PageSize: 10`, `MaxItems: 10`, or `max-keys: 10`) only if those
     parameters exist in the definition.
   - For region-like parameters, use the user's region when present; otherwise use `cn-hangzhou`.
   - For IDs, use realistic placeholders with the correct service prefix, such as
     `i-test1234567890`, `vpc-test1234567890`, `vsw-test1234567890`, `sg-test1234567890`, or
     `eipalloc-test1234567890`.
   - For names and descriptions, use short safe placeholders such as `test-vpc`, `test-sg`, or
     `updated by static cli test`.
   - For CIDR and network fields, use documentation-style private/test ranges such as
     `10.0.0.0/8`, `10.0.1.0/24`, or `203.0.113.0/24`.
   - For enums and booleans, choose conservative valid-looking values from the parameter
     description or examples, such as `tcp`, `accept`, `PayByTraffic`, `EcsInstance`, or `false`.
   - For integer sizes/counts/bandwidths, use small values such as `1`, `5`, or `10`.
   - For arrays/objects, preserve the schema shape: pass arrays as JSON arrays and objects as JSON
     objects in `jsonApiParameters`; do not flatten them into guessed CLI flags.
   - If a required parameter cannot be mocked safely from the definition, use a clear placeholder
     value like `<instance-id>` and mention that it must be replaced.

   Treat mock values as examples only. Do not execute generated commands unless the user explicitly
   asks.

5. Generate the command with `AlibabaCloud___GenerateCLICommand` (product, version, action,
   params). From the response, take **`unifiedCli`** verbatim as the `aliyun ...` string for
   MCP `CallCLI`. If **`unifiedCli` is empty**, take **`cli`** instead. Do NOT manually rewrite,
   re-case, or word-split either field — GenerateCLICommand already emits the correct subcommand
   and parameter names (avoiding proper-noun mistakes like `Vpc`, `Ipv6`, `SLB`). Only supply
   parameter *values* in the GenerateCLICommand request from the user's input and the API
   definition. When multiple independent calls are needed, batch the MCP lookups in parallel.
   Never repeat the same tool call with identical arguments.

6. Write the command string(s) to `/tmp/aliyun-cli-commands.sh` (one per line) and validate with
   the local checker:

   ```bash
   cat > /tmp/aliyun-cli-commands.sh <<'SHEOF'
   <aliyun command strings here, one per line>
   SHEOF
   python3 <SKILL_DIR>/script/check_cli.py /tmp/aliyun-cli-commands.sh
   ```

   Where `<SKILL_DIR>` is the directory containing this SKILL.md file.

7. If validation fails, read the `-> fix` suggestion for each violation, fix ONLY the listed
   issues, and re-validate. Maximum 3 rounds. If violations persist, show them to the user.

8. After validation passes, output the command string(s) in a single code block — each line is a
   value you would pass as the `command` argument of MCP `CallCLI`. Optionally add a one-line note
   about required parameters or `--help`. Do not execute them.

## CLI Contract

Enforced by `script/check_cli.py` (local pre-check). On failure, read each violation's
`-> fix` line; for broader CLI syntax, auth, or troubleshooting, see `alibabacloud-cli-guidance`.

| Rule ID | Category | Rule |
|---------|----------|------|
| — | **Command source** | After `GenerateCLICommand`, use the returned **`unifiedCli`** as the CallCLI `command` string. If `unifiedCli` is empty, use **`cli`**. Take the chosen field **verbatim** — do NOT hand-rewrite casing or split words. Only parameter *values* are supplied in the GenerateCLICommand request. |
| REQ-3001 | **CallCLI string** | Each line is one `aliyun ...` command string to pass to MCP `CallCLI`. It must start with `aliyun` — no `echo`, env prefixes, or leading subshell. |
| SEC-2002 | **No shell constructs** | CallCLI runs a single command with no shell. No pipes `\|`, redirects `>`/`<`, operators `&&`/`\|\|`/`;`, or substitution `$(...)`/backticks. Use `--cli-query` to filter instead of piping to `grep`/`jq`. Operators inside quoted values (JMESPath, JSON) are fine. |
| SEC-2003 | **No local files** | The MCP server is remote: no `file://` / `fileb://` paths. File-based commands (e.g. `oss cp`) must run with the local Bash tool, not CallCLI. |
| — | **Dependent steps** | Chain dependent operations by showing separate command lines with a `<placeholder>` for values carried on a previous command's output — never wire them with `$(...)`. |
| — | **OSS / ossutil** | OSS has custom commands (`aliyun oss cp/ls/mb`, `aliyun ossutil sync`), not OpenAPI actions. File operations (`cp`, `sync`) need local filesystem access and must use the Bash tool, not CallCLI. |
| — | **Structured params** | Lists are space-separated (`--security-group-ids sg-1 sg-2`); repeatable key-values use repeated flags (`--tag Key=env Value=prod`); complex structures use single-quoted JSON (`--data-disk '{"Size":100}'`). |
| — | **Output filtering** | Use `--cli-query "<jmespath>"` to filter, `--output table, json, or cols=...` to format, `--pager` / `--page-size` for pagination, `--waiter expr='Status' to='Available'` to wait. |
| — | **No auto-exec** | Suggest the command string(s) only. Do not call MCP `CallCLI` or run `aliyun` locally unless the user explicitly asks. |
| — | **Output format** | Output the command string(s) in one code block. Keep prose minimal — at most a one-line note about required params or `--help`. |

## Command Patterns

Each line below is a `command` string for MCP `CallCLI`. These are **illustrative shapes** —
the actual command must come from GenerateCLICommand's **`unifiedCli`** (or **`cli`** when
`unifiedCli` is empty), not from copying the examples here.

**Single command** (one operation):

```bash
aliyun ecs describe-instances --biz-region-id cn-hangzhou --page-size 50
```

**Sequential** (dependent steps — use a placeholder, not shell substitution):

```bash
# 1) Create the VPC, note the returned VpcId
aliyun vpc create-vpc --biz-region-id cn-hangzhou --cidr-block 10.0.0.0/8
# 2) Create a VSwitch in that VPC (replace <vpc-id> with the value from step 1)
aliyun vpc create-vswitch --biz-region-id cn-hangzhou --vpc-id <vpc-id> --cidr-block 10.0.0.0/16 --zone-id cn-hangzhou-a
```

Do **not** chain with shell substitution or pipes (SEC-2002):

```bash
# ❌ aliyun vpc create-vswitch --vpc-id $(aliyun vpc create-vpc ... --cli-query VpcId)
# ❌ aliyun ecs describe-instances --biz-region-id cn-hangzhou | grep Running
```

**Pagination** (list everything):

```bash
aliyun ecs describe-instances --biz-region-id cn-hangzhou --pager path='Instances.Instance[]' PageNumber=PageNumber PageSize=PageSize
```

**Filtered output** (project specific fields):

```bash
aliyun ecs describe-instances --biz-region-id cn-hangzhou --cli-query "Instances.Instance[?Status=='Running'].{ID:InstanceId,Name:InstanceName}" --output table
```

**Wait for state**:

```bash
aliyun vpc describe-vpc-attribute --biz-region-id cn-shanghai --vpc-id <vpc-id> --waiter expr='Status' to='Available'
```

## Guardrails

- Suggest the `aliyun ...` command string(s) only. Do not call MCP `CallCLI` or run them locally
  unless the user explicitly asks.
- Use **`unifiedCli`** from GenerateCLICommand as the CallCLI command; if empty, use **`cli`**.
  Do not rewrite either field. Only supply parameter values in the GenerateCLICommand request;
  do not invent flags or values.
- Do not use any MCP server except the local `alibabacloud-core` server for API discovery.
- Always validate with `check_cli.py` before output. Do not skip validation.
- If the request is ambiguous but not dangerous, use `<placeholder>` values instead of asking.
- Do not add boilerplate, redundant flags, or unused parameters.

## References

- `script/check_cli.py` — local CallCLI constraint checker (REQ-3001, SEC-2002, SEC-2003).
- `alibabacloud-cli-guidance` — CLI syntax, auth, install, plugin system, and troubleshooting.
