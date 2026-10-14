---
name: alibabacloud-domain-icp
description: Provide China ICP filing guidance, open the official filing workflow, query filing-order progress, and retrieve successful filing records through DomainCLI. Use when a user asks about ICP policy, materials, eligibility, an official filing entry, an in-progress filing, or an approved filing record. Do not use for website filing-number display, website publication, DNS changes, or domain identity templates.
license: Apache-2.0
source: https://gitlab.alibaba-inc.com/cloud-plugins-application/alibabacloud-domain
metadata:
  domain: aiops
  owner: aliyun-domain-team
  contact: keven.yef@alibaba-inc.com
  execution-surface: aliyun-domain-cli
  runtime-baseline: aliyun-3.5.1+_domaincli-0.9.8+
---

# Alibaba Cloud Domain Icp

Read [DomainCLI runtime and safety contract](references/runtime.md) before ANY execution, including version checks, supplied-state decisions and final result fields. It is mandatory for each activation.

Use the bundled [local preflight helper](scripts/dependency_setup.py) as the single owner of version checks; do not repeat its checks manually. For a missing/outdated runtime or explicit user authorization for possible setup, read [Authorized dependency installation/update guide](references/dependency-setup.md) before using the setup flag. Actual explicit user/task-prompt authorization permits reviewed sandbox setup once, double-version verification, then resumption. Otherwise request setup authorization once and return awaiting_input/write_effect=none. Never install implicitly or treat setup consent as business-write approval.

## Workflow

1. Input: distinguish policy, filing entry, progress and successful-record query; freeze supplied domain/order identifiers. Ask once for missing non-secret identifiers.
2. Judgment: select icp ask, fill, status or info. fill opens the official filing workflow only; it does not create or submit a filing.
3. Confirmation: advice/status reads need no write approval. Personal information entry and human verification remain in the official workflow; never collect identity documents or codes in chat.
4. Execute: run the verified attributed friendly leaf for the frozen scope, not raw Beian/Company Registration APIs or browser automation.
5. Readback: interpret matching returned order state and safe ID. Browser-opened, accepted, pending review and approved are distinct; do not poll manual review indefinitely.
6. Deliver: sanitized progress, next responsible party and safe resume identifier. Unknown remains unknown; no approval claim without explicit same-target evidence.

## Load only relevant references

- [Friendly command map](references/cli-commands.md): choose the role-specific supported leaf; examples are documentation identifiers, not real fixtures.
- [RAM permissions](references/ram-policies.md): permission planning only, never grant automatically.
- [Skill identity manifest](references/manifest.json): name/version source for session attribution.

The runtime contract takes precedence over map examples: EVERY Agent-issued DomainCLI invocation requires session user-agent and cli-ai-mode. Help is allowed only once after an actual same-leaf compatibility error, never broad or preemptive help.
