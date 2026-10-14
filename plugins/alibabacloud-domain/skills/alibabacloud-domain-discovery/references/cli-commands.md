# Friendly DomainCLI commands

Use only this Skill-owned subset. Mandatory runtime constraints override examples. Every Agent-issued call includes session attribution and cli-ai-mode. No broad/preemptive help; same-leaf help once only after an actual compatibility error.

## Read and discover

| User intent | Command | Notes |
|---|---|---|
| Check registration availability | `aliyun domain check --domain example.com` | Public, read-only; never implies price or purchase. |
| Query registration or renewal reference price | `aliyun domain price --domain example.com` | A registered domain may return a fixed-price marketplace quote. Preserve `quote_type` and never label it a registration fee. |
| Query suffix reference price | `aliyun domain price --suffix com --years 1` | Public reference price, not an account-specific final quote. |
| Query public registration data | `aliyun domain whois --domain example.com` | Public WHOIS/RDAP lookup, separate from account contact data. |
| Ask domain-industry knowledge | `aliyun domain ask --question "域名过期后多久进入赎回期？"` | Advice only; it does not inspect account state. |

Do not infer that `available=false` means a marketplace listing exists. Let `price --domain` report whether it found a fixed-price listing and preserve its source label.

Validate the same requested public domain or suffix in the successful response. Empty results are valid data for that scope, not permission to invent candidates, change account or create resources. Account inventory, templates, transfer details and tasks route to their owning Skill instead of expanding this public research request.
