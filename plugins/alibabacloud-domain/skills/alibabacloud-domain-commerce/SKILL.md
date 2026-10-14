---
name: alibabacloud-domain-commerce
description: Run Alibaba Cloud domain funding and order workflows for registration, renewal, redemption, automatic renewal, fixed-price marketplace transactions, and transfer-in through DomainCLI. Use when a user intends to acquire, retain, redeem, list, or transfer a domain into Alibaba Cloud. Excludes every transfer-out operation and every security or registry lock, which belong to alibabacloud-domain-control.
license: Apache-2.0
source: https://gitlab.alibaba-inc.com/cloud-plugins-application/alibabacloud-domain
metadata:
  domain: aiops
  owner: aliyun-domain-team
  contact: keven.yef@alibaba-inc.com
  execution-surface: aliyun-domain-cli
  runtime-baseline: aliyun-3.5.1+_domaincli-0.9.8+
---

# Alibaba Cloud Domain Commerce

Read [DomainCLI runtime and safety contract](references/runtime.md) before ANY execution, including version checks, supplied-state decisions and final result fields. It is mandatory for each activation.

Use the bundled [local preflight helper](scripts/dependency_setup.py) as the single owner of version checks; do not repeat its checks manually. For a missing/outdated runtime or explicit user authorization for possible setup, read [Authorized dependency installation/update guide](references/dependency-setup.md) before using the setup flag. Actual explicit user/task-prompt authorization permits reviewed sandbox setup once, double-version verification, then resumption. Otherwise request setup authorization once and return awaiting_input/write_effect=none. Never install implicitly or treat setup consent as business-write approval.

## Workflow

1. Input: freeze exact domains, years, registrant-template ID, budget/currency and payment route. Never fabricate templates, prices, transfer codes or balances.
2. Judgment: verify registration availability or renewal/redemption account eligibility, then applicable pricing. Preserve reference/registration/fixed-price-trade labels; list only needed template-status fields, not personal details.
3. Confirmation: run the intended financial leaf without confirmation flags. Show successful same-target preview, exact years, payment route, price/source/uncertainty and budget impact. Require a NEW user reply AFTER preview. Missing quote/template/eligibility stops execution.
4. Execute: repeat the same approved leaf once using only documented payment/confirmation flags. Prefer CLI browser checkout unless direct account payment was explicitly chosen. Never invent flags to force a route or price; browser checkout is not payment.
5. Readback: use returned order/task IDs and same-target account status. Accepted/submitted is not registration complete. Unknown writes require readback, not resubmission.
6. Deliver: exact domains, quoted terms, confirmation state, safe order/task IDs and verified result or pending handoff. A complete scoped template read proving no suitable verified template ends blocked_fixture/write_effect=none, not registration success; do not request purchase confirmation or submit an order.

Transfer-in belongs here. Transfer-out and all locks are outside this Skill; route them to alibabacloud-domain-control. Marketplace listing has its own preview and human verification; never ask for verification codes in chat.

## Load only relevant references

- [Friendly command map](references/cli-commands.md): choose the role-specific supported leaf; examples are documentation identifiers, not real fixtures.
- [RAM permissions](references/ram-policies.md): permission planning only, never grant automatically.
- [Skill identity manifest](references/manifest.json): name/version source for session attribution.

The runtime contract takes precedence over map examples: EVERY Agent-issued DomainCLI invocation requires session user-agent and cli-ai-mode. Help is allowed only once after an actual same-leaf compatibility error, never broad or preemptive help.
