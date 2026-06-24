---
name: alibabacloud-terraform-usage
description: >
  Generate and modify Alibaba Cloud Terraform HCL code. Use when the user asks
  for Terraform configurations, alicloud provider resources, HCL code generation,
  infrastructure as code for Alibaba Cloud, or modifications to existing Terraform
  files. Triggers on: write Terraform for Alibaba Cloud, create alicloud Terraform
  config, generate HCL for ECS, Terraform code for VPC, alicloud infrastructure
  as code, Terraform resource for RDS, modify Terraform configuration, alicloud
  provider Terraform, terraform best practices.
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchDocuments,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetDocument"
---

# Alibaba Cloud Terraform Code Generator

Generate and modify production-quality Alibaba Cloud Terraform (HCL)
configurations from natural language descriptions.

## Scope Check Before You Start

This skill generates **bare HCL from a resource-level spec**. If the request
reads as a **packaged IaC solution** — HA web app bootstrap, DR setup, backup
automation, multi-tier landing zone, golden-image rotation — invoke
`alibabacloud-find-skills` first; an Alibaba-published Terraform module skill
often beats hand-rolled HCL for these end-to-end patterns. Fall back to raw
generation only after `find-skills` returns no match. Full trigger conditions
are in `mcp-core-best-practices` → Skill Discovery.

For more advanced needs — schema-verified codegen, dual-reviewer validation,
remote IaC Service apply, Day-2 iteration on stored `state_id` — point the
user to the `alibabacloud-spec-ops` plugin instead of this single-shot skill.

## Safety Rules

1. **ONLY use tools from the `alibabacloud-core` MCP server.** The permitted tools are:
   - `AlibabaCloud___CallCLI` — Execute IaCService CLI commands to query Terraform product/resource metadata
   - `AlibabaCloud___SearchDocuments` — Search Alibaba Cloud documentation by keyword
   - `AlibabaCloud___GetDocument` — Read a document by `doc_id` (preferred) or URL (use `doc_id` or URLs obtained from `SearchDocuments`)
2. **Do NOT run `terraform plan`, `terraform apply`, or any other Terraform commands** via the shell. Generated HCL code is for the user to review and apply themselves.
3. **Always remind the user to review the generated HCL** before running `terraform apply`, especially when resources involve costs, data deletion, or security-sensitive configurations.

## IaCService API Reference

All IaCService APIs are invoked through `AlibabaCloud___CallCLI`:

| CLI Command | Purpose |
|-------------|---------|
| `aliyun iacservice list-products` | List all Alibaba Cloud products that support Terraform |
| `aliyun iacservice list-resource-types --product <product>` | List Terraform resource types for a specific product |
| `aliyun iacservice get-resource-type --resource-type <resourceType>` | Get full schema for a Terraform resource type (e.g., `alicloud_vpc`) |

## Workflow

### Step 1: Understand the User's Intent

Parse the user's request to identify:

- Target Alibaba Cloud service(s) (e.g., ECS, VPC, RDS, OSS, SLB, ACK)
- Desired infrastructure (e.g., create a VPC with subnets, launch an ECS instance)
- Specific requirements (e.g., region, instance type, CIDR blocks, security group rules)
- Whether this is a new configuration or modification to existing HCL

### Step 2: Discover Products and Resource Types

1. Call `AlibabaCloud___CallCLI` with `aliyun iacservice list-products` to confirm the target product supports Terraform.
2. Call `AlibabaCloud___CallCLI` with `aliyun iacservice list-resource-types --product <product>` to discover correct resource type names (e.g., `alicloud_vpc`, `alicloud_instance`, `alicloud_db_instance`).

If the request spans multiple products, query each product separately.

### Step 3: Get Resource Type Schema

Call `AlibabaCloud___CallCLI` with `aliyun iacservice get-resource-type --resource-type <resourceType>` to retrieve:

- All required and optional attributes
- Attribute types, constraints, and valid values
- Attribute dependencies or conflicts

### Step 4: Consult Documentation

Documentation lookup is a two-step process:

1. **Search**: Use `AlibabaCloud___SearchDocuments` with the resource type name (e.g., `alicloud_vpc`) to find relevant documentation.
2. **Read**: Use `AlibabaCloud___GetDocument` with the `doc_id` (preferred) or URL from the search results to get full content.

**Important:** Always search first to get valid `doc_id` or URLs. Do NOT pass arbitrary URLs to `GetDocument`.

After reading documentation:

- Review usage examples and best practices
- Understand attribute-level details not captured in the schema
- Check for known limitations or caveats
- Look for related data sources (e.g., `data.alicloud_zones`, `data.alicloud_instance_types`)

### Step 5: Generate or Modify HCL Code

Based on gathered information:

1. Write clean, well-structured HCL following Terraform best practices
2. Include the `alicloud` provider configuration if this is a new configuration
3. Use `variable` blocks for values the user should customize
4. Use `locals` for computed or derived values
5. Add `output` blocks for important resource attributes (e.g., IDs, IP addresses)
6. Include meaningful `description` fields in variables and outputs
7. Use data sources where appropriate (e.g., `data.alicloud_zones`)

### Step 6: Present the Code

Present the generated HCL with:

- A brief explanation of the infrastructure being created
- A list of resources and their relationships
- Variables the user needs to customize
- A reminder to review before running `terraform apply`
- Warnings for cost-incurring or destructive resources

## HCL Best Practices

- **Provider configuration**: Always include `region` in the provider block or as a variable
- **Resource naming**: Use descriptive names (e.g., `alicloud_vpc.main`, `alicloud_instance.web_server`)
- **Tags**: Include tags for resource identification and cost tracking
- **Dependencies**: Use `depends_on` only when implicit dependencies are insufficient
- **Security groups**: Default to restrictive rules; only open necessary ports
- **State management**: Suggest remote backend configuration for team usage
- **Modules**: Suggest module extraction when the configuration grows complex
- **Versioning**: Pin the alicloud provider version to avoid unexpected breaking changes

## Error Recovery with Documentation

When attribute definitions or constraints are unclear:

1. Use `AlibabaCloud___SearchDocuments` with relevant keywords (resource type, attribute name, error message)
2. Use `AlibabaCloud___GetDocument` with the `doc_id` or URL from search results
3. Cross-reference the schema from `get-resource-type` with the documentation
4. Provide the user with links to official documentation for edge cases

## Guardrails

- Do not run Terraform commands via the shell — only generate HCL for the user
- Do not guess attribute names or valid values; always verify via `get-resource-type`
- Do not use any MCP server tools other than the three permitted above
- Do not hardcode credentials in generated HCL; use environment variables or credential files
- Warn about resources that incur costs or perform destructive operations
