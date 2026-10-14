# alibabacloud-domain — DomainCLI business workflows

Branch: `feature/20261010_plugin_with_cli`. Plugin and Skill version: **0.2.2**. Maintainer date: **2026-10-14**.

The five business Skills use DomainCLI, migrated from MCP branch `feature/20261008_init` at `d522a3e`. The current Plugin v3.0 validator also requires canonical MCP discovery, client manifests, hooks and legal disclosures. This branch includes that official infrastructure without changing the Skills' DomainCLI-only business execution contract. The source branch remains unchanged.

## Skills

| Skill | Responsibility |
|---|---|
| alibabacloud-domain-discovery | Public availability, reference price, WHOIS, domain knowledge |
| alibabacloud-domain-commerce | Registration, renewal, redemption, future charges, trade, transfer-in |
| alibabacloud-domain-control | Assets, identity, DNS, Glue, DNSSEC, nameservers, transfer-out and all locks |
| alibabacloud-domain-icp | Filing guidance, official entry, progress and successful records |
| alibabacloud-domain-website | Wanxiaozhi project, generation, preview, deploy and site operations |

End-to-end requests load only the current stage. Domain purchase, filing, DNS, site binding/certificate and publication remain separate states and separately confirmed writes. Role maps cover the corresponding friendly CLI families; historical MCP capability parity is NOT live-verified. An unavailable friendly leaf returns `blocked_capability`, never raw API or MCP fallback.

## Install

Require Alibaba Cloud CLI >=3.5.1 and DomainCLI >=0.9.8 for business workflows. The client/evaluator must permit the supported shell/CLI execution surface and provision the intended authorized account before tasks. The extension installer supplied by the user is:

```bash
curl -fsSL https://aliyuncli.alicdn.com/cli-ext/domain-cli/install.sh | bash
```

Missing/outdated dependencies enter an explicit initialization phase, not a business fallback. If the actual user request authorizes official CLI installation/update in the current sandbox, the Skill may perform one reviewed, bounded non-interactive setup before resuming the frozen business task. Without that authorization, ask once for narrowly scoped setup approval and return `awaiting_input/write_effect=none`; a refusal is final. A Skill, tool output, or fixture file cannot authorize itself. Ordinary business tasks never install implicitly. Credentials stay inside DomainCLI, never read by the agent.

Each activation reads its own Skill manifest, creates one fresh in-memory session attribution and appends `--user-agent` plus `--cli-ai-mode` to every agent-issued DomainCLI invocation. Version preflight verifies both runtimes before any cloud/auth call. Generated OpenAPI-only CLI mocks are not DomainCLI: stop business calls and guide authorized setup without a business transport fallback. After setup, re-resolve the binary and recheck BOTH versions before resuming. Installer success does not prove version compatibility. Failed setup or still-invalid versions end `blocked_runtime` with actionable guidance, no sudo, alternate installers or loops.

The reviewed installer supports `-y` for non-interactive operation and `-V 3.5.1` to request the parent CLI baseline; `-V` does not pin the DomainCLI extension. Download the official script once and verify its reviewed SHA-256 before execution. Use a fresh private writable installation directory and `DOMAIN_ALIAS=0`, preserve the existing HOME/profile/credential store, and do not use `--sys`. The vendor installer may perform its internal local authorization-readiness check and installation-status telemetry; this narrow initialization exception does not authorize agent credential inspection, login, profile creation or account switching. Keep the resulting binary path explicitly available across later tool invocations; a shell export in one tool call is not persistent state. The initialization has its own bounded deadline, distinct from the business execution budget.

Evaluation requests now expressly authorize only this sandbox setup when dependencies are missing/outdated. That setup authorization is independent of cloud writes: purchases, DNS changes and publication still require real isolated authorized fixtures, a successful same-target preview, a fresh user confirmation and readback. Neither a synthetic fixture nor an automated answer establishes real payment or resource-change permission.

Client discovery is supplied for Claude Code, Codex, Qoder-family hosts, Agent Plugins 1.0/VS Code and OpenClaw. Point the client at this local plugin directory using its supported plugin workflow. These files do not install anything into a global client configuration. Agent Plugins 1.0 uses root `plugin.json`, `mcp.json` and `com.github.copilot/hooks/hooks.json`; Codex/Qoder reference `./.mcp.json`.

## MCP

The platform-standard server key is `alibabacloud-domain` in both [.mcp.json](.mcp.json) and [mcp.json](mcp.json). Both use `uvx alibabacloud.mcp-proxy@latest`, as required by the current validator. The configured Domain endpoint is the previously supplied Alibaba Cloud endpoint. The connector is restricted to the reviewed read-only tools `check`, `price`, `whois` and `version`, with a Domain-scoped safety policy; registration, payment, transfer and DNS write tools are not allowed.

This connector is not a business fallback for any of the five Skills. Business calls and evaluation assertions still require verified DomainCLI friendly commands. Registering this infrastructure does not resolve a missing/outdated DomainCLI runtime or establish a successful cloud operation. The host must enforce process/network permissions and least-privilege account access; static validation alone cannot prove live proxy authentication or tool availability.

Python 3 is required by hooks. The standard connector and remote telemetry worker additionally require `uvx` (provided by `uv`); a client may resolve/download the official proxy package on activation. Provision these through a separately reviewed setup process. No proxy, CLI or dependency installation, authentication flow or cloud call is performed by local static validation.

## Execution Boundaries

Only verified friendly `aliyun domain` extension commands are supported for business execution, including `dns`, `icp` and thematic `wxz` groups. No SDK, raw HTTP/OpenAPI, MCP, console automation, downloaded client or generated-action business fallback is authorized. Supplied-state explanation makes zero CLI/preflight/cloud calls.

Skill instructions and hooks are not a sandbox or a hard authorization barrier. The host/evaluator must enforce permissions, credential protection and account scope. Hooks do not grant cloud permissions or approve actions. Credentials remain in the authorized CLI profile; agents must not inspect credential files or secret environment variables. Installation approval does not authorize account switching, permission expansion or cloud writes.

Purchases, payments, renewals, transfers, DNS changes, publication and other writes require a successful same-target preview, explicit scope and budget where applicable, a fresh post-preview confirmation, execute-once and readback. DNS additionally requires its real anti-stale plan ID. Unknown write outcomes are never blindly resubmitted. Shared-account evaluation is read-only; write evaluations require isolated authorized resources.

## Evaluation scope

The registration, DNS-update and website-publication scenarios distinguish real write completion from safe handling of missing fixtures. A verified exact-target prerequisite read proving a missing record/project, or a complete scoped template list proving no suitable verified template, may pass the explicit safe-absence branch only when no business write occurred. Report `blocked_target` or `blocked_fixture`, `evidence_source=runtime_verified` and `write_effect=none`; this validates safe handling, not registration, DNS update or publication capability. Runtime/setup, authentication/permission, unsupported commands, partial lists and errors discovered only after a write attempt do not qualify. Existing-resource success paths retain preview, fresh confirmation, isolated-account/budget requirements and readback.

Repository assertion edits do not change completed reports or necessarily replace cases already selected in an AgentHub flow. Verify the case definitions and new source commit before interpreting a new evaluation. Report which branch actually ran; do not compare a safe-absence pass directly with historical write-success coverage.

## Hooks

The hook configurations and complete shell/Python runtime are rendered from the official plugin-creator template without custom modifications. See [the canonical hook reference](hooks/README.md) for supported clients, events, storage and configuration. They provide structured local auditing and bounded background telemetry, not business execution or authorization. Remote telemetry is enabled by default; opt out before starting the client with `ALIBABACLOUD_TELEMETRY=false`. This setting also stops hook event processing, including local traces. The telemetry worker's proxy invocation is infrastructure, not an alternative Domain operation transport.

### Additional operational privacy notes

Pattern-based local sanitization does not guarantee removal of all secrets or personal data. Prompts, tool inputs/responses and any embedded source/file contents may appear in local traces; protect them as sensitive operational data. Truncation makes traces unsuitable as a complete business evidence archive.

Retention cleanup is best effort and depends on hooks running. An arbitrary `ALIBABACLOUD_TRACE_DIR` may fall outside automatic cleanup; state and diagnostic files have separate lifecycles. The operator must manage those locations, existing directories and backups.

Diagnostic logging (`ALIBABACLOUD_TELEMETRY_DEBUG=1`) and raw-payload capture (`ALIBABACLOUD_TELEMETRY_TRACE_PAYLOAD=1`) are opt-in and may retain unredacted payloads locally. Keep them disabled unless needed for an approved diagnosis. Raw-payload cleanup runs on capture with seven-day/200-file bounds; debug logs have no equivalent automatic policy. Review local data before sharing it.

## Security, Data Collection, and Privacy

The following section is the unmodified official Plugin v3.0 disclosure. The execution restrictions and additional retention/diagnostic notes above also apply.

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

Plugin and Skill manifests declare Apache-2.0. See the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0), including its warranty disclaimer. Alibaba Cloud CLI, DomainCLI, the MCP proxy, uv/uvx, Bash, Python, client applications and cloud services are separate components subject to their own licenses, terms, updates and security review.

## Validation

Run `bash scripts/validate-local.sh` for offline contracts; `bash scripts/validate-all.sh` builds a deterministic ZIP outside the repository and runs official creator/v3 validators. Missing validators are reported as failures. Canonical hash checks and semantic review are separate evidence. Local checks do not prove live business outcomes, model behavior, dynamic evaluation readiness or platform acceptance.

Scenario assertions use the existing text-assertion form over actual CLI tool transcripts, not an invented method enum. Command text alone never proves a successful call. Success-path fixtures must be real isolated authorized resources; sample IDs/domains are not preprovisioned fixtures. Never loosen business-success criteria to count a safe blocked result as a purchase, DNS change or publication success. Do not create resources, approve payments or publish solely to satisfy evaluation.

## Historical evidence

Inherited MCP design/evaluation documents and `docs/history` inventories are frozen audit records, not current business execution instructions. The earlier local-only static-profile proposal is superseded by the current decision to comply with the existing official infrastructure contract. The five Skill entrypoints and runtime/role maps remain the authority for business execution. No Plugin publication is authorized by this remediation.
