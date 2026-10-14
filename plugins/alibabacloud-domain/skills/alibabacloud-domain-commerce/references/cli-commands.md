# Friendly DomainCLI commands

Use only this Skill-owned subset. Mandatory runtime constraints override examples. Every Agent-issued call includes session attribution and cli-ai-mode. No broad/preemptive help; same-leaf help once only after an actual compatibility error.

## Acquire and retain

| User intent | Command group | Risk |
|---|---|---|
| Register one or more domains | `aliyun domain buy --domains example.com` | Financial. Price first; browser checkout is the safer default. Balance submission needs all CLI payment confirmations and a verified registrant profile. |
| Transfer domains into Alibaba Cloud | `aliyun domain transfer-in` | Financial and secret-bearing. Never put transfer codes in chat, logs, or artifacts; follow the leaf help for secure input. |
| Renew one or more domains | `aliyun domain renew --domains example.com` | Financial. The CLI queries reference prices first; incomplete pricing may permit only a clearly labeled official browser handoff; it never authorizes payment or a cloud write without current successful preview and fresh user confirmation. |
| Redeem expired domains | `aliyun domain redeem` | Financial and time-sensitive. Quote and eligibility are separate checks. |
| Manage automatic renewal | `aliyun domain auto-renew` | May cause later charges; preview and confirm the exact domains and target state. |

For renewal/redemption, read the exact account asset and its lifecycle state before previewing the applicable operation. Public suffix pricing is useful even without that asset, but it neither proves eligibility nor locks a target-domain price. If `detail` fails while transforming its upstream response, report the runtime error; a field missing from that response is not evidence that the user omitted a domain or that the asset is absent. A separate successful account lookup can establish only its own returned scope.


## Domain marketplace

| User intent | Command | Risk |
|---|---|---|
| Query a fixed-price listing | `aliyun domain trade detail` | Read-only marketplace data; keep its transaction-price label. |
| Request a seller verification code | `aliyun domain trade send-code` | Authentication and anti-abuse sensitive; never expose the code. |
| Publish a fixed-price listing | `aliyun domain trade publish` | Financial ownership write. Preview, confirm the exact domain and listing price, submit once, then verify the seller-side result. |

Do not route a normal registration query to `trade`. Use it only for an already-registered domain's marketplace listing or seller workflow.

`trade detail` accepts one exact full domain; it is not marketplace keyword search or a list API. For a request to browse domains containing a keyword, explain this capability gap and ask for exact candidates instead of probing a large invented list. Before `trade publish`, verify that the exact domain is an applicable account asset, show its listing price, and collect the independent confirmations and human verification required by the leaf. Do not send a verification SMS implicitly or request its code in chat.

For `buy`, a `fixed_price_trade` result is not a normal registration order. DomainCLI opens the Alibaba Cloud domain transaction detail page and supports only the transaction path it reports. Do not force it into the registration balance-payment flow.

## Allowed prerequisite reads

Commerce may use `aliyun domain check`, `aliyun domain price`, exact-account `aliyun domain detail`, `aliyun domain template list` (safe IDs/status only), and supported `aliyun domain task` status leaves for actual returned IDs. These reads do not transfer control-write ownership to commerce. Missing documented flags/IDs require a capability/input handoff; never invent an order query or generated API action.

Before registration preview, establish a suitable verified registrant template through a scoped `template list` read. Follow pagination within the runtime budget; an incomplete page is not proof that none exists. If the complete applicable list is empty, report `blocked_fixture`, `evidence_source=runtime_verified`, `write_effect=none` and the exact missing prerequisite. Do not create a template, choose a different domain, fabricate a price/order, request purchase confirmation or submit a purchase. An authentication, permission, command or runtime failure is not an empty list. A `template_selection_required` response alone does not prove the account has no suitable templates. Registration eligibility remains a separate check: deletion preorder and fixed-price trade are not ordinary registration availability.
