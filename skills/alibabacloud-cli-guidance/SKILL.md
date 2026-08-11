---
name: alibabacloud-cli-guidance
description: >
  Guide for Alibaba Cloud CLI (aliyun) command syntax, plugin system, parameter naming,
  and best practices. Use this skill to generate correct CLI commands, understand plugin
  vs built-in command differences, structured parameter syntax, output filtering, pagination,
  and error troubleshooting. This skill is a CLI knowledge reference — when MCP tools
  (AlibabaCloud___CallCLI, etc.) are available, always prefer MCP tools for execution
  rather than running aliyun commands locally in the shell.
triggers: >
  aliyun CLI, 阿里云CLI, CLI命令, CLI command, aliyun命令, 命令行工具,
  CLI插件, plugin install, CLI安装, CLI配置, CLI报错, CLI error,
  InvalidAccessKeyId, SignatureDoesNotMatch, Throttling, biz-region-id,
  kebab-case, plugin command, CLI语法, command syntax, aliyun plugin,
  生成CLI命令, generate CLI command, CLI参数, CLI parameter
license: Apache-2.0
metadata:
  domain: aliyun-cli
  owner: sdk-team
  contact: sdk-team@alibabacloud.com
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetApiDefinition,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GenerateCLICommand,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___ListProducts"
---

# Aliyun CLI Expert

Guide for managing Alibaba Cloud resources using the `aliyun` command-line tool.

## MCP Tools vs Local CLI Execution

**IMPORTANT**: This skill provides CLI command knowledge and syntax guidance. It does
NOT mean you should always run `aliyun` commands locally in the shell.

**Execution priority:**

1. **MCP tools (highest priority)** — When `AlibabaCloud___CallCLI` and other MCP tools
   are available, **always use them** for API execution. MCP tools handle authentication,
   cross-account access (`x_assume_account_id`), and output filtering (`x_output_jmespath_filter`)
   without requiring local CLI installation or configuration.

2. **Local CLI (fallback)** — Only use local `aliyun` commands in the Bash tool when:
   - MCP tools are not available or not configured
   - The operation requires local file system access (e.g., `aliyun oss cp`, `aliyun ossutil sync`)
   - The user explicitly asks for a local CLI command to copy/paste or use in scripts
   - The user needs to install/configure the CLI itself

**Use this skill's knowledge for:**

- Understanding correct command syntax when calling `AlibabaCloud___CallCLI`
- Generating CLI commands via `AlibabaCloud___GenerateCLICommand`
- Knowing the difference between plugin-style and built-in-style commands
- Understanding parameter naming conventions (especially `--biz-` prefixes)
- Troubleshooting CLI errors returned by MCP or local execution
- Guiding users who want to run commands locally in their own terminals

**Pivot to `alibabacloud-find-skills` when:** the user's request reads as a
solution pattern (batch ops, audits, rotations, scheduled cleanup, runbooks)
or targets a product not covered by any in-plugin skill — a packaged official
skill usually beats hand-rolled CLI sequences. See `mcp-core-best-practices`
→ Skill Discovery for the full trigger list.

## Agent Execution: AI-mode and User-Agent

**Only applicable when running aliyun commands locally** (not via MCP tools).

**Skill identifier**: `AlibabaCloud-Agent-Skills/alibabacloud-cli-guidance`

Use **exactly one** way to attach this skill to requests. **Do not combine** AI-mode
(`configure ai-mode` + `set-user-agent`) with `ALIBABA_CLOUD_USER_AGENT` or a per-command
env prefix for the **same** skill token — the CLI stacks those sources, and
**User-Agent / attribution will duplicate** (bad for telemetry).

| Path | When to use | Start | End / cleanup |
| ---- | ----------- | ----- | ------------- |
| **A — AI-mode (preferred for agents)** | Agent session, many `aliyun` calls | `aliyun configure ai-mode enable` then `aliyun configure ai-mode set-user-agent --user-agent "AlibabaCloud-Agent-Skills/alibabacloud-cli-guidance"` | **[MUST]** `aliyun configure ai-mode disable` before the final response on **every** exit (success, failure, error, cancel, session end). **Do not** `export ALIBABA_CLOUD_USER_AGENT` to the same value while AI-mode is on. |
| **B — Environment or one-shot** | One-off commands, scripts without `configure`, or no AI-mode | `export ALIBABA_CLOUD_USER_AGENT=AlibabaCloud-Agent-Skills/alibabacloud-cli-guidance` for the session, **or** prefix each API call: `ALIBABA_CLOUD_USER_AGENT=AlibabaCloud-Agent-Skills/alibabacloud-cli-guidance aliyun ...` | If you used **`export`**, run `unset ALIBABA_CLOUD_USER_AGENT` when done so other skills are not mis-attributed. Inline prefix needs no unset. **Do not** enable AI-mode on path B for the same skill string. |

**Pre-check: Aliyun CLI >= 3.3.3 required** — Run `aliyun version`. If too low:
`curl -fsSL https://aliyuncli.alicdn.com/setup.sh | bash` or see `references/installation-guide.md`.

**Pre-check: Aliyun CLI plugin update required** — [MUST] `aliyun configure set --auto-plugin-install true`;
[MUST] `aliyun plugin update`.

### CLI Version Milestones

| From version | What you gain |
| ------------- | -------------- |
| **>= 3.3.3** | Baseline for product plugins and flows in this skill. |
| **>= 3.3.5** | **`aliyun upgrade`** — update the CLI from the binary itself. |
| **>= 3.3.8** | **`aliyun plugin show --name <plugin>`** — details for an installed plugin. |

## Instructions

### 1. Install and Configure the CLI

If the user hasn't installed or configured the CLI, guide them through setup.
See `./references/installation-guide.md` for full details. Quick path:

```bash
# Install or update (macOS / Linux — one command)
/bin/bash -c "$(curl -fsSL --connect-timeout 10 --max-time 120 https://aliyuncli.alicdn.com/setup.sh)"
```

After the CLI is at **3.3.5 or newer**, routine self-updates can use **`aliyun upgrade`**.

#### OAuth (browser login)

When a **browser can be opened** on the same machine, **prefer OAuth** over storing
AccessKey pairs. Requires CLI **3.0.299** or later. **Not** suitable for headless environments.

```bash
aliyun configure --profile <your-profile-name> --mode OAuth
```

#### Environment variables (headless / CI/CD)

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID=<key-id>
export ALIBABA_CLOUD_ACCESS_KEY_SECRET=<key-secret>
export ALIBABA_CLOUD_REGION_ID=cn-hangzhou
# Temporary credentials (StsToken) — add:
# export ALIBABA_CLOUD_SECURITY_TOKEN=<sts-token>

# Verify
aliyun version      # Should be >= 3.3.3
aliyun ecs describe-regions   # Tests authentication
```

#### Authentication modes

| Mode | When to use | Environment variables |
| ---- | ----------- | --------------------- |
| **AK** | Development, long-lived credentials | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID` |
| **StsToken** | CI/CD, temporary credentials | Same as AK, plus `ALIBABA_CLOUD_SECURITY_TOKEN` |
| **RamRoleArn** | After AssumeRole or cross-account session | Same variables as **StsToken** |

### 2. Consult `--help` Before Constructing Any Command

Built-in commands have inconsistent parameter naming across APIs. Running `--help` first
is the authoritative source:

```bash
aliyun <product> --help                # Discover available subcommands
aliyun <product> <subcommand> --help   # Get exact parameter names, types, structure
```

When a plugin is installed, `aliyun <product> --help` shows plugin help. To view legacy
built-in help instead:

```bash
ALIBABA_CLOUD_ORIGINAL_PRODUCT_HELP=true aliyun ecs --help
```

### 3. Ensure Service Plugins Are Available

Each Alibaba Cloud product has a CLI plugin. Plugins provide consistent kebab-case
commands with comprehensive help:

```bash
aliyun plugin install --names ecs     # Install (short name, case-insensitive)
aliyun plugin install --names ECS VPC RDS   # Multiple at once
aliyun plugin list                    # Installed plugins
aliyun plugin list-remote             # All available plugins
aliyun plugin search <keyword>        # Search by keyword
aliyun plugin show --name ecs         # >= 3.3.8 — details for one installed plugin
```

### 4. Prefer Plugin Commands Over Built-in Commands

The CLI has two command styles, and the **subcommand casing** determines which system handles it:

- **All-lowercase subcommand** -> routed to plugin (CLI Native style)
- **Contains uppercase** -> routed to built-in (OpenAPI style)

```bash
# Plugin (preferred): consistent kebab-case
aliyun ecs describe-instances --biz-region-id cn-hangzhou

# Built-in (fallback): PascalCase subcommand, inconsistent params
aliyun ecs DescribeInstances --RegionId cn-hangzhou
```

**Note for MCP tools**: `AlibabaCloud___CallCLI` uses OpenAPI-style (PascalCase) commands.
The plugin-style commands are for local CLI execution. When generating commands for MCP
execution, use PascalCase subcommands (e.g., `aliyun ecs DescribeInstances`).

| Aspect | Plugin (CLI Native) | Built-in (OpenAPI) |
| ------ | ------------------- | ------------------ |
| Subcommand | `describe-instances` | `DescribeInstances` |
| Parameters | kebab-case (consistent) | Mixed (inconsistent) |
| ROA Body | Expanded to individual params | Single `--body` JSON |
| Header params | Visible in help, usable directly | Hidden, manual `--header` only |
| Help | Comprehensive with structure | Basic |

### 5. Understand Global vs Business Parameter Naming

The CLI plugin system reserves certain global parameters:

- `--region-id` / `--region` — controls which **API endpoint** the request is sent to.
- Other globals: `--profile`, `--api-version`, `--output`, etc.

Many APIs also define their own `RegionId` parameter. The plugin resolves this with:

1. **`--biz-` prefix (default)**: API's `RegionId` becomes `--biz-region-id`
2. **`--<product>-` prefix (fallback)**: if `--biz-region-id` is already taken

Always check `--help` for the actual parameter name.

### 6. Use Structured Parameter Syntax

Plugins support structured input that the framework serializes automatically:

```bash
--instance-id i-abc123                                  # single value
--security-group-ids sg-001 sg-002 sg-003               # space-separated list
--tag Key=env Value=prod --tag Key=app Value=web        # repeatable key-value
--data-disk '{"DiskName":"d1","Size":100}'              # complex structure (JSON)
```

### 7. OSS Uses Custom Commands

Unlike other products, OSS has a hand-written implementation with custom command syntax.
API-style commands like `PutBucket` do not exist for OSS:

```bash
aliyun oss --help        # Basic operations (cp, ls, mb, rm, etc.)
aliyun ossutil --help    # Advanced utilities (sync, stat, etc.)
```

**Note**: OSS file operations (`cp`, `sync`, etc.) require local file system access.
These cannot be run via MCP tools — use the Bash tool directly.

### 8. Filter and Format Output

```bash
# JMESPath filter
aliyun ecs describe-instances \
  --biz-region-id cn-hangzhou \
  --cli-query "Instances.Instance[?Status=='Running'].{ID:InstanceId,Name:InstanceName}"

# Output formats
aliyun ecs describe-instances --biz-region-id cn-hangzhou --output table
aliyun ecs describe-instances --biz-region-id cn-hangzhou --output cols=InstanceId,InstanceName,Status rows="Instances.Instance[]"
```

**Note for MCP tools**: Use `x_output_jmespath_filter` parameter instead of `--cli-query`.

### 9. Pagination

```bash
aliyun ecs describe-instances \
  --biz-region-id cn-hangzhou \
  --page-number 1 \
  --page-size 50

# Auto-paginate all pages
aliyun ecs describe-instances \
  --biz-region-id cn-hangzhou \
  --pager path='Instances.Instance[]' PageNumber=PageNumber PageSize=PageSize
```

### 10. Wait for Resource State

```bash
aliyun vpc describe-vpc-attribute \
  --biz-region-id cn-shanghai \
  --vpc-id <your-vpc-id> \
  --waiter expr='Status' to='Available'
```

### 11. Debugging

- `--log-level debug` — detailed request/response logs
- `--cli-dry-run` — validate command without executing
- `ALIBABA_CLOUD_CLI_LOG_CONFIG=debug` — environment variable for global debug

For **403**, **Forbidden**, **NoPermission**, see `./references/ram-policies.md`.

### 12. Multi-Version API Support

Some products ship multiple API versions:

```bash
aliyun <product> list-api-versions
aliyun ess describe-scaling-groups --api-version 2022-02-22 --biz-region-id cn-hangzhou
```

Set default version via environment variable:

```bash
export ALIBABA_CLOUD_ESS_API_VERSION=2022-02-22
```

## Global Flags Reference

| Flag | Purpose |
| ---- | ------- |
| `--region <region>` | API endpoint region (global, not business region) |
| `--profile <name>` | Use a named credential profile |
| `--api-version <ver>` | Override API version for this command |
| `--output json\|table\|cols=...` | Response format |
| `--cli-query <jmespath>` | JMESPath filter on response |
| `--log-level debug` | Verbose request/response logging |
| `--cli-dry-run` | Validate without executing |
| `--endpoint <url>` | Override service endpoint |
| `--retry <n>` | Retry count for failed requests |
| `--quiet` | Suppress output |
| `--pager` | Auto-merge all pages for pageable APIs |

## References

- `./references/installation-guide.md` — Installation, configuration modes, credential setup
- `./references/command-syntax.md` — Complete command syntax guide
- `./references/global-flags.md` — Global flags reference
- `./references/ram-policies.md` — On-demand RAM, least privilege, common permission errors
