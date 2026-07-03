# alibabacloud-core

The primary Alibaba Cloud plugin for OpenAPI integration via MCP Server Core.

This plugin includes:

- Plugin manifests for Codex and Claude Code
- An MCP server named `alibabacloud-core` that covers all Alibaba Cloud OpenAPIs
- Skills for SDK code generation, Terraform HCL generation, Terraform import,
  multi-account resource querying, and MCP Core best practices

## Install

Recommended:

```bash
npx openplugin aliyun/alibabacloud-agent-toolkit --plugin alibabacloud-core
```

`openplugin` installs the selected plugin into the detected clients (Claude
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
directory (no symlinks). **This is the canonical source of truth for the
hooks implementation across the entire toolkit** — any future plugin must
copy from here verbatim rather than maintain its own copy. See
[`./hooks/README.md`](./hooks/README.md) for the full event reference,
file structure, and the rationale behind this convention.
