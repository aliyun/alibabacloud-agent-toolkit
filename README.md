# Alibabacloud Ecs Ops

Alibaba Cloud ECS 全生命周期运维管理插件，覆盖实例管理、诊断排障、磁盘快照、安全组网络及场景化运维

## Install

### One-command install (recommended)

```bash
npx openplugin acloudlabs-unofficial/agent-plugins
```

### Manual install

#### Claude Code

```text
/plugin marketplace add acloudlabs-unofficial/agent-plugins
/plugin install alibabacloud-ecs-ops@agent-plugins
/reload-plugins
```

#### Codex

```text
codex plugin marketplace add acloudlabs-unofficial/agent-plugins
```

## MCP Configuration

The MCP server configuration is defined in `.mcp.json`. Review the safety policy before use.

## Skills

| Skill | Description |
|-------|-------------|
| alibabacloud-ecs-instance-ops | Alibaba Cloud ECS instance lifecycle operations. Use for creating, starting, stopping,
restarting, releasing, and querying ECS instances. Covers instance status management,
batch operations, and instance attribute modification.
Triggers: "ecs instance", "create instance", "start instance", "stop instance",
"restart instance", "release instance", "query instance", "ecs ops", "ecs lifecycle". |
| alibabacloud-ecs-diagnose | Alibaba Cloud ECS instance diagnostics and troubleshooting. Use for diagnosing instance
connection issues, performance problems, system status checks, and health monitoring.
Covers SSH/RDP connectivity, system events, instance health, and performance analysis.
Triggers: "ecs diagnose", "ecs troubleshoot", "instance connection issue",
"ssh cannot connect", "ecs performance", "instance health", "ecs monitoring",
"system event", "instance unreachable". |
| alibabacloud-ecs-disk-ops | Alibaba Cloud ECS disk and snapshot operations. Use for managing cloud disks (attach,
detach, expand, create data disk), snapshots (create, restore, delete, policy), and
disk category management. Covers system disk and data disk lifecycle.
Triggers: "ecs disk", "cloud disk", "attach disk", "detach disk", "expand disk",
"data disk", "snapshot", "create snapshot", "restore snapshot", "disk resize",
"disk capacity", "auto snapshot policy". |
| alibabacloud-ecs-security-group | Alibaba Cloud ECS security group and network management. Use for creating and managing
security groups, configuring inbound/outbound rules, managing network interfaces, and
troubleshooting network connectivity. Covers security group CRUD, rule management,
ENI operations, and VPC network checks.
Triggers: "security group", "ecs network", "firewall rule", "security group rule",
"inbound rule", "outbound rule", "network interface", "ENI", "port access",
"open port", "security group management". |
| alibabacloud-ecs-scenario-ops | Alibaba Cloud ECS scenario-based operations. Use for end-to-end operational scenarios
that combine multiple ECS operations into complete workflows: full-stack instance
provisioning (VPC + SecurityGroup + Instance), disk expansion with OS resize, adding
data disks with formatting, instance migration, and batch operations.
Triggers: "create full instance", "provision ecs", "expand disk and resize partition",
"add data disk", "format disk", "ecs migration", "batch ecs operations",
"ecs scenario", "full stack ecs", "instance with network". |
| alibabacloud-cli-cost-estimation | Pre-execution cost estimation for Alibaba Cloud CLI operations. Use this skill
whenever a user asks "how much will this cost", before executing any chargeable
operation (create / resize / renew / bandwidth change), or when planning a
multi-step workflow whose total cost should be known up front. Covers the
--estimate-cost flag (quote without executing), --estimate-cost-context
(usage assumptions and future-state overrides for multi-step workflows),
reading the quote JSON correctly (pricingMode, pricingUnit, delta amounts),
and reconciling quotes against actual bills.
Triggers: estimate cost, cost estimation, price quote, how much will it cost,
询价, 报价, 多少钱, 费用预估, 成本预估, 变配差价, 执行前费用,
estimate-cost, PricingContext, 计费预览, 账单预览, price before execution,
chargeable operation, upgrade cost, renewal cost, bandwidth cost. |

## Hooks

This plugin includes telemetry and tracing hooks. See `hooks/` for details.

## Security, Data Collection, and Privacy

### MCP Safety / MCP 安全

The plugin defines an MCP server with a safety policy that restricts which MCP tools are accessible. Review the `.mcp.json` file in this plugin for the exact policy.

插件定义了带有安全策略的 MCP Server，限制可访问的 MCP 工具。请查看本插件中的 `.mcp.json` 文件了解具体策略。

### Security / 安全

Alibaba Cloud credentials are handled by the user's configured Alibaba Cloud tools, SDKs, MCP servers, or CLI profiles. This toolkit does not store AccessKey secrets, STS tokens, bearer tokens, private keys, or passwords.

MCP is an emerging integration standard. Before using this toolkit in production or regulated environments, review the full integration path, including the MCP client, agent runtime, model provider, local hooks, network access, and Alibaba Cloud account permissions.

阿里云凭证由用户已配置的阿里云工具、SDK、MCP Server 或 CLI profile 处理。本工具包不存储 AccessKey Secret、STS Token、Bearer Token、私钥或密码。

MCP 是较新的集成标准。在生产环境或受监管环境中使用本工具包前，建议审查完整链路，包括 MCP Client、Agent 运行时、模型提供方、本地 hooks、网络访问以及阿里云账号权限。

### Permissions and Risk / 权限与风险

MCP clients and AI agents may invoke Alibaba Cloud operations using the permissions available to the configured identity. Misconfigured, overly autonomous, or overly privileged clients may perform costly, sensitive, or destructive operations.

Use least-privilege RAM policies, separate test and production accounts, review generated commands and Terraform plans, and require explicit human approval before applying infrastructure changes or destructive operations.

MCP Client 和 AI Agent 可能会使用当前配置身份拥有的权限调用阿里云操作。配置不当、自治程度过高或权限过大的客户端，可能执行产生费用、涉及敏感资源或具有破坏性的操作。

建议使用最小权限 RAM 策略，隔离测试与生产账号，审查生成的命令和 Terraform plan，并在执行基础设施变更或破坏性操作前要求明确的人工确认。

### Data Collection / 数据采集

This toolkit collects limited, de-identified operational telemetry to improve Alibaba Cloud agent skills, MCP integrations, and troubleshooting quality. Remote telemetry is limited to Alibaba Cloud plugin activity. User prompts, source code, local file contents, and full tool responses are not uploaded.

Telemetry may include event type, timestamps, client name, plugin or skill name, MCP tool name, execution status, anonymous session identifiers, and Alibaba Cloud OpenAPI RequestId when present.

Additional operational context is collected only after user opt-in. This may include sanitized `aliyun` commands, sanitized MCP tool inputs, structured error classes, and token counts. Credentials, secrets, private keys, bearer tokens, STS tokens, passwords, and obvious personal identifiers are stripped before transmission.

Some features may enable you, Alibaba Cloud, or integrated services to collect operational data from users of applications, agents, workflows, or cloud environments that you build, operate, or expose through this toolkit. If you use such features, you are responsible for complying with applicable laws, providing appropriate notices to your users, and obtaining any required consents.

本工具包会采集有限的、去标识化的操作遥测，用于改进阿里云 Agent Skill、MCP 集成和问题排查质量。远程遥测仅限阿里云插件活动，不上传用户 prompt、源码、本地文件内容或完整工具响应。

遥测可能包括事件类型、时间戳、客户端名称、插件或 skill 名称、MCP 工具名称、执行状态、匿名会话标识，以及存在时的阿里云 OpenAPI RequestId。

额外操作上下文仅在用户 opt-in 后采集，可能包括清洗后的 `aliyun` 命令、清洗后的 MCP 工具输入、结构化错误类型和 token 计数。凭证、密钥、私钥、Bearer Token、STS Token、密码和明显个人标识会在传输前被移除。

某些功能可能使你、阿里云或集成服务采集你通过本工具包构建、运行或开放的应用、Agent、工作流或云环境用户的操作数据。若使用此类功能，你有责任遵守适用法律，向你的用户提供适当告知，并在需要时取得必要同意。

### Telemetry Configuration / 遥测配置

Remote telemetry is enabled by default. To disable remote telemetry:

远程遥测默认开启。禁用远程遥测：

```bash
export ALIBABACLOUD_TELEMETRY=false
```

### Local Audit Trace / 本地审计追踪

The plugin provides a transparent local trace in JSONL format. Local traces are stored on your machine and are not uploaded by default. They are intended for self-audit, troubleshooting, and local visualization.

插件会以 JSONL 格式记录透明的本地 trace。本地 trace 存储在你的机器上，默认不会上传，用于自审计、问题排查和本地可视化。

Local traces may include:

本地 trace 可能包括：

- User prompts for turns that invoke Alibaba Cloud tools
- Full tool inputs and responses, truncated at 64 KB
- Skill invocations, timing, and span hierarchy
- Turn lifecycle events
- 调用阿里云工具的回合中的用户 prompt
- 完整工具输入和响应，最大截断到 64 KB
- Skill 调用、耗时和 span 层级
- 回合生命周期事件

Trace files are stored per session:

trace 文件按 session 存储：

```text
~/.cache/alibabacloud-agent-toolkit/telemetry/<client>/traces/<session-id>.jsonl
```

Light sanitization is applied even locally. Trace files older than 90 days are automatically cleaned up on each session stop to prevent unbounded disk growth.

即使是本地 trace，也会做轻量清洗。超过 90 天的 trace 文件会在每次 session stop 时自动清理，避免磁盘无限增长。

To disable local trace recording:

禁用本地 trace：

```bash
export ALIBABACLOUD_TRACE=false
```

### Compliance Responsibility / 合规责任

This toolkit may interact with MCP clients, model providers, local development tools, Alibaba Cloud services, and third-party components outside Alibaba Cloud's compliance boundary. You are responsible for ensuring that your use of this toolkit complies with applicable organizational policies, laws, regulations, and contractual obligations.

本工具包可能与 MCP Client、模型提供方、本地开发工具、阿里云服务以及第三方组件交互，其中部分组件可能位于阿里云合规边界之外。你有责任确保本工具包的使用方式符合适用的组织策略、法律法规和合同义务。

### Third Party Components / 第三方组件

This toolkit may use or depend on third-party components, package managers, MCP clients, model providers, and local development tools. You are responsible for reviewing and complying with the licenses, security posture, and data handling practices of those components.

本工具包可能使用或依赖第三方组件、包管理器、MCP Client、模型提供方和本地开发工具。你有责任审查并遵守这些组件的许可证、安全状态和数据处理实践。

See [`./hooks/README.md`](./hooks/README.md) for the full telemetry field reference, hook behavior, local file structure, and troubleshooting details.

完整遥测字段、hook 行为、本地文件结构和问题排查细节见 [`./hooks/README.md`](./hooks/README.md)。

## License

This project is licensed under the Apache-2.0 License.
