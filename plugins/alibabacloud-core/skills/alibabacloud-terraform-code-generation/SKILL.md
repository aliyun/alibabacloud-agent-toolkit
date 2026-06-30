---
name: alibabacloud-terraform-code-generation
description: |
  Use when the user wants Terraform HCL for Alibaba Cloud (Alicloud) infrastructure —
  new project or extending an existing one. Covers VPC, ECS, ApsaraDB RDS, OSS,
  SLB / ALB, Function Compute v3, ACK, and any other `alicloud_*` resource via the
  provider documentation and IaCService metadata. IaCService API calls must go
  through the alibabacloud-core MCP CallCLI tool. For AWS → Alicloud migration,
  importing existing resources into state, or remote plan/apply execution, use
  a different skill.
  Triggers: "write terraform for alicloud", "generate alibaba cloud terraform",
  "alicloud HCL", "create alibaba cloud vpc/ecs/rds", "生成阿里云 Terraform",
  "阿里云 HCL", "用 Terraform 部署阿里云", "alicloud provider", "aliyun/alicloud",
  "terraform-provider-alicloud".
---

# Alibaba Cloud Terraform Code Generation

Turn natural-language Alibaba Cloud infrastructure requirements into validated
Terraform for the current `aliyun/alicloud` provider. Resource schema and
validation are resolved through IaCService via MCP; Terraform provider docs and
local reference files are used for HCL argument shape, examples, deprecations,
and product-specific guardrails.

## Hard rules (never violate)

### 1. Credentials — never leak, never require

NEVER read, print, ask for, or write AK/SK values anywhere — HCL, comments, env
declarations, shell output, logs. The alicloud provider resolves credentials
through seven mechanisms (env AK/SK, shared `config.json`, ECS instance RAM
role, Assume Role, OIDC/RRSA, sidecar URI, static HCL) — see
`references/auth-and-network.md` for the full chain. All read by the provider
itself, never by this skill. Do NOT recommend the deprecated `ALICLOUD_*` /
`ALIBABACLOUD_*` (no-underscore) env-var names — the current names are
`ALIBABA_CLOUD_ACCESS_KEY_ID` / `_ACCESS_KEY_SECRET` / `_SECURITY_TOKEN`.

### 2. Honest reporting — never claim a step you didn't run

Never report `fmt: ok` / `validate: ok` / `plan: ok` unless the corresponding
command actually executed AND returned that status. When a step is skipped
(tool missing, user opt-out), state **"SKIPPED"** (or **"FAILED"**) with a
reason. Paraphrasing real output is fine; fabricating it is not.

### 3. No local `terraform` execution

This skill NEVER runs `terraform` locally — not `fmt`, `init`, `validate`,
`plan`, or `apply`. Validation routes through MCP (Step 6, `aliyun
iacservice validate-module` via `AlibabaCloud___CallCLI`). Plan and apply
belong to the user's deployment workflow or the `alibabacloud-spec-ops`
execution skill, not this standalone code-generation skill.

## Environment (soft recommendations)

- **MCP** — the `alibabacloud-core` MCP server must be reachable; all
  IaCService API calls go through `AlibabaCloud___CallCLI`. Do NOT call local
  `aliyun` or helper scripts for IaCService.
- **IaCService endpoint** — use `--endpoint iac.cn-zhangjiakou.aliyuncs.com`
  for all IaCService commands. Do NOT derive endpoints from `region`.
- **No local Terraform dependency** — validation uses remote IaCService
  `validate-module`; no local `terraform` binary is required.

## Workflow

### Step 1. Parse requirement

Extract:

- `region` — default `cn-hangzhou`.
- `resources[]` — `{ alicloud_type, quantity, attributes }`.
- Non-functional: multi-AZ, encryption, backup, HA, IOPS.

If ambiguous (e.g. "搭个数据库"), ask **at most one** clarifying question.

### Step 2. Resolve target directory

Extract `<target-dir>` from the user's request (explicit path like
`myshop-infra/` or current working directory if unspecified). All subsequent
file writes and static HCL checks operate in this directory. Remote validation
submits the files from this directory through MCP/IaCService.

Before writing any `.tf` file, **MUST** create the directory:

```bash
mkdir -p <target-dir>
```

All file writes MUST prefix paths with `<target-dir>/` — never write to
the current working directory directly, never write to a generic `outputs/`
parent. After generation completes, verify the structure:

```bash
ls -R <target-dir>
```

### Step 3. Sketch architecture

Before any HCL, sketch a dependency table — one row per resource:

| resource | depends on | AZ / placement |
| --- | --- | --- |

- Expand `resources[]` with implied infra (VPC → VSwitch → SecurityGroup
  → workload); user parse often skips these.
- The expanded list is the input to Step 4's gate.

### Step 4. Pre-HCL gate (MANDATORY)

For every distinct `alicloud_*` type from Step 3 (resources **and** data
sources), execute 4.1 → 4.2 → 4.3. Before running any lookup, build a
task-local lookup cache:

- `types[]` — de-duplicated final resource/data-source names from Step 3.
- `catalog[type]` — local catalog row and provider doc URL.
- `product[type]` — IaCService product when it can be determined from
  IaCService metadata or resource naming.
- `resource_type[type]` — IaCService schema response or failure.
- `example[type]` — selected IaCService example code, only when useful.
- `provider_doc[type]` — GetProviderDocument result or fallback doc, only when needed.

Never repeat the same IaCService call, catalog grep, pattern lookup, or provider
doc fetch for the same key. Run independent lookups in parallel: `list-products`,
catalog grep, pattern grep; then parallelize per-type `get-resource-type`.

#### 4.1 Pre-doc lookup (MCP metadata + catalog + patterns, in parallel)

Run the live MCP metadata lookup and local targeted lookups before writing HCL.
Optimize for one pass over each unique key:

**(a) IaCService metadata via MCP** — when `AlibabaCloud___CallCLI` is exposed
in the session, you MUST attempt live metadata lookup. Do NOT silently skip this
step. Do NOT run these commands in a local shell.

Use this de-duplicated call plan:

1. Call `list-products` once per generation task.
2. Determine each type's product from metadata, resource naming, or task cache.
3. Call `get-resource-type` once per final distinct `alicloud_*` type after
   deprecation routing; this is mandatory when CallCLI is available.
4. Call `list-resource-types` only when product/resource type cannot be inferred.
5. Call example APIs only for complex/nested resources, incomplete metadata, or
   Step 6 diagnostics that cannot be fixed from metadata plus local references.

```bash
aliyun iacservice list-products --endpoint iac.cn-zhangjiakou.aliyuncs.com
aliyun iacservice get-resource-type --resource-type alicloud_<name> --endpoint iac.cn-zhangjiakou.aliyuncs.com

# Conditional only:
aliyun iacservice list-resource-types --product <Product> --endpoint iac.cn-zhangjiakou.aliyuncs.com
aliyun iacservice list-resource-type-examples --resource-type alicloud_<name> --endpoint iac.cn-zhangjiakou.aliyuncs.com
aliyun iacservice get-resource-type-example --example-id <exampleId> --endpoint iac.cn-zhangjiakou.aliyuncs.com
```

Use metadata for product/resource availability, required attributes, enum
values, defaults, sensitivity, ForceNew, and Computed constraints when present.
For every distinct type, record one of these metadata statuses for Step 4.3 and
Step 7:

- `ok` — include the product/resource type and the schema source returned by
  IaCService.
- `failed` — include the attempted command/API and the concise failure reason;
  continue with provider docs plus the local catalog.
- `skipped` — only allowed when the `AlibabaCloud___CallCLI` tool is not
  exposed in the current session; include that exact reason.

Never report `metadata constraints: SKIPPED` if CallCLI was available but you
did not try the IaCService command. That is a workflow failure; go back and run
the metadata lookup. If a CallCLI invocation fails, record the failure as
evidence and continue with provider docs plus the local catalog; do not
simulate API results.

Two local lookups; **run them concurrently** with the live metadata lookup:

**(b) Catalog lookup** — confirm the resource exists and check deprecation.
The catalog (`references/alicloud-providers.md`) is ~2600 lines; **do NOT
`Read` it whole**. Use exact table-row grep per requested type; avoid substring
patterns such as `alicloud_(vpc|instance)` because they overmatch:

```bash
for type in alicloud_vpc alicloud_vswitch alicloud_instance; do
  grep -E '^\| (resource|data source) \| `'"$type"'` \|' references/alicloud-providers.md
done
```

If a single type or routed replacement needs a follow-up:

```bash
grep -E '^\| (resource|data source) \| `alicloud_<name>` \|' references/alicloud-providers.md
```

Three outcomes:

- **Row found, status column empty** → note the `[doc](<url>)` from the row;
  proceed to 4.2.
- **Row found, status `DEPRECATED -> <new_name>`** → switch the plan to
  `<new_name>` and re-lookup. NEVER emit the deprecated name. Common catch:
  `alicloud_fc_function` → `alicloud_fcv3_function`.
- **Row found, status `DEPRECATED` without replacement** → stop and ask for a
  supported alternative; do not emit the deprecated resource/data source.
- **Row not found** → stop. Ask the user whether the name was a typo;
  don't invent an `alicloud_<guess>`.

**(c) Pattern lookup** (conditional) — if the user's requirement matches a
product-specific idiom listed in `references/resource-patterns.md` (e.g.
RDS cross-AZ HA, OSS lifecycle noncurrent, VPC peering), read the
relevant section. These idioms are NOT in the provider doc's *Required*
list but are what the user actually wants (e.g. `zone_id_slave_a` for RDS
HA is optional per the doc but required for real cross-AZ placement).
Missing them produces "validates but silently wrong" output.

When a matching pattern section is found, **ALL attributes listed in that
section's "Required attributes" table MUST appear in the generated HCL**
— treat them as mandatory even if the provider doc marks them Optional.

```bash
# Quick check whether a relevant pattern exists, then Read only the section:
grep -inE "<keyword1>|<keyword2>" references/resource-patterns.md
```

Run one pattern grep for the user's product keywords, not one grep per
resource, then cache any matching sections.

#### 4.2 Provider doc fallback (metadata-first)

Do NOT fetch provider docs when IaCService metadata and selected official
examples from 4.1 contain enough schema and usage shape for HCL generation.
Provider doc fetch is not a default phase; running WebFetch on the fast path is
a workflow failure.

Fetch provider docs only when metadata is unavailable/incomplete for the user's
requirement, examples are absent/insufficient, Step 6 diagnostics cannot be
fixed from metadata plus local references, or the user explicitly asks for docs.

When docs are needed, call IaCService `get-provider-document` through MCP first.
Use `--endpoint iac.cn-zhangjiakou.aliyuncs.com`, call once per distinct type,
and cache `provider_doc[type]`.

If `get-provider-document` fails, fall back to the catalog GitHub URL/raw URL.
If all documentation channels fail, use the local catalog plus IaCService
metadata from 4.1 and prefix recitation with
`doc unreachable: used metadata/local catalog`.

#### 4.3 Recite (proof-of-read)

Before writing HCL, emit a compact per-resource brief:

- **Required param names only** from IaCService metadata/doc/local fallback
- **2–5 key Optional/nested params** relevant to the user's requirement
- **Non-obvious pattern attrs** from `resource-patterns.md`, if any
- **Metadata constraints** from IaCService, or `metadata constraints: SKIPPED
  (<reason>)` / `metadata constraints: FAILED (<reason>)`
- **Metadata evidence** — attempted IaCService command/API for this type and
  its status (`ok`, `failed`, or `skipped`). If this line is missing, Step 4 is
  incomplete and HCL generation must not start.
- **Doc evidence** — `not fetched (metadata sufficient)` on the fast path, or
  the provider doc/raw URL when 4.2 fetched documentation.

If Required or Optional params are missing, return to 4.2. Skipping or using
a partial recitation is a hard failure; metadata/doc failure uses local catalog
fallback, not memory.

### Step 5. Generate

#### 5.1 Write HCL from the recitations, not memory

Use ONLY the params established in 4.3. If you need a param that wasn't in the
recited brief, re-fetch 4.2 with a deeper read; do not guess.
Use the fastest batch write method allowed by the host client (single batch
edit, script, or heredoc); avoid serial per-file writes unless required.

Before writing a field, look up the resource in
`references/deprecated-fields.md` (see §5.5 handling rules):

```bash
grep '`alicloud_<resource>`' references/deprecated-fields.md
```

If the user's requirement touches a product with a specific usage pattern
(e.g. RDS cross-AZ HA, VPC peering, OSS lifecycle), also consult
`references/resource-patterns.md` for the non-obvious attributes.

#### 5.2 Data-source enforcement (MANDATORY — no hardcoded IDs)

Resolve via `data` blocks, never literals. These also pass Step 4's gate:

- `zone_id` → `data "alicloud_zones"` (filter by `available_resource_creation`).
- `image_id` → `data "alicloud_images"` (filter by `name_regex`, `owners = "system"`, `most_recent = true`).
- `instance_type` → `data "alicloud_instance_types"` (filter by `cpu_core_count`, `memory_size`, AZ).

Generate `variables.tf` for all `variable` blocks; every generated `var.*`
MUST have type and description. Generate `outputs.tf` for useful non-sensitive
resource IDs, endpoints, and names. Terraform merges all `*.tf` equivalently.

#### 5.3 Provider block (content contract)

Two Terraform blocks must appear **somewhere** in the project's `*.tf`
files. Terraform merges all `*.tf` in a directory, so *file organization
is a style choice, not a contract* — see "File organization" below.

**Block 1 — `terraform { required_providers {} }`**:

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.274"
    }
  }
}
```

- Provider version: resolve the latest published stable `aliyun/alicloud` 1.x
  version through IaCService metadata when available, then write a pessimistic
  minor constraint (`1.278.0` -> `~> 1.278`).
  Lookup sources, in order:
  1. MCP `AlibabaCloud___CallCLI` with `aliyun iacservice list-terraform-provider-versions`
     if supported by the installed MCP/proxy version.
  2. MCP `AlibabaCloud___CallCLI` metadata responses that include provider
     version information.
  3. Provider registry/GitHub release metadata only when the host client has an
     explicit safe documentation fetch mechanism.
- If lookup fails, fall back to `~> 1.274`. Accepted form is `~> 1.<minor>`
  from a confirmed or conservative stable 1.x release. Do NOT write open-ended
  constraints (`>= 1.x`, `>= 1.239.0`) or bare version strings.

**Block 2 — `provider "alicloud" {}`** with BOTH `region = var.region`
and `configuration_source`:

```hcl
provider "alicloud" {
  region               = var.region
  configuration_source = "AlibabaCloud-Agent-Toolkit/alibabacloud-core"
}
```

- `configuration_source` is the attribution signature — required.
- `region` MUST reference `var.region`, not a hardcoded literal.

**File organization (recommended, not required)**: conventional split is
`terraform.tf` (Block 1) + `providers.tf` (Block 2). Also acceptable:
a single `versions.tf` containing both blocks, or either block at the
top of `main.tf`. Pick what fits the project — Terraform merges all
`*.tf` equivalently. Do NOT add a filename check; run the content check
below instead.

**Post-generation verification:** read `references/static-checks.md` and run
the Provider Block Check. All three checks must return `OK`. If any fails, fix
the offending content and re-run — do NOT proceed to Step 6 with failures.

#### 5.4 Style baseline

- 2-space indent; `=` aligned within a block; snake_case semantic resource labels
  (`alicloud_vswitch.app_a`, not `vsw1`).
- Every tag-supporting resource should carry a non-empty `tags` block for ops
  hygiene — pick reasonable keys for the scenario (common choices:
  `ManagedBy`, `Project`, `Environment`, `CreatedBy`). Skill does not
  prescribe specific tag keys or values.

#### 5.5 Deprecated-field audit — static grep pass (MANDATORY)

Run before `terraform` is needed — this is a pure-grep pass on the HCL you
just wrote. For every resource in this generation, grep the project against
`references/deprecated-fields.md` and handle each row-kind:

- **rename** row → if the old field name appears in HCL you just wrote,
  replace it with the new field name. Examples that show up most often:
  - `alicloud_ram_role`: `name` → `role_name`,
      `document` → `assume_role_policy_document`
  - `alicloud_security_group`: `name` → `security_group_name`
  - `alicloud_db_database`: `name` → `data_base_name`
- **split / soft-split** row → do NOT write the inline field on the parent.
  Declare the replacement sub-resource only when the user's requirement
  needs that capability, or when `references/resource-patterns.md` says the
  sub-resource has an explicit safe default. Example: for OSS buckets,
  `alicloud_oss_bucket_acl` defaults to `private`, but logging/CORS/website
  sub-resources are omitted unless the user asks for those features.
- **deprecated-no-replacement** row → stop using the field, no substitute.

Applies only to files written in this generation — do NOT refactor
pre-existing user files you weren't asked to touch.

**HARD GATE: must pass before Step 6** — read
`references/static-checks.md` and run the Deprecated Field Audit. If it produces
any `DEPRECATED:` line, fix using the Action column in
`references/deprecated-fields.md`, then re-run until every line returns `OK:`.
Do NOT proceed to Step 6 with any `DEPRECATED:` output. Do NOT claim
"verified" unless the script produces all `OK:`.

### Step 6. Validate via IaCService (remote, MCP)

NEVER run `terraform fmt`, `terraform init`, or `terraform validate`
locally. Validation runs server-side through the available MCP tool ending in
`AlibabaCloud___CallCLI` with `aliyun iacservice validate-module`. The IaCService backend performs
Terraform syntax and schema validation without requiring a local
Terraform binary, network access to `registry.terraform.io`, or backend init.
Always use the fixed Zhangjiakou endpoint:
`--endpoint iac.cn-zhangjiakou.aliyuncs.com`. Do NOT use the Terraform
resource region (for example `cn-hangzhou`) as the IaCService endpoint region.

Read `references/iacservice-cli.md` for exact syntax. Prefer the fast path:
concatenate generated `.tf` files in memory and submit one `--code` payload.
Use `--code-map` only when filename-specific diagnostics are needed or `--code`
fails unexpectedly. Generate a fresh UUID `--client-token` per call.

**Loop until validate passes** (max 3 fix attempts total):

1. Parse the IaCService response. If there are **errors / diagnostics with
   severity `error`** → fix the offending file in `<target-dir>/`,
   regenerate the `--code` or `--code-map` payload, then go to step 3.
2. Scan the response diagnostics for `[DEPRECATED]` strings. The provider
   emits authoritative deprecation annotations (e.g. `"document":
   "[DEPRECATED] … New field 'assume_role_policy_document' instead."`).
   If found → fix the matching field, then go to step 3.
3. Re-invoke `aliyun iacservice validate-module` via
   `AlibabaCloud___CallCLI` and go back to step 1.

Exit the loop only when validate reports **no errors AND no `[DEPRECATED]`
diagnostics**. After 3 attempts without reaching this state: proceed to
Step 7 with `Validation: FAILED (<diagnostic excerpt>)` and include the
failing HCL verbatim in the optional notes.

**If the MCP CallCLI fails** (auth, network to OpenAPI endpoint, or
IaCService backend unavailable): do NOT fall back to local `terraform
validate`. SKIP this step and surface the failure in Step 7's summary
(Hard rule §2) with
`Validation: SKIPPED (iacservice validate-module unavailable — <reason>)`.

### Step 7. Coverage check + summarize

**MANDATORY — runs regardless of generation outcome.** The `Files written:`,
`IaCService metadata:`, `Validation:`, and `Deprecation routing:` labels are
the final contract; do not skip or rename them.

**Coverage check.** Enumerate resource blocks in the generated HCL and compare
with Step 3's sketch. If any row is missing, return to Step 5, add it, then
rerun Step 5 checks and Step 6; do not skip implicit resources.

**Summary template** — print in the user's language, using this structure:

```
Files written:
<path/to/file1>
<path/to/file2>
...

IaCService metadata: <ok | SKIPPED (CallCLI tool not exposed) | FAILED (<reason>)>

Validation: <iacservice validate-module: ok | SKIPPED (...) | FAILED (...)>

Deprecation routing: <If re-routed: `<original_name>` → `<new_name>`; else: None>

<optional architecture notes, design decisions, deploy hints>
```

Allowed `Validation:` values:

- `Validation: iacservice validate-module: ok`
- `Validation: SKIPPED (iacservice validate-module unavailable — <reason>)`
- `Validation: SKIPPED (<reason>)`
- `Validation: FAILED (<diagnostic excerpt>)`

`IaCService metadata:` summarizes Step 4.1 only. Use `ok` only when every
generated resource/data source had successful metadata lookup; use
`SKIPPED (CallCLI tool not exposed)` only when CallCLI is unavailable; otherwise
use `FAILED (<reason>)`.

### Step 8 (internal). Where execution belongs — DO NOT narrate to user

After Step 7, stop. Do not run plan/apply. Do not expose orchestration phrases
such as "returning control", "handoff", or "upstream caller". If the user asks
to deploy, point to their normal Terraform workflow or
`alibabacloud-spec-ops:alibabacloud-executing-plans`.

## References

| Source | When to read |
| --- | --- |
| `references/alicloud-providers.md` (local) | Step 4.1 — resource existence, deprecation mark, doc URL |
| OSS provider doc mirror, then catalog GitHub/raw URL | Step 4.2 — fallback docs for HCL argument shape and examples |
| `references/iacservice-cli.md` | IaCService command/parameter reference for Step 4.1 and Step 6 |
| `references/deprecated-fields.md` (local) | Step 5.1 + Step 5.5 — field-level deprecations not always flagged by IaCService |
| `references/resource-patterns.md` (local) | Step 5.1 — product-specific idioms not emphasized by the provider doc (RDS HA, …) |
| `references/static-checks.md` | Step 5.3 + Step 5.5 — provider block and deprecated-field verification scripts |
| `references/auth-and-network.md` (local) | Background credential chain reference; this skill does not consume credentials |
