# alibabacloud-core

The primary Alibaba Cloud plugin for OpenAPI integration via MCP Server Core.

Help AI coding agents build, deploy, and operate applications on Alibaba Cloud through a constrained MCP server that covers all Alibaba Cloud OpenAPIs.

## What's Included

- Plugin manifests for Claude Code, Codex, and QoderWork
- An MCP server named `alibabacloud-core` that covers all Alibaba Cloud OpenAPIs
- Skills for SDK code generation, Terraform HCL generation, Terraform import,
  multi-account resource querying, and MCP Core best practices
- Telemetry and local trace hooks

## Repository Layout

```text
.
├── .claude-plugin/     # Claude Code plugin manifest
├── .codex-plugin/      # Codex plugin manifest
├── .qoder-plugin/      # QoderWork plugin manifest
├── .mcp.json           # MCP server configuration
├── hooks/              # Telemetry and local trace hooks
└── skills/             # Bundled Alibaba Cloud skills
```

## Prerequisites

**Python 3.10+** — hook handlers (pre-installed on most systems).

**[uv](https://docs.astral.sh/uv/)** (provides `uvx`) — telemetry tracing view & mcp server:

```bash
# macOS
brew install uv
```

```
# Linux / WSL
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

**[Alibaba Cloud CLI](https://help.aliyun.com/document_detail/139508.html)** (`aliyun`) — cloud operations:

```bash
# Linux amd64
curl -fsSL https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz | tar xz

# macOS
brew install aliyun-cli
```

## Install

Recommended:

```bash
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-core
```

`openplugin` installs the plugin into the detected clients (Claude
Code, Codex CLI, QoderWork) and configures client-specific hooks/MCP wiring.

To target one client only, add a client flag:

```bash
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-core --claude
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-core --codex
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-core --qoderwork
```

## MCP

This plugin configures an MCP server named `alibabacloud-core` without a safety
policy, allowing access to all Alibaba Cloud CLI commands. For production
environments, configure a safety policy to restrict the callable command set:

```json
{
  "mcpServers": {
    "alibabacloud-core": {
      "command": "uvx",
      "args": [
        "alibabacloud.mcp-proxy@latest",
        "--safety-policy",
        "ecs:*=allow,vpc:*=allow,*=deny"
      ]
    }
  }
}
```

## Skills

| Skill | Description |
|-------|-------------|
| `alibabacloud-sdk-usage` | Generate or modify Alibaba Cloud SDK code using OpenAPI metadata |
| `alibabacloud-terraform-code-generation` | Generate validated Alibaba Cloud Terraform HCL from natural language using alibabacloud-core MCP metadata, docs, and remote IaCService validation |
| `alibabacloud-terraform-import` | Import existing Alibaba Cloud resources into Terraform management with discovery, HCL generation, state import, and drift validation |
| `alibabacloud-multi-account-query` | Query resources across RD member accounts by alias |
| `alibabacloud-mcp-core-best-practices` | Shared reference for MCP Core tool usage patterns |
| `alibabacloud-find-skills` | Search and install Alibaba Cloud official skills when this plugin's built-in skills don't cover the user's task |

### When the built-in skills don't fit

The built-in skills above cover the common ground (SDK codegen, Terraform, CLI guidance, cross-account queries). For everything else — purpose-built operational solutions (batch ops, key rotation, backup audits), less common products, or end-to-end workflows packaged by the Alibaba Cloud team — invoke `alibabacloud-find-skills`. It searches the official Alibaba Cloud skill catalog and installs a matching skill on demand, so the agent does not have to hand-roll an answer when a vetted one already exists. See the `mcp-core-best-practices` Skill Discovery section for exact trigger conditions.

## Hooks

Telemetry and local trace hooks live at [`./hooks/`](./hooks/) as a real
directory (no symlinks). See [`./hooks/README.md`](./hooks/README.md) for the
full event reference, file structure, and rationale.

## Data Collection

[English](#english) | [中文](#中文)

### English

#### Data Collection

During operation, this toolkit may collect necessary information related to your usage and send it to Alibaba Cloud. Alibaba Cloud will use this information only to provide, maintain, and continuously improve related services.

By default, we only collect basic operational information related to Alibaba Cloud plugin activity, as described in **[What is collected by default](#what-is-collected-by-default)**. You may turn off this data collection at any time by following the instructions below. In addition to the default collection, the toolkit may collect necessary supplementary information for troubleshooting or similar needs only after obtaining your authorization, as described in **[Additional opt-in fields](#additional-opt-in-fields)**.

In addition, some features in this toolkit may enable you and Alibaba Cloud to collect data from users of your applications. If you use these features, you must comply with applicable laws, including providing appropriate notice to users of your applications and obtaining any required consent. Your use of this toolkit constitutes your consent to these practices.

##### What is collected by default

All fields below describe Alibaba Cloud plugin behavior only.

| Field | Description |
|---|---|
| startTimestamp / endTimestamp | Alibaba Cloud tool call start and end time (ISO 8601 UTC) |
| clientName | Agent client type (`claude-code`, `codex`, `copilot-cli`, `qoderwork`, `vscode`) |
| eventType | Alibaba Cloud event category (`skill_invocation`, `mcp_tool_use`, `cli_command_use`, `subagent_dispatch`, `reference_file_read`, `user_prompt_turn_start`, `llm_call`) |
| sessionId / mcpSessionId | Session identifiers used for correlation; not linked to an Alibaba Cloud account by this toolkit |
| skillName / pluginName / skillTag | Alibaba Cloud skill and plugin identity |
| mcpTool / toolName | Alibaba Cloud MCP tool name and raw tool entry point |
| eventTag | Fixed Alibaba Cloud event marker |
| status | Alibaba Cloud tool call outcome (`success` / `failure`) |
| toolRequestId | Alibaba Cloud OpenAPI RequestId for server-side log correlation |

##### Additional opt-in fields

These fields contain sanitized Alibaba Cloud operational context and are collected only after explicit user authorization.

| Field | Description |
|---|---|
| cliCommand | Sanitized `aliyun` CLI command or Alibaba Cloud MCP tool input JSON; credentials stripped; capped at 2000-4000 chars |
| errorMessage | Alibaba Cloud API error class/code only, such as `NoPermission` or `Throttling`; not free-text |
| inputUncachedTokens | LLM uncached input tokens for turns involving Alibaba Cloud tools |
| inputCachedTokens | LLM cached input tokens for turns involving Alibaba Cloud tools |
| inputCreationTokens | LLM cache creation tokens for turns involving Alibaba Cloud tools |
| outputTokens | LLM output tokens for turns involving Alibaba Cloud tools |
| reasoningTokens | LLM reasoning tokens for turns involving Alibaba Cloud tools |

#### Telemetry Configuration

Remote telemetry is enabled by default. To disable remote telemetry:

```bash
export ALIBABACLOUD_TELEMETRY=false
```

#### Local Audit Trace

The plugin provides a transparent local trace in JSONL format. Local traces are stored on your machine and are not uploaded by default. They are intended for self-audit, troubleshooting, and local visualization.

Local traces may include:

- User prompts for turns that invoke Alibaba Cloud tools
- Full tool inputs and responses, truncated at 64 KB
- Skill invocations, timing, and span hierarchy
- Turn lifecycle events

Trace files are stored per session:

```text
~/.cache/alibabacloud-agent-toolkit/telemetry/<client>/traces/<session-id>.jsonl
```

Light sanitization is applied even locally. Trace files older than 90 days are automatically cleaned up on each session stop to prevent unbounded disk growth.

To disable local trace recording:

```bash
export ALIBABACLOUD_TRACE=false
```

#### Local Telemetry Visualization

`telemetry-view` starts a local web server for browsing and analyzing trace data. It supports multi-client session browsing, span hierarchy tree, Gantt timeline, graph flow chart, and live updates.

Start:

```bash
uvx alibabacloud.mcp-proxy@latest telemetry-view
```

It opens `http://localhost:18321` in your browser automatically.

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `18321` | Local server port |
| `--no-open` | - | Do not auto-open browser |

Data sources scanned automatically:

1. `$ALIBABACLOUD_TELEMETRY_STATE_DIR`, if set
2. `~/.cache/alibabacloud-agent-toolkit/telemetry/`
3. `/tmp/alibabacloud-agent-toolkit-telemetry-<uid>/`

### 中文

#### 数据采集

本工具包在运行过程中可能会收集与您使用情况相关的必要信息，并发送至阿里云。阿里云将仅用于提供、维护和持续改进相关服务。

默认情况下，我们仅采集与阿里云插件活动相关的基础运行信息（详见 **[默认采集内容](#默认采集内容)**），您可随时按照下方说明关闭此类数据采集。除默认采集信息外，如问题排查等需要，在获得您授权后，本工具包将额外采集必要的补充信息（详见 **[额外授权字段](#额外授权字段)**）。

此外，本工具包中的某些功能可能会使您和阿里云能够收集您应用程序用户的数据。如果您使用这些功能，则必须遵守适用法律，包括向您的应用程序用户提供适当通知并取得必要同意。您使用本工具包即表示您同意这些做法。

##### 默认采集内容

以下字段仅描述阿里云插件行为。

| 字段 | 说明 |
|---|---|
| startTimestamp / endTimestamp | 阿里云工具调用的开始和结束时间（ISO 8601 UTC） |
| clientName | Agent 客户端类型（`claude-code`、`codex`、`copilot-cli`、`qoderwork`、`vscode`） |
| eventType | 阿里云事件类别（`skill_invocation`、`mcp_tool_use`、`cli_command_use`、`subagent_dispatch`、`reference_file_read`、`user_prompt_turn_start`、`llm_call`） |
| sessionId / mcpSessionId | 用于关联的会话标识；本工具包不会将其关联到阿里云账号 |
| skillName / pluginName / skillTag | 阿里云 skill 和插件标识 |
| mcpTool / toolName | 阿里云 MCP 工具名称和原始工具入口 |
| eventTag | 固定的阿里云事件标记 |
| status | 阿里云工具调用结果（`success` / `failure`） |
| toolRequestId | 用于服务端日志关联的阿里云 OpenAPI RequestId |

##### 额外授权字段

以下字段包含清洗后的阿里云操作上下文，仅在您明确授权后采集。

| 字段 | 说明 |
|---|---|
| cliCommand | 清洗后的 `aliyun` CLI 命令或阿里云 MCP 工具输入 JSON；凭证会被移除；长度限制为 2000-4000 字符 |
| errorMessage | 仅包含阿里云 API 错误类别或错误码，例如 `NoPermission` 或 `Throttling`；不包含自由文本 |
| inputUncachedTokens | 涉及阿里云工具的回合中的 LLM 未缓存输入 token 数 |
| inputCachedTokens | 涉及阿里云工具的回合中的 LLM 已缓存输入 token 数 |
| inputCreationTokens | 涉及阿里云工具的回合中的 LLM 缓存创建 token 数 |
| outputTokens | 涉及阿里云工具的回合中的 LLM 输出 token 数 |
| reasoningTokens | 涉及阿里云工具的回合中的 LLM reasoning token 数 |

#### 遥测配置

远程遥测默认开启。禁用远程遥测：

```bash
export ALIBABACLOUD_TELEMETRY=false
```

#### 本地审计追踪

插件会以 JSONL 格式记录透明的本地 trace。本地 trace 存储在您的机器上，默认不会上传，用于自审计、问题排查和本地可视化。

本地 trace 可能包括：

- 调用阿里云工具的回合中的用户 prompt
- 完整工具输入和响应，最大截断到 64 KB
- Skill 调用、耗时和 span 层级
- 回合生命周期事件

trace 文件按 session 存储：

```text
~/.cache/alibabacloud-agent-toolkit/telemetry/<client>/traces/<session-id>.jsonl
```

即使是本地 trace，也会做轻量清洗。超过 90 天的 trace 文件会在每次 session stop 时自动清理，避免磁盘无限增长。

禁用本地 trace：

```bash
export ALIBABACLOUD_TRACE=false
```

#### 本地遥测可视化

`telemetry-view` 会启动本地 Web Server，用于浏览和分析 trace 数据。它支持多客户端 session 浏览、span 层级树、Gantt 时间线、图形链路视图和实时更新。

启动：

```bash
uvx alibabacloud.mcp-proxy@latest telemetry-view
```

它会自动在浏览器中打开 `http://localhost:18321`。

参数：

| 参数 | 默认值 | 说明 |
|------|---------|-------------|
| `--port` | `18321` | 本地服务端口 |
| `--no-open` | - | 不自动打开浏览器 |

自动扫描的数据来源：

1. `$ALIBABACLOUD_TELEMETRY_STATE_DIR`，如果已设置
2. `~/.cache/alibabacloud-agent-toolkit/telemetry/`
3. `/tmp/alibabacloud-agent-toolkit-telemetry-<uid>/`
