---
name: alibabacloud-domain-website
description: Create and operate Wanxiaozhi AI websites through DomainCLI, including account quota, projects, conversations, generation, code, content, materials, plugins, preview, domain binding, certificates, deployment, rollback, site lifecycle, and analytics. Use for Wanxiaozhi project creation or management, AI site generation, preview or publishing, website domain and certificate setup, content assets, or site analytics.
license: Apache-2.0
source: https://gitlab.alibaba-inc.com/cloud-plugins-application/alibabacloud-domain
metadata:
  domain: aiops
  owner: aliyun-domain-team
  contact: keven.yef@alibaba-inc.com
  execution-surface: aliyun-domain-cli
  runtime-baseline: aliyun-3.5.1+_domaincli-0.9.8+
---

# Alibaba Cloud Domain Website

Read [DomainCLI runtime and safety contract](references/runtime.md) before ANY execution, including version checks, supplied-state decisions and final result fields. It is mandatory for each activation.

Use the bundled [local preflight helper](scripts/dependency_setup.py) as the single owner of version checks; do not repeat its checks manually. For a missing/outdated runtime or explicit user authorization for possible setup, read [Authorized dependency installation/update guide](references/dependency-setup.md) before using the setup flag. Actual explicit user/task-prompt authorization permits reviewed sandbox setup once, double-version verification, then resumption. Otherwise request setup authorization once and return awaiting_input/write_effect=none. Never install implicitly or treat setup consent as business-write approval.

## Workflow

1. Input: freeze supplied bizId, conversation/chat IDs, domain, channel and intended change. Resolve missing IDs only from successful scoped discovery with an unambiguous selector.
2. Judgment: select thematic wxz <theme> --operation <operation>. Before any publication preview, read project --operation show for the exact bizId and require structured same-project success. A project-not-found response ends blocked_target/write_effect=none, without preview, confirmation or publication. Verify the requested channel is supported without silently remapping it; then read relevant quota/binding/certificate/ICP prerequisites. Never substitute projects or widen plugin scope from mine to public.
3. Confirmation: creation/generation quota, deploy, rollback, offline, binding/certificate and destructive actions need successful same-target preview followed by a fresh user reply. Each material stage requires its own approval.
4. Execute: approved leaf once using documented flags. A cloud website-plugin operation is not permission to install local dependencies or execute downloaded content.
5. Readback: use same-project deploy --operation status or corresponding read within budget. Preview URL is not publication. site domain-icp changes display, not filing approval. DNS changes route to control with a separate anti-stale plan.
6. Deliver: exact project, preview/deployment state, safe IDs, channel and remaining handoff. Registration, filing, DNS, binding, certificate and live deployment are separate states.

## Load only relevant references

- [Friendly command map](references/cli-commands.md): choose the role-specific supported leaf; examples are documentation identifiers, not real fixtures.
- [RAM permissions](references/ram-policies.md): permission planning only, never grant automatically.
- [Skill identity manifest](references/manifest.json): name/version source for session attribution.

The runtime contract takes precedence over map examples: EVERY Agent-issued DomainCLI invocation requires session user-agent and cli-ai-mode. Help is allowed only once after an actual same-leaf compatibility error, never broad or preemptive help.
