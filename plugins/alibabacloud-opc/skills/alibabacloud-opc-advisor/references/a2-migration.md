# Migration Output Template: Five-Section Format

> **User-visible opening hard block:** the first visible characters of the final prescription MUST be `【诊断】`. Emit no analysis preface and no internal routing code. Draft the reasoning privately, then emit only the five-section prescription in plain Chinese.
>
> **Applies to**: user already has an MVP on an external platform (Vercel/Netlify/another cloud/third-party SaaS/other AI tool hosting/self-built server/WeChat service account etc.), has real users/data, wants to migrate to Alibaba Cloud and continue growing.
> **Key design**: Starter uses unified ECS Economy e + QWCN Pro base; starter_static deprecated; single-question tier determination (calls AI or not); exact pricing; Token Plan unified Standard + upgrade advice; Pro retains only steady/burst.
> **Pricing notes**: ① starter_webui defaults to ECS ¥99/year promo; if ECS ¥99/year promo not eligible, deploy auto-fallback to ECS Economy e + 40G ESSD Entry + pay-by-traffic + 100 Mbps peak at ¥284.99/year (Beijing), with an outbound-traffic alarm (advisor no longer asks promotion history). ② All quotes must include the disclaimer (zh-CN):

```text
「💡 价格供参考，实际以最终下单为准」
```

> **Dual-path closing**: ① All prescriptions end with A/B paths (A = let me place the order / B = self-service at opc.aliyun.com/products) — never expose advisor/deploy tool names; ② Self-service path guides to specific card (4 main cards: `Starter-网络名片版` / `Starter-AI应用版` / `Lite` / `Pro`) with default-checkbox guidance; ③ starter_webui ECS Economy e ¥284.99/year pay-by-traffic fallback available only via assisted path; ④ Upgrade prompts point to "console upgrade" or "tell me and I'll help," never to purchase page; ⑤ Domain registration removes hardcoded prices.
> **Companion references**: see the SKILL.md references table (SKU matrix / concurrency mapping / glossary / domain & ICP)

## Decision Steps

### Step 1: Migration Upstream Validation (avoid mis-routing)

Ask whether it has actually gone live with real users, or is only a local/demo run. Sample wording (zh-CN):

```text
你说的'已经做出来了'是已经对外发布、有真实用户能访问到，还是目前只在本地或自己电脑上跑通了 demo？
```

| User Answer | Maps To |
|---|---|
| Already published, users can access/give feedback | **Stay on the migration path** |
| Local demo / not actually live | **Use the zero-start path** |

> When signal is already clearly sufficient, validation can be skipped: "users report access instability," "already deployed on XX platform," "users are coming in," "can't open from China on Vercel."

### Step 2: Determine Stage

| Stage Keywords | Maps To |
|---|---|
| "just want to switch hosting / want compliance / slow access from China" | **starter** (→ proceed to Step 3) |
| "already have seed users / acquiring customers / need database / need to store user data" | **lite** (→ proceed to Step 4) |
| "business accelerating / need HA / multiple machines" | **pro** (→ proceed to Step 5) |

### Step 3: Starter Single-Question Tier Determination (Migration Version)

Migration users already have running code.

**One question — does the product call AI**:

Ask whether the product heavily calls AI when used. Sample wording (zh-CN):

```text
你的产品，用户用的时候会不会大量调 AI？
```

- No → **starter_webui** (ECS Economy e ¥99/year, ~¥8.25/month)
- Yes → **starter_app** (¥212.88/month)

> 💡 If deploy-side pricing doesn't qualify for ¥99 (may have used similar promotion before), deploy auto-fallback to ECS Economy e + 40G ESSD Entry + pay-by-traffic + 100 Mbps peak at ¥284.99/year (Beijing), with an outbound-traffic alarm.

**Starter → Lite upgrade condition**:

- User going public + needs independent database + simultaneous users >20 → upgrade to lite
- Internal-test level (≤20 people) stays starter

### Step 4: Lite Simultaneous-Users Bijection

Map to lite_seed / lite_growth / lite_traction per the concurrent-users bijection.

### Step 5: Pro Traffic-Challenge Follow-Up

Ask which situation gives them the biggest headache right now. Sample wording (zh-CN):

```text
你目前最头疼的是哪种情况？
```

> 1. Stable user volume, steady access, mainly want higher availability → **pro_steady** (¥2524.55/month + ALB LCU pay-as-you-go)
> 2. Traffic concentrated in specific periods (livestream/campaign/flash-sale) → **pro_burst** (¥3258.19/month min=2, burst machines billed separately)

### Migration-Specific Tier-Jump Determination (never forcibly change tier — write into upgrade triggers)

- **Money/health/privacy sensitive data + already shared with others** → even if stage keywords only reach starter, write "upgrade to lite when data sensitivity increases" in section 5
- **User already reports "unstable/disconnects/can't open"** → write into upgrade trigger conditions
- **Determination principle**: stage keywords take priority; sensitive signals go into section 5 upgrade triggers, **never override the user's tier decision**

---

## Output Template (Migration Version)

### Structured Section

Structured fields (sku / price / scope_declaration / fallback_ecs_config / image) are produced for the downstream deploy skill and **not dumped to the user** — render the Chinese prescription below. Full schema: SKILL.md Output Contract.

### Plain-Language Section (Migration Five-Section Format)

#### If starter_webui (display-type migration)

```text
【诊断】
你的 [product form]（展示类/名片类）已经在 [platform] 跑着，[slow from China/want compliance/want to migrate to Alibaba Cloud]。

【处方】
→ **starter_webui** —— 「小店面」（ECS 云服务器 经济型e），¥99/年活动价，约 ¥8.25/月，北京地域

接下来你可以：
A. **让我帮你下单** —— 你说一声，我直接帮你创建好（推荐，省得自己点）
B. **自己去页面买** —— 打开 https://opc.aliyun.com/products
   → 选「OPC Starter 套餐 - 网络名片版」卡片
   → 把默认勾选的 QoderWork（¥59/月）去掉——那是桌面软件，不属于云资源，需要的话你自己单独下载订阅
   → 确认付款

💡 价格供参考，实际以最终下单为准。「小店面」（ECS 云服务器 经济型e）¥99/年如果没命中（比如你之前已经享过同类优惠），
   我会自动给你切到按流量计费的备选配置 ¥284.99/年（北京），同时帮你装一个出流量告警防过冲。

为什么是它：
- 展示类产品不需要 AI 额度
- 「小店面」（ECS 云服务器 经济型e）¥99/年长期优惠（续费同价）最经济
- 「全球加速」（ESA 边缘安全加速 免费版）标配解决国内访问速度

【你会拿到什么】
- 你的「小店面」（ECS 云服务器 经济型e 2核2G）
- 「全球加速」（ESA 边缘安全加速 免费版）

[domain + ICP filing prompt]
[desktop assistant line — per a1-zero-start Step 2's runtime inference: either "靠你现在这个桌面 AI 助手就能迁" or the QoderWork CN Pro download guide (¥59/月，自付，不含在套餐里)]

【怎么迁过来（3 步）】
1. **购买页确认付款** → 约 2 分钟服务器就绪
2. **让桌面 AI 助手接手** → 让它把代码从旧平台搬过来 + 部署
3. **域名 DNS 切换** → 旧平台保留几天兜底

迁移期注意点：
- 域名可保留不变，只改 DNS 解析方向
- [if mainland China region] ICP 备案约 7-20 工作日，建议提前启动
- [if service account/mini-program] 业务域名 + IP 白名单需更新

【什么时候该升级】
- 现在不用操心升级。等真正开始部署后，我会把这个套餐「什么时候该升配、升到哪档、大概多少钱」一次性讲清楚（升档前都会先报新月费你确认）；想现在就了解也可以直接问我。
```

#### If starter_app (AI-calling app migration)

```text
【诊断】
你的 [product form] 已经在 [external platform] 跑着，产品调 AI（[specific AI usage]），想迁到阿里云。

【处方】
→ **starter_app 档**（¥204.63/月 + 「小店面」（ECS 云服务器 经济型e）¥99/年摊月 ¥8.25 ≈ **¥212.88/月**，北京地域；其他地域略浮动 ±5%）

接下来你可以：
A. **让我帮你下单** —— 你说一声，我直接帮你创建好（推荐，省得自己点）
B. **自己去页面买** —— 打开 https://opc.aliyun.com/products
   → 选「OPC Starter 套餐 - AI 应用版」卡片
   → 把默认勾选的 QoderWork（¥59/月）去掉——那是桌面软件，不属于云资源，需要的话你自己单独下载订阅
   → 确认付款

💡 价格供参考，实际以最终下单为准。「小店面」（ECS 云服务器 经济型e）¥99/年活动以下单时活动可用性为准。

为什么是它：
- 产品调 AI → Token Plan 提供调用额度
- 阿里云盘 200GB 存 AI 相关资料

【你会拿到什么】
- 你的「小店面」（ECS 云服务器 经济型e 2核2G）
- 你的「AI 店员工时包」（Token Plan 标准版 25k/月）
- 你的「文件柜」（阿里云盘 200GB）
- 「全球加速」（ESA 边缘安全加速 免费版）

[Token Plan upgrade advice]
[domain + ICP filing prompt]
[desktop assistant line — per a1-zero-start Step 2's runtime inference: either "靠你现在这个桌面 AI 助手就能迁" or the QoderWork CN Pro download guide (¥59/月，自付，不含在套餐里)]

【怎么迁过来（3 步）】
1. **购买页确认付款** → 全部就绪
2. **打开 QWCN Pro → 让它帮你搬代码 + 部署 + 配好 AI 调用**
3. **域名 DNS 切换** → 旧平台保留几天兜底

迁移期注意点：
- 域名可保留不变，只改 DNS 解析方向
- 旧平台保留几天验证无误再下线
- [if mainland China region] ICP 备案约 7-20 工作日
- [if service account/mini-program] 业务域名 + Token + IP 白名单需更新

【什么时候该升级】
- 现在不用操心升级。等真正开始部署后，我会把这个套餐「什么时候该升配、升到哪档、大概多少钱」一次性讲清楚（升档前都会先报新月费你确认）；想现在就了解也可以直接问我。
```

#### If lite (migration version)

```text
【诊断】
你的 [product form] 已经在 [external origin] 跑起来、[有种子用户/在获客]，[pain point]——按同时访问规模落在 [SKU tier name]。

【处方】
→ **[lite_seed/growth/traction] 档**（¥[596.54/736.54/1131.45]/月 + 「储物间」（OSS 对象存储）¥9/年，北京地域；其他地域略浮动 ±5%）

接下来你可以：
A. **让我帮你下单** —— 你说一声，我直接帮你创建好（推荐，省得自己点）
B. **自己去页面买** —— 打开 https://opc.aliyun.com/products
   → 选「OPC Lite 套餐」卡片
   → 配置调整：
     · lite_seed → 保持默认（「业务专用店面」（ECS 云服务器）2核4G + 「客户档案柜」（RDS 数据库）1核2G）
     · lite_growth → 把「客户档案柜」（RDS 数据库）实例规格改成 2核4G
     · lite_traction → 「业务专用店面」（ECS 云服务器）改成 4核8G、「客户档案柜」（RDS 数据库）改成 4核8G
   → 确认付款

💡 价格供参考，实际以最终下单为准。

为什么是它：
- [Reason 1: fits stage]
- [Reason 2: fits scale]
- [Reason 3: pain point resolved after migration]

【你会拿到什么（大白话清单）】
- 「AI 助理的家」（轻量应用服务器 · OpenClaw 镜像 2核4G）：AI 助理帮你运维
- 「AI 店员工时包」（Token Plan 标准版 25k/月）
- 「业务专用店面」（ECS 云服务器 [2核4G/2核4G/4核8G]）：承接真实流量
- 「客户档案柜」（RDS 数据库 [1核2G/2核4G/4核8G]）
- 「储物间」（OSS 对象存储 40GB + 阿里云盘 200GB）
- 「全球加速」（ESA 边缘安全加速 免费版）

[Token Plan upgrade advice]

【怎么迁过来（4 步）】
1. **购买页确认付款** → 约 5 分钟全部资源就绪
2. **登录轻量应用服务器 → 完成 OpenClaw 部署**（可视化配置）
3. **登录 OpenClaw → AI 助理帮你搬** → 代码/数据从旧平台导出 → 部署到「业务专用店面」（ECS 云服务器）+ 配好数据库
4. **平滑切换流量** → DNS 改向 → 旧部署保留几天兜底

迁移期注意点：
- [if sensitive data] 先备份 + 小流量灰度验证
- [if service account/mini-program] 业务域名 + Token + IP 白名单更新
- [if ICP needed] ICP 备案约 7-20 工作日，建议提前启动
- 先按此档跑两周，CPU/内存持续 >70% 可一键升配

【什么时候该升级】
- 现在不用操心升级。等真正开始部署后，我会把这个套餐「什么时候该升配、升到哪档、大概多少钱」一次性讲清楚（升档前都会先报新月费你确认）；想现在就了解也可以直接问我。
```

#### If pro — migration version

```text
【诊断】
你的 [product form] 已经在 [external origin] 跑着，同时访问超两百人，[steady/has burst spikes]。

【处方】
→ **[pro_steady/pro_burst] 档**（¥[2524.55/3258.19]/月 + 「流量调度员」（ALB 应用型负载均衡）LCU 按量约 ¥30-50/月，北京地域；其他地域略浮动 ±5%）

接下来你可以：
A. **让我帮你下单** —— 你说一声，我直接帮你创建好（推荐，省得自己点）
B. **自己去页面买** —— 打开 https://opc.aliyun.com/products
   → 选「OPC Pro 套餐」卡片
   → 配置调整：
     · pro_steady → 保持默认（「业务专用店面」（ECS 云服务器）4核8G × 2）
     · pro_burst → 「业务专用店面」（ECS 云服务器）改成 8核16G × 2，并启用弹性伸缩
   → 确认付款

💡 价格供参考，实际以最终下单为准。全国加速+安全防护（ESA 边缘安全加速 标准版）限时优惠 ¥99/月以下单时活动状态为准。

为什么是它：
- 超两百人同时 → 双机高可用架构
- [steady] 稳态 → 两台互备
- [burst] 突发 → 弹性伸缩自动加机器

【你会拿到什么（大白话清单）】
- 「AI 助理的家」（轻量应用服务器 · OpenClaw 2核4G）
- 「AI 店员工时包」（Token Plan 标准版 25k/月）
- 「业务专用店面」（ECS 云服务器 [4核8G×2 / 8核16G×2-3]）：多台分担流量
- 「客户档案柜·高可用版」（RDS 数据库 高可用版 4核8G · 200GB 数据存储空间）
- 「流量调度员」（ALB 应用型负载均衡）
- 「全国加速+安全防护」（ESA 边缘安全加速 标准版）
- [burst] 「自动伸缩」（ESS 弹性伸缩）
- 「大仓库」（OSS 对象存储 500GB + 阿里云盘 500GB）

[Token Plan upgrade advice]

【怎么迁过来（4 步）】
1. **购买页确认付款** → 约 10 分钟多机架构全部就绪
2. **登录 OpenClaw → AI 助理帮你搬** → 代码/数据从旧平台导出 → 分别部署到多台「业务专用店面」（ECS 云服务器）+ 配好「流量调度员」（ALB 应用型负载均衡）分流
3. **验证**：模拟多人访问确认负载均衡正常
4. **DNS 切换** → 旧部署保留几天兜底

迁移期注意点：
- [if sensitive data] 先备份 + 灰度验证
- [if service account/mini-program] 业务域名 + IP 白名单更新
- [if ICP needed] ICP 备案约 7-20 工作日
- 「流量调度员」（ALB 应用型负载均衡）健康检查确保自动剔除故障节点

【什么时候该升级】
- 现在不用操心升级。等真正开始部署后，我会把这个套餐「什么时候该升配、升到哪档、大概多少钱」一次性讲清楚（升档前都会先报新月费你确认）；想现在就了解也可以直接问我。
```
