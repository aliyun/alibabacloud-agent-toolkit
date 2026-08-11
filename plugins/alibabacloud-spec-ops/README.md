# alibabacloud-spec-ops

> A complete **infrastructure operations methodology** for coding agents on Alibaba Cloud.
> Don't let agents blindly write Terraform — make them **think like an architect, validate like a reviewer, execute like an SRE, and iterate continuously**.

## TL;DR — One command, full SDD treatment

```text
/alibabacloud-spec-ops:alibabacloud-planning   I need a web app on aliyun
```

Then you get:

- 🧠 **一组阿里云专家**陪你**澄清需求** —— Security / Cost / Efficiency / Stability 四维度逐项问诊，把模糊的"我想要个 web app"挖成精确的架构方案
- 📝 **schema-verified Terraform** —— IaCService 实时校验，不胡编资源属性
- ✅ **双独立 reviewer 并行评审** —— spec 满足度 + 代码质量，挡在执行之前
- 🚀 **远程沙箱执行** —— IaC Service 帮你跑 plan + apply，一次授权一气呵成，全链路审计
- ↻ **可持续迭代的设计 + 状态** —— `design.md` 和远程 `state_id` 跨会话保留，Day-2 一句"升配 RDS"就在原有基础上做增量，不重建已有资源

## Workflow at a Glance

```mermaid
flowchart LR
    classDef plan fill:#e8f0fe,stroke:#1967d2,color:#1967d2
    classDef code fill:#fef7e0,stroke:#e37400,color:#e37400
    classDef val  fill:#e6f4ea,stroke:#1e8e3e,color:#1e8e3e
    classDef exec fill:#fce8e6,stroke:#c5221f,color:#c5221f

    Plan["🧠 Plan<br/>Requirement Scoping<br/>Alibaba Cloud Docs<br/>Best Practices"]:::plan
    Code["📝 Code<br/>IaC Templates<br/>Schema Verified"]:::code
    Validate["✔ Validate<br/>Spec Compliance Review<br/>Code Quality Review"]:::val
    Execute["🚀 Execute<br/>Human-In-The-Loop<br/>Sandboxed Execution"]:::exec

    Plan --> Code --> Validate --> Execute
    Execute -. "DAY-2: MODIFY & ITERATE" .-> Plan
```

Two infrastructure lanes run underneath every stage:

- **MCP (Alibaba Cloud CLI) drives every stage** — real-time docs lookup, schema verification, remote IaC Service execution
- **Observability (Trace + Telemetry) spans the full lifecycle** — every tool call's duration, status, request-id, and outcome is recorded for audit

## Get Started — Step by Step

### 1. Install the plugin

Recommended:

```bash
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-spec-ops
```

`openplugin` installs the selected plugin into the detected clients (Claude
Code, Codex CLI, QoderWork) and configures client-specific hooks/MCP wiring.

### 2. One-time prerequisites

- **`aliyun` CLI configured** — `aliyun configure` with a valid AccessKey, or rely on AssumeRole / OIDC / ECS RAM role. The plugin never reads or stores AK/SK itself.
- **`uvx` on PATH** — install via `brew install uv` (macOS) or `curl -LsSf https://astral.sh/uv/install.sh | sh` (Linux/WSL). The plugin's MCP server boots through `uvx alibabacloud.mcp-proxy@latest`.

### 3. Kick off the workflow

Pass your requirement inline (or after the prompt — both work):

```text
/alibabacloud-spec-ops:alibabacloud-planning   I need a web app on aliyun
```

The planner asks 2–8 clarifying questions (Fast Track vs Full Mode auto-picked by complexity), evaluates every key choice across **Security / Cost / Efficiency / Stability**, then proposes 1–3 architectures with cost estimates.

### 4. Approve the design

When the final design + cost estimate is shown, reply **"确认"** (or `confirm`). The plugin then auto-chains the next two stages and renders a 3-task TODO list so you always see how far through the pipeline you are:

```text
writing-plans → terraform-codegen → validate (spec + quality reviewers in parallel)
```

### 5. Approve the deploy — the ONLY user gate

After validation passes, the plugin asks once whether to deploy. Reply **"部署"** (or `yes`). Then `terraform plan` + `apply` run **automatically** through Alibaba Cloud IaC Service — sandboxed, with a full audit trace. You can still interrupt mid-stream if `plan` output reveals anything unexpected; spec-driven failures (e.g. a SKU offline in the target AZ) automatically stop and ask you for a replacement.

### 6. Iterate (Day-2)

Need to scale up or add a service later? Just say it:

```text
/alibabacloud-spec-ops:alibabacloud-planning   RDS 升配到 2C4G + 加一台 ECS
```

The plugin auto-detects the modification intent, loads the previous `design.md`, and continues on the same remote `state_id` — your existing resources stay, only the delta is applied.

## Each Stage in Detail

### 1. Plan — 需求澄清与架构设计

扮演阿里云资深解决方案架构师，像专家问诊一样逐步引导用户澄清需求边界 —— 即使用户表达模糊或不完整，也能通过结构化提问挖掘真实意图。实时调用 MCP 查询阿里云官方文档、产品 API 和最佳实践，**用数据驱动每一个架构决策**。所有关键选型均从 **安全 / 成本 / 效率 / 稳定性** 四维度评估，并给出带理由的明确推荐。

- **快速模式**：2-3 个问题锁定规格
- **完整模式**：四维度逐一深度探索

### 2. Code — IaC 代码生成

将审批通过的架构设计转化为 Terraform HCL 代码。通过专用的 `alibabacloud-terraform-codegen` skill 生成，确保每个资源块均经过 Schema 校验，符合阿里云 Provider 的最新规范。代码按资源类型组织，结构清晰、可维护。

- **快速模式**：单文件 `main.tf`
- **完整模式**：按资源类型拆分

### 3. Validate — 双重独立验证

执行前的质量关卡。派遣两个独立的 AI 子代理**并行**审查：

- **需求满足度审查**（`spec-reviewer`）—— 逐条比对 `design.md`，确保每项需求都在代码中正确实现、无遗漏
- **代码质量审查**（`code-quality-reviewer`）—— 检查安全合规、命名规范、最佳实践和可维护性

加上代码生成阶段已通过的 IaC Service 远程语法校验，**三重保障**确保进入执行的内容质量达标。

- **快速模式**：仅信任上游远程语法校验
- **完整模式**：两个 reviewer 并行 + 上游语法校验

### 4. Execute — 人工确认 + 沙箱执行

通过 MCP 调用阿里云 **IaC Service** 远程执行，全程沙箱隔离、零本地风险。严格遵循 Human-In-The-Loop 原则：

- 用户在 Validate 出口**一次性授权**整条 plan + apply 链路
- 自动展示 `terraform plan` 变更详情，但**不再二次拦截**
- 若 plan 出现非预期破坏性变更（典型 Day-2 中误删资源），主动停下来询问
- **Destroy 必须二次确认**（输入项目名才执行）

每一步操作均有完整审计记录和可追溯 Trace。

### ↻ Day-2 — 持续维护与增量迭代

基础设施不是一次性交付，而是持续演进。当用户说"升配 / 扩容 / 加 Redis"，spec-ops 自动检测变更意图并扫描 `.aliyun-ai-ops-spec/` 已有项目，**先读全原 `design.md` 内化原设计意图**，再加载现有 Terraform 代码和执行历史作为上下文。变更对话以"在已有架构基础上做 delta"的方式进行 —— 只改需要变的部分。然后走同一条 Plan → Code → Validate → Execute 流水线，**复用远程 `state_id`**，在原有资源状态上做增量 plan/apply，不重建已有资源。

每一次迭代都有据可循，源 `design.md` 与 `.tf` 始终同步反映真实部署。

## Quality In, Quality Out

```text
❌ Garbage In, Garbage Out
        vs
💎 Quality In, Quality Out
```

Planning 是入口关卡 —— 让阿里云虚拟专家助理帮你**把需求澄清对、把设计做对**。
Validate 是出口关卡 —— 确保执行前内容质量达标。

| ❌ Without — 临时拼凑、脆弱不可控 | ✅ With — 系统化、可持续迭代 |
| --- | --- |
| 需求模糊就直接写代码 —— 用户无法一次性表达清楚，Agent 也不会主动追问 | 专家诊断式探索 —— 即使用户表达模糊，也能逐步引导澄清真实需求和边界 |
| 没有专家引导澄清边界 —— 模糊需求变成错误假设，固化到基础设施中 | 需求边界先锁定再动手 —— 不在错误假设上浪费一行代码 |
| Agent 盲写 Terraform，反复试错 | MCP 实时数据驱动的架构设计 |
| 无架构评审 —— 遗漏安全漏洞 | 四维评审：安全 / 成本 / 效率 / 稳定性 |
| 无验证关卡 —— 代码与设计意图偏离 | 双独立 Agent 验证，执行前必须通过 |
| 手动 CLI 复制粘贴 —— 无审计追踪 | MCP 远程沙箱执行 —— 零本地风险，全链路审计 |
| 无成本感知 —— 账单惊喜 | 每个决策点都有实时费用估算 |
| 无可观测性 —— 黑盒操作，出问题无从追溯 | 全链路可观测 —— 每次调用的耗时、状态、结果均可追溯 |
| Day-2 变更 —— 每次都从头开始 | Day-2 持续迭代 —— 加载上下文，增量变更，同一条流水线 |

## State Directory

All artifacts live under `.aliyun-ai-ops-spec/{requirement-name}/`:

```text
.aliyun-ai-ops-spec/{name}/
├── designs/
│   ├── design.md              # Architecture design + Decisions Log
│   ├── architecture.html      # Optional visual diagram
│   └── terraform/             # Generated HCL
└── tasks/
    ├── status.json            # Pipeline state + state_id for Day-2
    ├── validation-report.md
    ├── tf-plan-result.md
    └── tf-apply-result.md
```

`status.json` carries the IaC Service `state_id` so the next iteration continues on the same remote state instead of recreating resources.

## Install

Recommended:

```bash
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-spec-ops
```

To target one client only, add a client flag:

```bash
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-spec-ops --claude
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-spec-ops --codex
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-spec-ops --qoderwork
```

## MCP

This plugin configures an MCP server named `alibabacloud-spec-ops` without a safety policy by default, allowing access to all Alibaba Cloud CLI commands. For production environments, configure a safety policy to restrict the callable command set:

```json
{
  "mcpServers": {
    "alibabacloud-spec-ops": {
      "command": "uvx",
      "args": [
        "alibabacloud.mcp-proxy@latest",
        "--safety-policy",
        "iacservice:*=allow,ecs:*=allow,vpc:*=allow,rds:*=allow,*=deny"
      ]
    }
  }
}
```

The server is named distinctly from `alibabacloud-core` to avoid namespace collision when both plugins are installed simultaneously.

## Skills

| Skill | Description |
|-------|-------------|
| `alibabacloud-planning` | Clarify requirements and design Alibaba Cloud architectures (Day-1 / Day-2) |
| `alibabacloud-writing-plans` | Convert approved designs into Terraform HCL via the codegen skill |
| `alibabacloud-terraform-codegen` | Generate and modify Alibaba Cloud Terraform HCL code |
| `alibabacloud-validate` | Dual review (spec compliance + code quality) — auto-runs after codegen |
| `alibabacloud-executing-plans` | Execute validated Terraform plans through Alibaba Cloud IaC Service |
| `alibabacloud-ram-permission-diagnose` | Diagnose and repair RAM permission errors (403 / NoPermission / etc.) |

## Agents

| Agent | Purpose |
|-------|---------|
| `spec-reviewer` | Verify generated Terraform implements every requirement in `design.md` |
| `code-quality-reviewer` | Evaluate Terraform for quality, security, and best practices |

Both agents are dispatched in parallel by `alibabacloud-validate`.

## Hooks

Telemetry and local trace hooks live at [`./hooks/`](./hooks/) as a real directory (no symlinks). See [`./hooks/README.md`](./hooks/README.md) for the full event reference, file structure, and rationale.

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
