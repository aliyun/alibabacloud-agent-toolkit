---
name: multi-account-query
description: >
  Query Alibaba Cloud resources across multiple accounts in a Resource Directory.
  Resolves member account aliases to UIDs via ResourceDirectory ListAccounts,
  then uses x_assume_account_id to assume into the target account for CLI calls.
  Use when the user references a member account by display name or alias, or
  explicitly asks to query resources in another account under the same RD.
  MUST be loaded for any cross-account or member-account operation before
  calling AlibabaCloud___CallCLI with x_assume_account_id.
triggers: >
  成员账号, member account, 跨账号, cross-account, 资源目录, resource directory,
  x_assume_account_id, assume role, 其他账号, other account, 子账号资源,
  ListAccounts, 账号下的, 查询账号, account alias, 多账号, multi-account,
  某个账号的, 切换账号
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetApiDefinition,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GenerateCLICommand"
---

# Multi-Account Resource Query

Query Alibaba Cloud resources across member accounts in a Resource Directory (RD)
organization. When the user refers to an account by its display name (alias)
rather than its UID, this skill resolves the alias first, then assumes into the
target account to execute the actual resource query.

## Scope Check Before You Start

This skill resolves the **cross-account routing layer only** — alias→UID,
plus the assume-role hop. If the user's actual request is a **multi-account
solution pattern** — key rotation across all members, drift / cost / RAM
audits, billing aggregation, organization-wide compliance scans — invoke
`alibabacloud-find-skills` first; a packaged multi-account-ops skill captures
the full workflow (iteration, error rollup, reporting), not just the
cross-account hop. Use this skill directly only when the user just needs the
routing primitive for a single-shot query. Full trigger conditions are in
`mcp-core-best-practices` → Skill Discovery.

## Prerequisites

- The current credentials must belong to an RD management account (or a delegated
  administrator) with `resourcedirectory:ListAccounts` permission.
- A cross-account assume role (default: `ResourceDirectoryAccountAccessRole`) must
  exist in target member accounts.

## Workflow

### 1. Determine Whether Cross-Account Access Is Needed

If the user explicitly provides an account ID (UID), skip to step 3.

If the user refers to an account by display name, alias, or any non-numeric
identifier, proceed to step 2 to resolve it.

### 2. Resolve Account Alias to UID

Use `AlibabaCloud___CallCLI` to list member accounts. The API returns at most 100
accounts per page, so always set `--page-size 100` and handle pagination when the
organization has more than 100 accounts:

```
aliyun resourcedirectorymaster list-accounts --page-size 100 --page-number 1
```

From the response, find the account whose `DisplayName` matches the user's input.
Extract its `AccountId` field — this is the UID needed for cross-account access.

If the target is not found in the first page, increment `--page-number` and continue
fetching until the target is found or all pages are exhausted (total account count is
returned in the response's `TotalCount` field).

If no match is found, report to the user and ask for clarification. Do not guess
account IDs.

### 3. Execute the Resource Query in the Target Account

When calling `AlibabaCloud___CallCLI` for the actual resource query, pass the
`x_assume_account_id` parameter with the resolved UID. This tells the MCP server
to assume into the target account before executing the command.

Example — list ECS instances in member account "dev-team":

```
# Step 1: Resolve "dev-team" to its UID
AlibabaCloud___CallCLI(command="aliyun resourcedirectorymaster list-accounts --page-size 100 --page-number 1")
# → find AccountId where DisplayName == "dev-team", e.g. "1234567890123456"
# → if not found and TotalCount > 100, continue with --page-number 2, 3, ...

# Step 2: Query resources in that account
AlibabaCloud___CallCLI(
  command="aliyun ecs describe-instances --region cn-hangzhou",
  x_assume_account_id="1234567890123456"
)
```

### 4. Present Results

Return the query results to the user. If the user asks about multiple accounts,
repeat steps 2–3 for each account, or iterate over all accounts from the
ListAccounts response.

## Parameter Reference

| Parameter | Description |
|-----------|-------------|
| `x_assume_account_id` | Target member account UID. The MCP server assumes into this account using the default cross-account role. |
| `x_assume_role_name` | Override the default role name if the target account uses a custom role (default: `ResourceDirectoryAccountAccessRole`). |
| `x_assume_role_arn` | Full ARN of the role to assume. Takes highest priority over account_id + role_name. |

## Error Handling

- **AccessDenied on ListAccounts**: The current credentials lack RD read
  permission. Ask the user to verify they are using the management account.
- **AssumeRole failed**: The target account may not have the expected role, or
  the role trust policy does not allow the current account. Report the error and
  suggest the user check the role configuration.
- **Account not found**: The display name does not match any member account.
  List available account names to help the user pick the correct one.

## Guardrails

- Always resolve aliases via the ListAccounts API. Never guess or hardcode
  account IDs.
- Do not cache account lists across conversations — accounts can be added or
  removed at any time.
- When iterating over multiple accounts, include the account display name and ID
  in the output so the user can verify correctness.
- Respect the principle of least privilege: only query the resources the user
  asked about, do not enumerate all resources in all accounts unless explicitly
  requested.
