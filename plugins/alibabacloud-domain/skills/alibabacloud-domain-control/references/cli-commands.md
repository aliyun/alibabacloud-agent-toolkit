# Friendly DomainCLI commands

Use only this Skill-owned subset. Mandatory runtime constraints override examples. Every Agent-issued call includes session attribution and cli-ai-mode. No broad/preemptive help; same-leaf help once only after an actual compatibility error.

## Read and discover

| User intent | Command | Notes |
|---|---|---|
| List account domains | `aliyun domain list` | Supports pagination, sorting, domain, group, and auto-renew filters. |
| Show one account domain | `aliyun domain detail --domain example.com` | Account asset detail, not public WHOIS. |
| Filter domain assets | `aliyun domain search` | Use for richer account-side search. |
| Check registration availability | `aliyun domain check --domain example.com` | Public, read-only; never implies price or purchase. |
| Query registration or renewal reference price | `aliyun domain price --domain example.com` | A registered domain may return a fixed-price marketplace quote. Preserve `quote_type` and never label it a registration fee. |
| Query suffix reference price | `aliyun domain price --suffix com --years 1` | Public reference price, not an account-specific final quote. |
| Query public registration data | `aliyun domain whois --domain example.com` | Public WHOIS/RDAP lookup, separate from account contact data. |
| Ask domain-industry knowledge | `aliyun domain ask --question "域名过期后多久进入赎回期？"` | Advice only; it does not inspect account state. |
| Review domain operation history | `aliyun domain history` | Read-only account history. |
| Inspect asynchronous tasks | `aliyun domain task ...` | Use the relevant task leaf to track submitted operations. |

Do not infer that `available=false` means a marketplace listing exists. Let `price --domain` report whether it found a fixed-price listing and preserve its source label.

Discovery and detail are separate steps. Query details only for identifiers actually returned by a successful discovery, and only when relevant: `task show` needs a task ID; transfer-in detail needs the returned instance ID; verification failure details need a failed review target. A successful empty list is valid data. Report zero matching results in the queried scope and stop dependent steps, rather than inventing an identifier or changing filters repeatedly to manufacture a result. Listing templates does not require reading every contact field.


## Identity and ownership data

| User intent | Command group | Notes |
|---|---|---|
| Read domain contacts | `aliyun domain contact` | The current CLI preserves the OpenAPI response without client-side masking or field pruning. Return only the private-data output allowlist from `references/runtime.md`; omit all other personal fields. |
| Apply a registrant template | `aliyun domain set-contact` | Ownership-affecting write; preview and confirm. |
| Manage registrant templates | `aliyun domain template ...` | Use `list`, `create`, `update`, `delete`, `set-default`, `regions`, `validate`, or `verify`. Sensitive inputs belong in permission-restricted local files when the CLI supports them. |
| Check real-name verification | `aliyun domain verification ...` | Read verification state or follow the exact verified workflow. |
| Manage email verification | `aliyun domain email ...` | Use list, detail, request, resend, confirm, or delete leaves. Do not expose email tokens. |

Do not combine identity changes with purchase, transfer, or DNS changes into one confirmation. Each material action needs its own preview and decision.


## Organize and protect assets

| User intent | Command group |
|---|---|
| Manage groups | `aliyun domain group list`, `create`, `rename`, `move`, or `delete` |
| Set remarks | `aliyun domain remark` |
| Manage transfer prohibition | `aliyun domain transfer-lock` |
| Manage update prohibition | `aliyun domain update-lock` |
| Manage secure transfer-out | `aliyun domain transfer-out ...` |
| Manage registry server lock | `aliyun domain server-lock ...` |
| Set registry nameservers | `aliyun domain nameserver set` |

Before contact, lock, transfer-out, server-lock, or nameserver writes, run account-side `aliyun domain detail` for the exact domain. The returned domain must exactly match the user target and prove that the intended Alibaba Cloud account can manage it. Public WHOIS/RDAP proves public registration state only; it is never account ownership or write-authority evidence. If the domain is absent, registered elsewhere, inaccessible, or returned under another identifier, stop without previewing or writing.

Nameserver delegation is not a DNS record edit. It can interrupt all website and mail resolution, so validate account applicability, inspect current delegation with `detail`, preview the change, obtain confirmation, submit once, then read back the saved configuration. Do not redirect the request to another registrar or DNS provider from this Skill.

For groups and remarks, resolve group IDs from `group list` and freeze each requested target. Renaming needs both the existing group and the user-provided new name. For multiple preview-only actions, show each successful preview separately and state which steps are blocked or `no_change`; do not ask for executable confirmation for a missing/failed preview.


## DNS command selection

Choose by resource type:

| Resource | Command group | Meaning |
|---|---|---|
| Alibaba Cloud DNS zone records | `aliyun domain dns ...` | A, AAAA, CNAME, MX, TXT, NS, SRV, and CAA records hosted by Alidns. |
| Registry Glue Records | `aliyun domain dnshost ...` | Child-host records registered at the registry. |
| Registry DNSSEC DS records | `aliyun domain dnssec ...` | DS records for registry delegation. |
| Registry authoritative nameserver delegation | `aliyun domain nameserver set` | Which nameservers are authoritative for the domain. |

DNS record reads include `list`, `detail`, `lines`, and `logs`. DNS record writes include `create`, `update`, `enable`, `disable`, and `delete`.

Leaf flags are not interchangeable: `dns list --domain` selects a zone, whereas `dns detail` reads the supplied record ID with that leaf's documented record-ID flag. Do not copy `--domain` from list to detail. An actual same-leaf flag error permits one bounded help read, not speculative command variations.

Alidns hosting is independent of Alibaba Cloud registrar ownership. For a user-supplied hosted zone, call `dns list --domain` directly with the intended credential source; do not reject it solely because `domain list` is empty or public WHOIS names a different registrar. Conversely, a registered account domain does not prove its zone is hosted in Alidns. Use `dns detail` with an exact record ID supplied for the frozen target by the user or an original operation response, or parsed from a successful same-Zone `dns list`; never invent an ID. For an unknown write with its original record ID already supplied, read that ID directly rather than rediscovering resources, and verify the returned Zone/host/type/line against the frozen intent. An empty record set does not authorize creating a record in a read-only request. If the zone or permission is unavailable, stop as the applicable blocked state. Preserve the exact host/type/line filters, and never expose TXT verification values through `--show-values` implicitly.

When no exact hosted Zone is supplied, ask for it or use a Zone-discovery leaf only if the installed DomainCLI actually supports one. Do not use an account-domain list, public nameservers, guessed candidates, or another product's raw command to discover the target. A read-only evaluation fixture may supply a non-secret exact Zone; missing fixture data is not permission to create resources or choose another Zone.

For any `aliyun domain dns` write:

For an update to a supplied record ID, an exact-target `DNS_RECORD_NOT_FOUND` response ends `blocked_target`, `evidence_source=runtime_verified`, `write_effect=none` before the steps below. Report that the record was not changed; do not request confirmation, create a replacement or try a different record. Authentication/permission errors, invalid commands and incomplete discovery do not establish absence.

1. Read the exact owner/type/line first. If the requested value and TTL already match, report `no_change`; if the record exists with a different target, choose `update`; otherwise choose `create`.
2. Run that intended friendly leaf without `--confirm=true` to obtain a successful preview and usable `plan_id`. If authentication, permission, or preview fails, stop; never call a generated Alidns action as fallback.
3. Show the owner name, type, value, line, TTL, and before/after state.
4. After explicit user confirmation, repeat the same operation with `--confirm=true --confirm-domain example.com --plan-id PLAN_ID`.
5. Never auto-retry a write. On uncertainty, read back with `dns detail` or `dns list` before deciding.
6. A successful readback means the control-plane value was saved; it does not prove public DNS propagation.
