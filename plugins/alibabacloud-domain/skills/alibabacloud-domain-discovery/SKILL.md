---
name: alibabacloud-domain-discovery
description: Check domain availability and reference prices, retrieve public WHOIS data, and answer domain policy or lifecycle questions through DomainCLI. Use when a user asks whether a domain is available, how much a domain or suffix may cost, who publicly operates a domain, or how domain rules work. Do not use for purchases, account assets, transfers, DNS changes, ICP filing, or website operations.
license: Apache-2.0
source: https://gitlab.alibaba-inc.com/cloud-plugins-application/alibabacloud-domain
metadata:
  domain: aiops
  owner: aliyun-domain-team
  contact: keven.yef@alibaba-inc.com
  execution-surface: aliyun-domain-cli
  runtime-baseline: aliyun-3.5.1+_domaincli-0.9.8+
---

# Alibaba Cloud Domain Discovery

Read [DomainCLI runtime and safety contract](references/runtime.md) before ANY execution, including version checks, supplied-state decisions and final result fields. It is mandatory for each activation.

Use the bundled [local preflight helper](scripts/dependency_setup.py) as the single owner of version checks; do not repeat its checks manually. For a missing/outdated runtime or explicit user authorization for possible setup, read [Authorized dependency installation/update guide](references/dependency-setup.md) before using the setup flag. Actual explicit user/task-prompt authorization permits reviewed sandbox setup once, double-version verification, then resumption. Otherwise request setup authorization once and return awaiting_input/write_effect=none. Never install implicitly or treat setup consent as business-write approval.

## Workflow

1. Input: freeze the exact user domain or suffix and requested public fact. Ask once for missing non-secret input; never substitute invented candidates.
2. Judgment: validate syntax and load the role command map. Choose only check, price, whois or ask. No identity reads for public checks.
3. Confirmation: read-only only, no payment/confirmation fields. Route explicit acquisition intent to commerce instead of performing it here.
4. Execute: invoke the verified friendly leaf with session attribution; advance only on structured same-target success.
5. Readback: validate returned target/source/currency/quote type. Availability, reference price, marketplace listing and WHOIS are separate facts. available=false does not prove a listing; WHOIS does not prove account ownership.
6. Deliver: chat summary with target, separate availability and price/policy/WHOIS evidence, uncertainty and write_effect=none. A reference price is not a final quote or charge.

## Load only relevant references

- [Friendly command map](references/cli-commands.md): choose the role-specific supported leaf; examples are documentation identifiers, not real fixtures.
- [RAM permissions](references/ram-policies.md): permission planning only, never grant automatically.
- [Skill identity manifest](references/manifest.json): name/version source for session attribution.

The runtime contract takes precedence over map examples: EVERY Agent-issued DomainCLI invocation requires session user-agent and cli-ai-mode. Help is allowed only once after an actual same-leaf compatibility error, never broad or preemptive help.
