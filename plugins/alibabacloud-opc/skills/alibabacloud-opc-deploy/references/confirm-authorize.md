# Phase 1: Confirm + authorize

> Runs after Phase 0.4 image resolution, before Phase 2. The SKU was already settled in Phase -2
> (`sku-resolution.md`) — this phase does NOT re-identify it.
>
> - **Entry**: SKU settled, credential green, policy probe passed, image locked.
> - **Exit**: resource list shown + component removal handled + **payment second-confirmation obtained** +
>   Step 1.5 self-check all green → go to Phase 2 (`network.md`).
> - This phase owns the money conversation. Nothing here creates a resource.

```text
Step 1.2: Load the parameter file (default)
  starter_webui → default to references/sku-params/starter_webui.yaml (ECS primary path)
  other SKUs → references/sku-params/<sku>.yaml

Step 1.2.4: Make the inquiry templates below literally runnable — do this ONCE, then copy them verbatim
  Every price template in this file uses ${PROFILE} for the credential profile — the profile pinned back in
  Phase 0.2 (`credential-setup.md`), commonly `default`, or `opc` when this skill configured it. Each Bash call
  is a fresh shell, so bind it in the SAME call as the command:
      PROFILE=<the profile pinned in Phase 0.2>; aliyun ecs describe-price --profile ${PROFILE} …
  ⚠️ Why this exists: the templates used to hardcode `--profile opc`. In an environment whose profile is named
     something else, that single token makes the command look wrong — and a rewrite that starts as "fix the
     profile" ends as a hand-written command. Measured: one run rewrote the ECS inquiry from scratch, lost
     `--resource-type instance` and `--system-disk-performance-level PL0`, hit repeated parameter errors, then
     filled in a price it never obtained. Another run in the same round substituted only the profile name, kept
     every other flag, and got the correct ¥205.91 on the first call.
  ⚠️ So: substitute ${PROFILE} and NOTHING else. Every other flag in these templates is a fixed literal, and
     the placeholders `<yaml …>` are the only other values you fill — from the SKU yaml, not from memory.
     If a template errors, fix the one flag the error names (`--help` on that command); do not re-derive the call.

Step 1.2.5: starter_webui / starter_app price-inquiry gate (SWAS fallback deprecated)
  ① First inquiry (promo config: 3 Mbps fixed bandwidth):
    aliyun ecs describe-price --profile ${PROFILE} --biz-region-id cn-beijing \
      --resource-type instance --instance-type ecs.e-c1m1.large \
      --price-unit Year --period 1 \
      --system-disk-category cloud_essd_entry --system-disk-size 40 \
      --internet-charge-type PayByBandwidth --internet-max-bandwidth-out 3 --amount 1
    ⚠️ Note: DescribePrice accepts PriceUnit=Year + Period=1;
       but RunInstances at creation MUST use PeriodUnit=Month + Period=12 (the two APIs use different param formats!).
       Passing PeriodUnit=Year to RunInstances errors with InvalidPeriodType.ValueNotSupported.

  Parse the result:
    Check whether Promotions.Promotion[] contains RuleId=20906709 with TradePrice ≈ 99.0
    ① hit → silently continue on the starter_webui.yaml (or starter_app.yaml) ECS promo path
       show the user: "询价确认 ✓ 这次能拿到「小店面」（ECS 经济型e）¥99/年活动价"
       ⚠️ Do NOT pass PromotionOptions.RuleId to RunInstances — the RunInstances API has no such parameter and the CLI rejects it ("is not a valid parameter or flag"). The economy-e ¥99/yr long-term promo applies automatically on the API creation path for eligible accounts; the DescribePrice RuleId=20906709 hit above only confirms eligibility. Verify the actual charge in the order/summary after creation.

    ② miss (TradePrice > 99 or no Promotion hit) →
       **no longer fall back to SWAS ¥45/month** —
       read the fallback_ecs_config field from the advisor prescription (without advisor context, use deploy's
       built-in defaults: InstanceType=ecs.e-c1m1.large / 40G cloud_essd_entry system disk /
       PayByTraffic + 100 Mbps peak — same values as the advisor contract), immediately run a second inquiry (pay-by-traffic + 100M peak):

       aliyun ecs describe-price --profile ${PROFILE} --biz-region-id cn-beijing \
         --resource-type instance --instance-type ecs.e-c1m1.large \
         --price-unit Year --period 1 \
         --system-disk-category cloud_essd_entry --system-disk-size 40 \
         --internet-charge-type PayByTraffic --internet-max-bandwidth-out 100 --amount 1

       Expect TradePrice ≈ 284.99 (Beijing); >20% deviation is a hard stop.
       After getting the price, present the fallback option AND run the PAYMENT GATE (Hard Gate #1) on this path too — the closing question below IS the charge authorization, not a config toggle:

       "我刚试着询价了一下：这次没拿到 ¥99/年优惠（成交价是 ¥XXX）。
        多半是因为你之前在阿里云用过同类优惠（云服务器包1年99元每用户限1台）。

        给你切到一个按流量计费的备选配置：
        → 「小店面」（ECS 经济型e）· 2核2G · 40G ESSD Entry 系统盘
        → **按使用流量计费 + 100Mbps 峰值带宽**（类似手机流量套餐——不用包月，按实际用量算）
        → 年费 ¥284.99/年（约 ¥23.75/月，北京已询价确认）
        → 部署完成后我会自动帮你装一个出流量告警（CloudMonitor），防止万一被刷流量账单跳

        💡 价格供参考，实际以最终下单为准。

        🌐 网站端口（80/443）将对公网开放，互联网上的访客都能访问你的站点；远程登录（SSH）只对你自己的 IP 开放。
        即将从你的阿里云账户扣款 ¥284.99（包年/包月），确认付款？"

       ⚠️ Do NOT self-continue into creation. After emitting the prompt above, STOP and wait; proceed to network setup / RunInstances ONLY after the user replies with an explicit charge authorization. Presenting the fallback config is NOT authorization, and the promo-miss explanation is context, NOT authorization — this is exactly the spot a weak model wrongly skips (it runs RunInstances autonomously without ever emitting this prompt). The amount ¥284.99 must be the actual second-inquiry TradePrice.
       user explicitly authorizes the charge → switch to the fallback yaml (the variant=traffic_fallback branch inside starter_webui.yaml, or a separate starter_webui_traffic.yaml); the RunInstances params MUST **exactly match** the second inquiry (close the "inquiry ¥284.99 → actual charge ¥1988.39" gap)
       user declines / has not authorized yet → go back and let the user re-pick a tier via advisor or decide themselves, **no second fallback to SWAS**

       Phase 4 auto-adds a CloudMonitor outbound-traffic alarm (threshold 50GB/day):
       aliyun cms put-metric-rule-targets --rule-id opc-${ecs_instance_id}-traffic-alarm ...

    ③ the inquiry itself returns no price (Throttling.User / 429 / 5xx, or a parameter error that survives the
       single cli-meta correction) → there is NO price, therefore there is nothing to authorize. Do not grind for one.
       Budget is iron-rule #26: call #1 + exactly one retry = 2 calls, at most one sleep of ≤15s, then STOP.
       Forbidden on this branch: escalating backoff (sleep 15 → 45 → 60 is 4 calls against one goal, 2× over the cap);
       switching call form to get a different answer (a 200 from a form the failed call did not use is iron-rule #35's
       silent-false-green, not a price); and quoting the yaml's static monthly figure as a stand-in, which is a
       fabricated price. This branch has a real exit — the deployment stays resumable. Emit this and stop:

       "刚才查价格没成功：询价接口这会儿在限流，是服务端侧的临时状况，不是你账号的问题。
        我按规矩只重试了一次就停下了，没有反复刷接口。

        现在的状态：没有创建任何资源，也没有产生任何扣款。
        你选的套餐和地域我都记着，随时可以接着做。

        你说一声「继续」，我就从查价格这一步往下走。
        如果一直查不到，也可以开工单：https://smartservice.console.aliyun.com/service/create-ticket"

       ⚠️ Never cross the PAYMENT GATE without a price you just obtained live. No price → no authorization request.
       ⚠️ The SKU / region / config settled in the earlier phases are already in state, so a later 「继续」 resumes
          at this step instead of restarting Phase 0.

Step 1.2.6: lite_* / pro_* itemized price inquiry — describe-price ONLY, never create
  🔒 Phase 1 is the money conversation and creates NOTHING. Inquire each paid product with its **describe-price**
  (read-only) command, copied verbatim. **NEVER run any create / purchase / order call here — `create-instances`,
  `create-order`, `RunInstances`, `CreateInstance`, `CreateDBInstance`, `PurchaseRatePlan`, or ANYTHING matching
  `create-*` / `*-order` / `Create*` / `Run*` / `Purchase*`** — those spend money and belong to Phase 3, AFTER the
  payment gate. Running any of them to “get a price” is a silent charge and a Hard Gate #1 violation (measured
  incidents: a SWAS `create-instances` AND a SWAS `create-order` each fired during pricing and built a real billed
  instance before the gate — `swas-open` has BOTH, and describe-price is the ONLY read-only one).

  **Command contract — use only the four commands below.** Copy the selected SKU's literal values from its
  `price_inquiries` block. Replace only `${PROFILE}` with the profile pinned in Step 0.2. Do NOT switch to
  PascalCase, a BSS API, `--help`, an existing-instance lookup, or a different flag shape. Those alternatives
  are not price evidence. For `lite_seed`, the commands below are already fully concrete except `${PROFILE}`.

  SWAS (AI 助理那台) — `swas-open describe-price` ONLY; both region flags and `Server` are literal:

    aliyun swas-open describe-price --profile ${PROFILE} --region cn-beijing --biz-region-id cn-beijing \
      --commodity-type Server --plan-id swas.s.c2m4s50b1.linux \
      --price-unit Month --period 1 --pay-type Prepaid --amount 1

  Read the amount from `PriceInfo.Price.TradePrice`.

  ECS — `--region` and `--biz-region-id` are both required. PL0 is part of the purchased configuration and
  MUST appear literally in the command:

    aliyun ecs describe-price --profile ${PROFILE} --region cn-beijing --biz-region-id cn-beijing \
      --resource-type instance --instance-type ecs.c9i.large \
      --price-unit Month --period 1 \
      --system-disk-category cloud_essd --system-disk-size 40 \
      --system-disk-performance-level PL0 \
      --internet-charge-type PayByTraffic --internet-max-bandwidth-out 100 --amount 1

  Read the amount from `PriceInfo.Price.TradePrice`. Dropping PL0 silently prices PL1 and is invalid.

  RDS — use the SKU's database class and storage verbatim; this is the full read-only command:

    aliyun rds describe-price --profile ${PROFILE} --region cn-beijing --biz-region-id cn-beijing \
      --zone-id cn-beijing-l --engine MySQL --engine-version 8.0 \
      --db-instance-class mysql.n2e.small.1 --db-instance-storage 100 \
      --db-instance-storage-type general_essd --pay-type Prepaid \
      --time-type Month --used-time 1 --quantity 1 --commodity-code rds

  Read the amount from `PriceInfo.TradePrice`.

  ESA — ESA has no `DescribePrice`; this is its required equivalent. `entranceplan` is the free plan used by
  Lite, but it must still be queried and shown as an independent ¥0 line:

    aliyun esa describe-rate-plan-price --profile ${PROFILE} \
      --plan-name entranceplan --period 1 --amount 1 \
      --endpoint esa.cn-hangzhou.aliyuncs.com

  Read only `PriceModel.RatePlan.PlanPriceList[0].Price`, never `TotalPrice`.

  OSS bucket creation has no upfront order amount and is not queried here. Its prepaid storage package is a
  user self-purchase item; show it separately and exclude it from the automatic-charge total.

  ⚠️ The concrete block above is for `lite_seed` only. Never reuse its literal specs for another SKU; resolve
  every other SKU's complete product set and pricing parameters from that SKU before running any inquiry.
  ⚠️ Dropping --system-disk-performance-level PL0 defaults the API to PL1 and quotes ~¥20/month too high
     (PL0 ¥205.91 vs PL1 ¥225.91 for ecs.c9i.large / 40G / cn-beijing / Month). NOT optional for cloud_essd.
     (Correctly omitted for cloud_essd_entry on starter — see Step 1.2.5.)

  🔴 **An inquiry that did not return a number blocks that product — it does not become an estimate.**
  For each paid product, hold the actual amount together with where it came from (the response field you read
  it out of). Then, before Step 1.3:
    ① every paid line has an amount you can trace to a response received in THIS session → proceed;
    ② any line's inquiry errored, returned nothing, or you cannot say which field the number came from →
      that product is NOT priced. You may NOT put a figure next to it, may NOT include it in the total, and
      may NOT create it later. Retry the inquiry once with the flag the error names; still no number → tell
      the user plainly which item could not be priced and stop there.
  ⚠️ Never bridge a failed inquiry with a number from the yaml `monthly_price`, from `references/skus.md`,
     from an earlier session, or from your own estimate — and never defer it with 「稍后在创建时确认」: at
     creation time the amount is no longer a quote, it is a charge. A measured failure displayed multiple
     mutually inconsistent static, quoted, and charged totals; none was a valid authorization basis.

Step 1.3: Show the resource list + confirm
  Display in plain language using the final chosen yaml's user_summary field.
  Always include "💡 价格供参考，实际以最终下单为准" + when a promo is hit, append "以下单时活动可用性为准".
  ⚠️ **This step's deliverable is the ASK, not the price readout.** The itemized list exists only to set up
    the authorization question at its end; you are NOT done here until you have emitted the "即将…确认付款？"
    question and yielded the turn. Treating "I showed the prices" as "I finished" is the core mistake behind
    the failure below. So **the summary is ONE message and it MUST END on that payment question.** The
    "💡 价格供参考…" disclaimer is a MID-BODY line, NEVER your closing line — do not stop right after it.
    Measured failure: a weak model rendered the itemized list, ended its turn exactly at
    "💡 价格供参考，实际以最终下单为准。", and never emitted the charge prompt — so the user was left staring at
    prices with no way to say yes or no, no idea whether money had already moved, and the run just stopped.
    A resource list WITHOUT the trailing "确认付款？" question is a TRUNCATED gate, not a confirmation: if your
    draft ends anywhere before that question, you have not shown the gate — append the exposure line + the
    question and only then end the turn.
  Component-removal opt-out gate (deploy-side backstop, does not depend on advisor context):
    The SKU name does not carry the component removals negotiated on the advisor side, so proactively backstop here to avoid provisioning resources the user already declined (wasting money).
    Removable-component mapping (only items that actually create CLI resources and affect billing):
      - lite_seed / lite_growth / lite_traction / pro_steady / pro_burst → swas-openclaw (the "AI 助理那台", the SWAS instance)
      - starter_webui / starter_app → no CLI-removable item (qwcn-pro is a desktop tool, handled in Phase -1.2, creates no cloud resource)
    Handling logic:
      ① context/visible prescription already shows the user removed an item (e.g. the advisor prescription wrote "已去掉 AI 助理那台")
         → pre-apply directly: skip that yaml step + deduct from the list and quote, only inform "已按你之前的选择去掉 AI 助理那台", do not re-ask.
      ② no removal signal (cross-session / deploy-only / user did not mention) → for a SKU containing a removable item, proactively give one opt-out:
         "你的套餐里含 AI 助理那台（云上常驻运维助手 OpenClaw）。
          如果你已经有自建的云上运维 agent，可以去掉这台省钱；需要保留吗？"
         user answers remove → skip the corresponding yaml step (e.g. SWAS CreateInstances) + re-inquire price (deduct that component) + mark state removed_components: [swas-openclaw] (teardown/later management recognizes it)
         user answers keep / default → create everything
    ⚠️ Removal must complete **before** the payment second-confirmation below, so the price shown at second-confirmation is the post-removal final price.
    ⚠️ **HARD STRUCTURAL RULE — the opt-out question and the payment confirmation are TWO SEPARATE messages, never bundled.** Emit the “需要保留吗？” opt-out as its own message and STOP for the user's reply. Only after they answer (and the list + total are re-quoted post-removal) do you emit the separate payment confirmation “即将扣款 ¥XX，确认付款？”. NEVER merge them into one prompt such as “确认两个问题：1. 保留吗？2. 确认后开始创建” —— a weak model tends to collapse the two, which muddies the charge-authorization moment and breaks the clean confirm/decline gate. One decision per message.
  **Split the list into 自动 / 手动 — and do NOT gate on the manual half here.**
  Every SKU's resource list MUST be presented as two clearly separated blocks, because the two halves have
  different money semantics and different execution timing:

  我自动帮你开（这些会从你账户扣款，逐笔列在下面）：
    ✦ …（每行：比喻名（正式名） → 金额 + 计费周期）
    本次由我代扣：¥X

  需要你自己开（不在本次扣款内，我会带着你一步步弄）：
    ✦ AI 能力（Token Plan AI 模型订阅计划）… → 你自己在页面买
    ✦ 存储空间（阿里云盘 PDS）… → 你自己在页面买
    ✦ 大仓库的存储包（OSS）… → 你自己在页面买
    你自己另买：¥Y

  **Execution order (this is the whole point — do not reorder it):**
  1. 先把「自动」那半**全部创建完**（Phase 3 的付费流程，受 PAYMENT GATE 管辖）。
  2. 再回头**逐个引导用户开「手动」那半**，PDS / OSS 给到字段级的具体指引（下面两段）。
  3. **用户明确说 OSS 开好了之后**，才去建桶（Phase 3 的建桶步骤，见 `provision.md` 的 Step 3c）。

  ⚠️ **手动项在本步骤只是「交代清楚」，不是通行闸。** 用户此刻回「先不买 / 晚点买」完全正常：记录下来、一行确认、
  **继续走付款确认和自动资源创建**。把手动项当成付款前置会堵住整条流程，
  而且会让用户在还没看到方案和总价时就被推去买东西。

  Self-purchase item — OSS storage package (only for SKUs that contain OSS: lite_seed / lite_growth /
  lite_traction / pro_steady / pro_burst):
    OSS has no CLI purchase channel AND must be activated before any bucket call, so it is the user's own
    one-click step. List it in the 手动 block above with its price, and give the field-by-field instructions
    below **once**. Then move on — the blocking check lives at the bucket step, not here.
    ⚠️ A preset link is impossible: the page defaults to 标准-同城冗余 and its selections do not travel in
    the URL. So spell out every pick, field by field, and never just paste the link:
      "OSS 存储包这一笔要你自己在页面上买一下（买的同时就把 OSS 开通了，一步到位）：
       https://common-buy.aliyun.com/?commodityCode=ossbag&regionId=china-common
       打开后按这几项选，其它保持默认：
       ① 商品类型：OSS 资源包
       ② 资源包类型：标准 - 本地冗余存储 ← 页面默认是「同城冗余」，一定要改，选错了抵扣不到等于白买
       ③ 地域：中国内地通用
       ④ 规格：${40 GB · 约 ¥9/年 | 500 GB}
       ⑤ 购买时长：1 年
       买完回来跟我说一声。我先把能自动开的都装好，到建仓库那一步再用得上它。"
    Spec per SKU: lite_seed / lite_growth / lite_traction → 40 GB; pro_steady / pro_burst → 500 GB.
    Why 本地冗余 is mandatory: a package only offsets the storage type it names (the buy page says so under
    抵扣规则 and each type's 场景描述), and every sku-params yaml creates LRS buckets.
    If the user says they already have OSS activated with enough quota, accept it and move on — never make
    them buy a second package.
    ⚠️ **Say it once, then stop asking.** The instruction block above is emitted **one
    time**. Record the outcome in state (`self_purchase.oss_package` = `bought` | `already_active` |
    `deferred`) and **never re-issue the block or re-ask in later turns**:
      - bought / already active → mark it and proceed.
      - 「先不买」/「晚点买」/「等一下再说」 → mark `deferred`, acknowledge in ONE line
        (`好，OSS 这笔你晚点买。我先把能自动开的都装好，到建仓库那步再提醒你一次。`) and **continue** —
        a deferred OSS package does NOT block the payment gate, the network step, or any automatic creation.
      - the ONE permitted re-mention is at the bucket step in `provision.md` (Step 3c), and only when the
        state is still `deferred`.
    Repeating the full purchase block, or re-asking 「买了吗」 across turns, is this rule's violation.
  **Payment second-confirmation logic**:
    After showing the resource list, the first confirmation only confirms creation intent ("确认开始创建？").
    Before entering Phase 3 to run RunInstances/CreateInstances (i.e., before the actual charge),
    a second explicit payment confirmation is required:
      "🌐 网站端口（80/443）将对公网开放，互联网上的访客都能访问你的站点；SSH 只对你自己的 IP 开放。
       即将从你的阿里云账户扣款 ¥XX（[计费周期说明]），确认付款？"
    ⚠️ **This question is the LAST line you emit this turn — then STOP and wait (emit-then-yield).** No
       disclaimer / footer / "价格供参考" line may sit after it, and you may NOT end your turn before you have
       emitted it. Showing the resource list + total but NOT this question is the exact failure to avoid: the
       gate only exists once "确认付款？" is on screen AND a later user turn answers it. No question emitted ⇒ no
       gate ⇒ you have shown prices and vanished, leaving the user unable to approve or refuse and unsure
       whether they have been charged. The user's reply is the ONLY thing that moves the flow forward:
    user answers "确认" → execute creation
    user answers no / "先不下单" / "再考虑一下" → STOP the flow, create nothing, issue no fee-incurring call, and
       emit a self-contained closing that: ① plainly states 未创建任何资源、未产生任何扣款; ② recaps the would-be
       自动扣款合计（¥XX/月）so they know the standing quote; ③ re-lists the self-purchase items
       (Token Plan / PDS / OSS 存储包) they can buy later; ④ tells them how to resume. Do not just ask "why" and
       trail off, and never say 已扣款 — nothing was charged.
    **Exception**: if the API returns InsufficientBalance, no second confirmation is needed —
    directly tell the user the top-up amount + link, then re-execute after top-up.

    ⚠️ **Multi-order SKUs (Lite / Pro): ¥XX is a total that will be charged as N separate orders.**
    Only starter is one paid call. For every SKU with more than one paid product, before asking for
    authorization you MUST:
      a) run each product's own DescribePrice (ecs / swas-open / rds / oss …) and list one line per paid
         order with its amount + billing period — never estimate, never reuse the yaml `monthly_price`
         marketing string;
      b) **write the addition formula out loud** — a plain-text line built only from this session's results, like
             `SWAS ¥<live> + ECS ¥<live> + RDS ¥<live> + ESA ¥<live> = ¥<live total>`
         placed just above the payment prompt, so both you and the user can eyeball whether the sum
         equals the ¥XX in the prompt. This is an emitted step, not a mental check:
         a total that is only summed in your head can drift from the itemized lines without anyone
         noticing. **If the formula doesn't equal ¥XX, DO NOT edit the
         total to match; re-run DescribePrice for every line and rebuild the list from scratch.**
      c) **the total is ALWAYS re-summed from the current DescribePrice results** — never sourced from,
         nor patched against, the yaml's `monthly_price` field or any other static reference. Those
         numbers exist only for advisor's sizing conversation; the payment total is a live-inquiry sum.
         On any correction (removed component, refreshed price), throw away the old total and re-add the
         current line items — do NOT do `old_total ± delta` (patching the static
         ¥2524.55 by +¥54 yielded ¥2578.55, ¥60 off the true ¥2518.50).
      d) if the payment list mixes billing cycles (monthly + annual + pay-as-you-go), keep each line
         labelled inline (`/月` vs `/年` vs `按量`) and DO NOT collapse them into a single unlabelled
         total; annual amounts must not be summed with monthly amounts as if they had the same unit.
      e) say plainly that these are separate orders charged one by one (e.g. "这几笔是分开下单的，会一笔
         一笔扣，每扣一笔我都会告诉你"), so the user is not surprised by several deductions;
      f) note that renewal is also per-order (they expire and renew separately).
    The user may prefer one bundled order via the OPC purchase page — that is a legitimate alternative to
    offer if they ask, but never a way to skip this confirmation.

    ⚠️ **`${automatic_total}` in every SKU yaml `user_summary` = the total re-summed from THIS session's
    DescribePrice results** (the same figure the addition formula above produces), never the yaml's own
    `monthly_price` / 费用 marketing string. Substitute the live number when you render the summary —
    never emit the literal `${automatic_total}` to the user, and never quote a price you did not inquire.
    ⚠️ **The payment question is the REQUIRED LAST LINE of that summary.** Every SKU yaml ends its
    `user_summary` with 「即将从你的阿里云账户扣款 ¥…，确认付款？」 — emit the whole block as one message,
    end on that question, and yield. Keep 「💡 价格供参考…」 mid-body, never as the closing line: measured,
    a weak model that ended its turn on the disclaimer never asked for payment, so the confirm/decline gate
    never happened (the user could neither approve nor refuse). A prompt like 「确认开始创建？」 that does not
    name the deduction is NOT a payment gate — it asks about creating, not about paying.

Step 1.4: Determine the region
  Default: cn-beijing
  user specifies another → use the specified value

Step 1.5: Pre-execution hard-gate self-check (HARD BLOCK · every item must pass before Phase 3)
  ⚠️ This self-check is a hard gate, not a soft hint, not a "suggested review".
     Any item not passing → stop immediately, discard the current execution plan, forbid calling any create/charge API;
     first return to the corresponding Phase to fill the gap, then re-run this self-check; only enter Phase 3 when all pass.
     NEVER "just create it first".
  [ ] 1. SKU settled and one of the legal 7 (else back to Phase -2 / advisor)
  [ ] 2. Phase -1.5 CLI-reachability gate passed; partial/false items went through fallback and were user-confirmed
  [ ] 3. Step 0.2b policy coverage probe run for THIS SKU's product set and all-green (no 403 / NoPermission / Forbidden.RAM outstanding)
  [ ] 4. credential profile type = RamRoleArn (verified via aliyun configure list); AK/SK never read/echoed throughout; one profile pinned for the whole run
  [ ] 5. resource list + monthly price shown, with the "💡 价格供参考，实际以最终下单为准" disclaimer appended
  [ ] 6. payment second-confirmation obtained: I emitted "即将扣款 ¥X，确认付款？" **as a chat message**, and a
         **user turn that arrived AFTER it** explicitly confirmed. The opening request ("帮我开一个 <SKU>") predates
         the prompt and can never be that turn; insufficient-balance top-up path excepted.
  [ ] 7. starter inquiry: the RunInstances order params exactly match the final DescribePrice params (close the inquiry↔charge gap)
  [ ] 8. out-of-scope requests hard-rejected per iron-rule #23 built-in scope cannot_do and pointed back to the desktop AI assistant (if any)
  [ ] 9. component-removal opt-out handled: a SKU with a removable item (Lite/Pro's "AI 助理那台") was pre-applied per context or given one opt-out; the final to-create set matches the quoted monthly price
  [ ] 10. OSS-bearing SKU (lite_* / pro_*): the OSS storage package was **listed in the 手动 block and its field-by-field instructions given once**, and `state.self_purchase.oss_package` carries a resolved value (`bought` / `already_active` / `deferred`). **`deferred` PASSES this item** — it does not block Phase 3. Rationale: a read-only `ossutil ls` now tells activation apart (unactivated → 403 UserDisable; activated → succeeds; E2E-measured 2026-09-16), yet OSS is still NOT gated here — blocking Phase 3 on one optional storage package would stall the whole deployment. The bucket step (`provision.md` Pass 3c) creates the bucket and treats 403 UserDisable as an acceptable "not activated" final state.
  [ ] 11. the authorized total covers ONLY the orders THIS skill charges. Self-purchase items (Token Plan / PDS / the OSS package) sit in their own `另需你自己购买（不在本次扣款内）` block and are NOT inside the addition formula, and the two figures were stated apart (`本次由我代扣：¥X` vs `你自己另买：¥Y`). A `type: manual` yaml step never enters the total.
  [ ] 12. every message sent so far in this session passes the language + terminology check: Chinese prose throughout, and no internal label (Phase / Preflight / Gate / probe / 探针 / RamRoleArn / AssumeRole / STS / StsToken / bootstrap / iron-rule / state file / yaml) leaked into user-facing text. If any earlier message leaked, do not silently continue — restate that part in plain Chinese now.
  [ ] 13. the list, the per-order amounts, the addition formula and the total are quotable from **messages I sent in this conversation**. If any of them lives only in a file under `outputs/`, this item FAILS — a written record is a copy, never the disclosure.
  [ ] 14. every amount shown is traceable to a `DescribePrice`-family response received in THIS session (I can name the product, the command and the field). Any line I cannot trace → that product is unpriced: remove it from the list and the total, and do not create it.
```
