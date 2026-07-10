---
name: alibabacloud-cli-cost-estimation
description: >
  Pre-execution cost estimation for Alibaba Cloud CLI operations. Use this skill
  whenever a user asks "how much will this cost", before executing any chargeable
  operation (create / resize / renew / bandwidth change), or when planning a
  multi-step workflow whose total cost should be known up front. Covers the
  --estimate-cost flag (quote without executing), --estimate-cost-context
  (usage assumptions and future-state overrides for multi-step workflows),
  reading the quote JSON correctly (pricingMode, pricingUnit, delta amounts),
  and reconciling quotes against actual bills.
triggers: >
  estimate cost, cost estimation, price quote, how much will it cost,
  询价, 报价, 多少钱, 费用预估, 成本预估, 变配差价, 执行前费用,
  estimate-cost, PricingContext, 计费预览, 账单预览, price before execution,
  chargeable operation, upgrade cost, renewal cost, bandwidth cost
license: Apache-2.0
metadata:
  domain: aliyun-cli
  owner: sdk-team
  contact: sdk-team@alibabacloud.com
allowed-tools: "mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___CallCLI,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___SearchApis,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GetApiDefinition,mcp__plugin_alibabacloud-core_alibabacloud-core__AlibabaCloud___GenerateCLICommand"
---

# Alibaba Cloud CLI Cost Estimation

Get an exact price quote for a CLI operation **without executing it**. The quote
comes from the same pricing source as the trade system: for operations that
produce an immediate order, the quoted amount equals the order amount you would
actually pay (verified across new purchases, spec upgrades, and bandwidth
changes — quote and bill match to the cent).

This is the **pre-execution** half of cost management. The post-hoc half
(bills already incurred) is `aliyun bssopenapi QueryAccountBill` — see the
reconciliation section below.

## Requirements

- Alibaba Cloud CLI ≥ 3.4.2 (`aliyun version`)
- Product plugins up to date (`aliyun plugin update`)

## The Agent Rule: Quote Before Chargeable Execution

When you are about to execute an operation that creates, resizes, renews, or
otherwise changes billable resources:

1. **Check** whether the API supports quoting (see Discovery below).
2. **Quote** it by appending `--estimate-cost` to the exact command you intend
   to run.
3. **Present** the amount to the user as part of the confirmation, e.g.
   "This will execute `ModifyPrepayInstanceSpec` — estimated charge ¥28.89
   (prorated upgrade delta). Proceed?"
4. **Execute** only after confirmation, by removing `--estimate-cost` from the
   same command.

Never silently execute a chargeable operation when a quote was obtainable.
`--estimate-cost` is always safe to add: it only quotes, never executes, and
changes nothing in the account.

**Multi-step plans: quote everything first, confirm once.** When the user's
request decomposes into multiple API calls (a workflow), do NOT interleave
execute-and-ask step by step. Instead:

1. Quote **all** chargeable steps up front, before executing step 1 — use
   `--estimate-cost-context` state overrides for steps that depend on the
   state an earlier step will produce.
2. Present **one consolidated cost plan**: each step's amount labelled by its
   nature (immediate order / usage-based estimate with its assumption /
   refund / free), plus the total of immediate charges.
3. Ask for a **single confirmation** of the whole sequence, then execute the
   steps in order.
4. If a step fails or the account state changes mid-sequence, stop and
   re-quote the remaining steps before continuing.

### The Cost Plan Format

Present the consolidated plan in this fixed shape:

```text
Cost plan: <goal> (<N> steps)
  <i>. <step action>  —  <LABEL> <amount>  (<basis or assumption>)
  ...
Totals: pay now ¥<X> · refund ¥<Y> · future ¥<Z>/<unit> (assumes <usage>)
Execute all <N> steps in order? [y/N]
```

Use exactly four labels, one per step:

| Label | Meaning | Amount shown |
| --- | --- | --- |
| `PAY NOW` | Immediate order on execution | Quoted order amount |
| `FUTURE` | Usage-based, billed as consumed | Estimate × unit price, **with the assumption** |
| `REFUND` | Money returned on execution | Negative amount, or "not quotable" if the API can't quote it |
| `FREE` | No money involved | — |

Rules:

- **Never sum different natures together.** The totals line keeps pay-now,
  refund, and future amounts as separate figures — a single "grand total"
  mixing an immediate ¥130 with a ¥80/month estimate is misleading.
- Every `FUTURE` amount must carry its assumption inline; if the user never
  confirmed the assumption, ask before presenting the plan.
- A step whose quote is unavailable shows the reason in place of a number
  (e.g. "refund occurs, amount not quotable yet") — never silently drop it.

Filled example (the 5-step public-IP replacement):

```text
Cost plan: replace public IP (5 steps)
  1. Switch bandwidth billing to pay-by-traffic  —  FUTURE ¥0.8/GB  (assumes 100 GB/month → ¥80/month)
  2. Convert fixed public IP to EIP              —  FREE  (EIP then billed by usage)
  3. Unassociate EIP                             —  FREE
  4. Set 5 Mbps bandwidth, new public IP         —  PAY NOW ¥130.40  (prorated to term end)
  5. Release old EIP                             —  FREE  (stops the old IP's billing)
Totals: pay now ¥130.40 · refund: step 1 returns unused bandwidth fee (not quotable yet) · future ¥80/month (assumes 100 GB)
Execute all 5 steps in order? [y/N]
```

## Discovery: Which APIs Support Quoting

```bash
aliyun list-supported-pricing-apis

# Does a specific API support it? (any output = yes)
aliyun list-supported-pricing-apis \
  --cli-query "supportedApis[?apiName=='ModifyInstanceNetworkSpec']"
```

The list is served live and keeps expanding — query it rather than relying on a
cached copy. Each entry is a `popCode / popVersion / apiName` triple.

## Basic Usage

Append `--estimate-cost` to any supported command (works on both PascalCase
built-in and kebab-case plugin command forms):

```bash
# What would a 1-month subscription instance cost?
aliyun ecs run-instances --biz-region-id cn-hangzhou \
  --image-family acs:ubuntu_22_04_x64 \
  --instance-type ecs.e-c1m1.large \
  --instance-charge-type PrePaid --period 1 --period-unit Month \
  --system-disk-category cloud_essd --system-disk-size 20 \
  --vswitch-id vsw-xxx --security-group-id sg-xxx \
  --estimate-cost

# What is the prorated delta for upgrading an instance type?
aliyun ecs modify-prepay-instance-spec --region cn-hangzhou \
  --instance-id i-xxx --instance-type ecs.e-c1m2.large --estimate-cost
```

## Reading the Quote JSON

Top level is `price` + `requestId`. Decide how to read the amount in this order:

1. **`pricingMode: "delta"`** (spec changes) → read `calculatedAmount`. That is
   the net amount to pay after the old configuration's remaining value is
   refunded. `components.baseline` / `components.target` are the gross sides —
   do not present them as the price.
2. **`pricingMode: "single"`** → read `priceSummary.effectiveModuleSum`
   (post-discount total), then check `pricingUnit`:
   - Present (e.g. `"1 Month"`, `"Once"`) → the amount is per that unit.
   - **Missing** → this is a usage-based quote: amount = the estimated usage
     you supplied × unit price. Its dimension is the usage you passed in
     (e.g. ¥80 for the 100 GB you estimated). Do not present it as a monthly
     or one-time charge.
3. `priceSummary.modules[]` gives the per-billing-item breakdown
   (originalCost / invoiceDiscount / costAfterDiscount) — useful when the user
   asks where the money goes.
4. `success: false` → read `errorCode` / `errorMessage`; do not infer from the
   exit code.

## PricingContext: `--estimate-cost-context`

Some quotes need input that is not an API parameter. Pass it as repeatable
`Key=Value` pairs (must be combined with `--estimate-cost`):

```bash
--estimate-cost --estimate-cost-context K1=V1 K2=V2
```

It carries two kinds of information:

| Kind | Example | When needed |
| --- | --- | --- |
| **Usage assumption** | `EstimatedInternetTrafficOutGB=100` | Usage-based billing: cost = usage × unit price, and only the user knows the expected usage |
| **State override** | `InternetChargeType=PayByTraffic` | Multi-step workflows: a later step must be quoted against the state produced by an earlier step, not the current state |

Ask the user for usage assumptions when a quote requires them (e.g. "How much
monthly outbound traffic do you expect?") instead of inventing a number; state
the assumption alongside the quoted amount.

## Multi-Step Workflow Quoting

Example: replacing a fixed-bandwidth instance's public IP (5 steps). All
chargeable steps can be quoted **before executing step 1**:

```bash
# Step 1 — switch bandwidth billing to pay-by-traffic.
# Usage-based: supply the traffic estimate.
aliyun ecs modify-instance-network-spec --region cn-hangzhou \
  --instance-id $INS --network-charge-type PayByTraffic \
  --estimate-cost --estimate-cost-context EstimatedInternetTrafficOutGB=100

# Step 2 — convert the fixed public IP to an EIP. No context needed.
aliyun ecs convert-nat-public-ip-to-eip \
  --instance-id $INS --biz-region-id cn-hangzhou --estimate-cost

# Step 3 — unassociate EIP: free operation (see "Free APIs" below).

# Step 4 — set new bandwidth. At quoting time the instance is still
# fixed-bandwidth, but by execution time step 1 will have completed —
# override the state so the quote is based on the future state:
aliyun ecs modify-instance-network-spec --region cn-hangzhou \
  --instance-id $INS --network-charge-type PayByBandwidth \
  --internet-max-bandwidth-out 5 \
  --estimate-cost --estimate-cost-context InternetChargeType=PayByTraffic

# Step 5 — release old EIP: free; its effect is stopping the old IP's billing.
```

Sum the per-step quotes client-side and present one pre-execution bill preview,
labelling each amount by its nature: immediate order vs future usage-based cost
vs refund vs free step.

## Free / Unsupported APIs

Quoting an API with no pricing information returns an explicit message:

```text
Error: no pricing information for vpc/2016-04-28/UnassociateEipAddress:
this OpenAPI either incurs no cost or has no pricing mapping registered yet
```

This is an answer, not a failure — treat it as "this step is not chargeable
(or not yet quotable)" and say so, rather than reporting an error to the user.

For APIs that are not yet quotable, never present a number from your own
knowledge as if it were a quote. If you cite public list prices, label them
explicitly as unverified estimates with their assumptions, and point the user
to the official pricing page (or to `bssopenapi QueryAccountBill` after a
trial run) for authoritative figures.

## Troubleshooting

| Symptom | Meaning / action |
| --- | --- |
| `no pricing information for ...` | API is free or not yet quotable — informational |
| `No pricingTarget matched the input request` | The parameter combination hit no pricing rule. The error lists each rule's `when` condition — usually a required PricingContext key is missing (e.g. traffic estimate for pay-by-traffic) |
| `--estimate-cost-context requires --estimate-cost` | Add `--estimate-cost` |
| `invalid --estimate-cost-context 'xxx'` | Use `Key=Value` form; key must be non-empty |
| Quote succeeds but no `pricingUnit` | Usage-based quote: amount = your estimate × unit price |

## Reconciliation (Post-Execution)

Chargeable executions return an `OrderId`. To verify the quote against the
actual bill:

```bash
aliyun bssopenapi GetOrderDetail --OrderId <order-id>
```

For upgrade orders the bill has two lines (new config + refund of the old);
their net equals the quoted `calculatedAmount`.

## Command Cheat Sheet

| Goal | Command |
| --- | --- |
| List quotable APIs | `aliyun list-supported-pricing-apis` |
| Quote (no execution) | `aliyun <product> <command> ... --estimate-cost` |
| Quote with assumptions / state override | `... --estimate-cost --estimate-cost-context K1=V1 K2=V2` |
| Verify against actual order | `aliyun bssopenapi GetOrderDetail --OrderId <id>` |
| Post-hoc bills (complementary) | `aliyun bssopenapi QueryAccountBill --BillingCycle YYYY-MM` |
