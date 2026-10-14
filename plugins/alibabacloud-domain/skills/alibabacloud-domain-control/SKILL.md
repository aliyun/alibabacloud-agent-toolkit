---
name: alibabacloud-domain-control
description: Inspect and control Alibaba Cloud domain assets, groups, remarks, contacts, registrant templates, verification, DNS records, Glue Records, DNSSEC, nameservers, transfer-out, audit history, and all domain locks through DomainCLI. Use for account-owned domain management, DNS or identity changes, transfer-out, or any transfer, update, server, registry, or security lock. Excludes registration, renewal, redemption, marketplace funding, and transfer-in.
license: Apache-2.0
source: https://gitlab.alibaba-inc.com/cloud-plugins-application/alibabacloud-domain
metadata:
  domain: aiops
  owner: aliyun-domain-team
  contact: keven.yef@alibaba-inc.com
  execution-surface: aliyun-domain-cli
  runtime-baseline: aliyun-3.5.1+_domaincli-0.9.8+
---

# Alibaba Cloud Domain Control

Read [DomainCLI runtime and safety contract](references/runtime.md) before ANY execution, including version checks, supplied-state decisions and final result fields. It is mandatory for each activation.

Use the bundled [local preflight helper](scripts/dependency_setup.py) as the single owner of version checks; do not repeat its checks manually. For a missing/outdated runtime or explicit user authorization for possible setup, read [Authorized dependency installation/update guide](references/dependency-setup.md) before using the setup flag. Actual explicit user/task-prompt authorization permits reviewed sandbox setup once, double-version verification, then resumption. Otherwise request setup authorization once and return awaiting_input/write_effect=none. Never install implicitly or treat setup consent as business-write approval.

## Workflow

1. Input: freeze exact domain, record/template/group/task ID and desired action/delta; never replace a supplied ID with another visible resource.
2. Judgment: read the exact account asset before contact, ownership, lock, transfer-out or nameserver changes. Public WHOIS is not ownership. For an exact Alidns zone/record supplied by the user, use dns list/detail directly: DNS hosting is independent of registrar ownership. An exact-record not-found response ends blocked_target/write_effect=none before preview or confirmation; failed runtime/auth/permission checks are not evidence of absence.
3. Confirmation: show successful same-target preview with exact delta, risk and recovery limits. DNS needs a usable returned plan_id before a fresh post-preview user reply. A failed output mentioning plan_id is not a preview.
4. Execute: one approved write only. DNS repeats the same leaf with --confirm=true, --confirm-domain set to the frozen domain and --plan-id set to the returned plan. Other leaves use only documented flags. No implicit delete/create or permission expansion.
5. Readback: reread the SAME record/asset/task and check target/value/TTL/type/line as applicable. Preserve no_change when state matches. A write timeout triggers readback, not retry.
6. Deliver: requested versus saved state, safe task IDs and remaining action. DNS control-plane persistence is not global propagation.

Own transfer-out and all domain locks. Transfer-in belongs to `alibabacloud-domain-commerce`. Keep nameserver delegation, Alidns records, Glue Records and DNSSEC distinct.

## Load only relevant references

- [Friendly command map](references/cli-commands.md): choose the role-specific supported leaf; examples are documentation identifiers, not real fixtures.
- [RAM permissions](references/ram-policies.md): permission planning only, never grant automatically.
- [Skill identity manifest](references/manifest.json): name/version source for session attribution.

The runtime contract takes precedence over map examples: EVERY Agent-issued DomainCLI invocation requires session user-agent and cli-ai-mode. Help is allowed only once after an actual same-leaf compatibility error, never broad or preemptive help.
