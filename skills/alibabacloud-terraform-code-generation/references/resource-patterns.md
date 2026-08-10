# Product-specific resource patterns

Positive patterns — "when the user asks X, use these attributes or
multi-resource idioms". This complements:

- `alicloud-providers.md` (catalog: does this resource exist? any
  deprecation?)
- `deprecated-fields.md` (field-level renames / splits / soft-splits)

Entries here are **product-specific conventions** that the provider doc
technically documents but does not emphasize, leading agents to miss them.
Consult this file during Step 5.1 whenever the user's requirement touches
a product listed below.

---

## RDS cross-AZ primary/secondary HA

**Trigger phrases**: "高可用 / HA / 主从架构 / 多可用区 / 跨可用区 /
primary-secondary / master-slave" applied to `alicloud_db_instance`.

**Non-obvious requirement**: the provider doc lists `zone_id_slave_a` as
*optional*. Agents often set `category = "HighAvailability"` alone and
assume alicloud places the standby automatically in a different AZ. It does
not — without `zone_id_slave_a`, primary and standby land in the same AZ,
defeating the user's cross-AZ intent.

**Required attributes on `alicloud_db_instance`**:

| Attribute | Value | Why |
| --- | --- | --- |
| `category` | `"HighAvailability"` | Switches the edition. `multi_az = true` and `ha_config = "Auto"` **do not** replace this. |
| `zone_id` | `data.alicloud_db_zones.<n>.zones[0].id` | Primary AZ. |
| `zone_id_slave_a` | `data.alicloud_db_zones.<n>.zones[1].id` | Secondary AZ. MUST differ from `zone_id`. |

**Sketch**:

```hcl
data "alicloud_db_zones" "mysql_ha" {
  engine                   = "MySQL"
  engine_version           = "8.0"
  category                 = "HighAvailability"
  db_instance_storage_type = "cloud_essd"
}

resource "alicloud_db_instance" "this" {
  engine                   = "MySQL"
  engine_version           = "8.0"
  category                 = "HighAvailability"
  db_instance_storage_type = "cloud_essd"
  instance_type            = var.rds_instance_type
  instance_storage         = 100

  zone_id          = data.alicloud_db_zones.mysql_ha.zones[0].id
  zone_id_slave_a  = data.alicloud_db_zones.mysql_ha.zones[1].id

  # ... vswitch_id, security_group_ids, security_ips, etc.
}
```

---

## OSS lifecycle — current vs noncurrent versions

**Trigger phrases**: "旧版本 / historical versions / noncurrent /
old object versions / N 天后(转 IA|归档)" applied to an
`alicloud_oss_bucket` with a lifecycle rule.

**Non-obvious requirement**: the `lifecycle_rule` block has TWO
transition sub-blocks with different targets — picking the wrong one
transitions the wrong objects.

| Sub-block | Targets | When to use |
| --- | --- | --- |
| `transition { days = N, storage_class = … }` (or `transitions`) | *Current* object version | User says "文件 N 天后转 IA" (current objects) |
| `noncurrent_version_transition { days = N, storage_class = … }` | *Older* / noncurrent versions | User says "旧版本 / 历史版本 / noncurrent …" |

Versioning MUST be enabled on the bucket (via
`alicloud_oss_bucket_versioning`, see `deprecated-fields.md`) for
`noncurrent_version_transition` to have any effect.

**Sketch**:

```hcl
resource "alicloud_oss_bucket" "this" {
  bucket = var.bucket_name
  lifecycle_rule {
    id      = "archive-old-versions"
    prefix  = ""
    enabled = true

    # user said "旧版本 90 天后转 IA" → use noncurrent_version_transition
    noncurrent_version_transition {
      days          = 90
      storage_class = "IA"
    }
  }
}

resource "alicloud_oss_bucket_versioning" "this" {
  bucket = alicloud_oss_bucket.this.bucket
  status = "Enabled"
}
```

---

## OSS bucket — split sub-resource defaults

**Trigger phrases**: writing `alicloud_oss_bucket` where a split/soft-split
sub-resource is needed by user intent or by the safe-default table below
(`acl`, `logging`, `versioning`, `website`, etc. — see
`deprecated-fields.md` for the full list).

**Non-obvious requirement**: do not generate every split sub-resource just
because it exists. Generate the safe defaults below only where listed; otherwise
create the sub-resource only when the user asks for that feature. For ACL,
never pick `public-read` without public-access intent — default to `private`.

| Sub-resource | Default value when no user intent specified |
| --- | --- |
| `alicloud_oss_bucket_acl` | `acl = "private"` |
| `alicloud_oss_bucket_versioning` | `status = "Suspended"` |
| `alicloud_oss_bucket_logging` | Omit the sub-resource (logging disabled) |
| `alicloud_oss_bucket_website` | Omit the sub-resource (no static website) |

`cors_rule` is an inline block on `alicloud_oss_bucket`, not a standalone
`alicloud_oss_bucket_cors` resource. Generate `cors_rule { ... }` only when
the user explicitly asks for CORS; otherwise omit it.

Only use permissive values (`public-read`, `Enabled`, etc.) when the user
**explicitly** described a public-access scenario: "静态网站 / 托管网站 /
public / CDN / CORS / website / 版本控制".

---

## FCv3 function — mandatory RAM role + service access policy

**Trigger phrases**: any `alicloud_fcv3_function` (or its deprecated name
`alicloud_fc_function`) where the function needs to access other Alibaba Cloud
services — OSS, RDS, LogService, VPC resources, etc. Also triggers when the
user mentions permissions like "读写 / read-write / access / 访问 / 权限".

**Non-obvious requirement**: the agent often generates only the function
resource and skips the RAM role because the user never said "create a role".
BUT — without a RAM role with `sts:AssumeRole` for `fc.aliyuncs.com`, the
function has no identity outside itself and cannot reach any other service.
This is NOT a style preference; it is a functional requirement for any
function that talks to OSS, RDS, or any other alicloud resource.

**Required additional resources on the Step 3 sketch**:
When the FC function accesses another service, you MUST add these two
resources to the sketch, even if the user didn't name them:

| Resource | Purpose |
| --- | --- |
| `alicloud_ram_role` | Identity the function assumes. Trust policy: `Principal.Service = ["fc.aliyuncs.com"]`, Action: `sts:AssumeRole`. |
| `alicloud_ram_role_policy_attachment` | Binds the access policy to the role. Use the policy name `AliyunOSSFullAccess`, `AliyunRDSFullAccess`, etc., or attach a custom `alicloud_ram_policy`. |

Attach without a previous `alicloud_ram_role` → skip the role and policy
attachment is a generation defect, not "clean minimal code". The `role`
attribute on `alicloud_fcv3_function` accepts either
`alicloud_ram_role.<n>.arn` (preferred) or `alicloud_ram_role.<n>.role_name`
— both resolve correctly.

Note on deprecated fields on `alicloud_ram_role`:

- `name` → use `role_name` instead (see `deprecated-fields.md`)
- `document` → use `assume_role_policy_document` instead

**Sketch**:

```hcl
resource "alicloud_ram_role" "fc" {
  role_name                   = "${var.project_name}-fc-role"
  assume_role_policy_document = jsonencode({
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = ["fc.aliyuncs.com"] }
    }]
    Version = "1"
  })
}

resource "alicloud_ram_role_policy_attachment" "fc_oss" {
  role_name   = alicloud_ram_role.fc.role_name
  policy_name = "AliyunOSSFullAccess"
  policy_type = "System"
}

resource "alicloud_fcv3_function" "this" {
  function_name = "${var.project_name}-fn"
  runtime       = "python3.10"
  memory_size   = 256
  role          = alicloud_ram_role.fc.arn   # preferred
  # role        = alicloud_ram_role.fc.role_name  # also works
  # ... code, handler, etc.
}
```

---

## VPC connectivity — peering vs CEN

**Trigger phrases**: "VPC 互通 / 跨 VPC / peering / 对等连接 / CEN /
跨地域内网互通" applied to two or more VPCs.

**Non-obvious requirement**: creating only the peering or CEN attachment does
not make traffic flow. Route entries on the participating route tables are
required. For cross-region or many-VPC topologies, prefer CEN; for simple
same-region pairwise connectivity, VPC peering is usually simpler.

| User intent | Required resource pattern |
| --- | --- |
| Same-region two-VPC peering | Peering connection plus route entries in both VPC route tables. |
| Cross-region or hub-spoke connectivity | CEN instance, transit router or attachment resources, plus route propagation/entries. |

**Sketch**:

```hcl
resource "alicloud_vpc_peer_connection" "this" {
  accepting_ali_uid = var.peer_account_id
  vpc_id            = alicloud_vpc.left.id
  accepting_vpc_id  = alicloud_vpc.right.id
}

resource "alicloud_route_entry" "left_to_right" {
  route_table_id        = alicloud_vpc.left.route_table_id
  destination_cidrblock = alicloud_vpc.right.cidr_block
  nexthop_type          = "VpcPeer"
  nexthop_id            = alicloud_vpc_peer_connection.this.id
}
```

---

## ACK managed cluster — node pool is not optional

**Trigger phrases**: "ACK / Kubernetes / K8s / 托管集群 / managed cluster /
node pool / 节点池".

**Non-obvious requirement**: a managed ACK control plane alone does not provide
worker capacity. If the user asks for a usable cluster for workloads, include a
node pool (or explicitly state that only the control plane is being created).
Use VSwitch data/resources across the requested zones and avoid hardcoded image
or instance type IDs.

| Resource | Purpose |
| --- | --- |
| `alicloud_cs_managed_kubernetes` | Managed ACK control plane. |
| `alicloud_cs_kubernetes_node_pool` | Worker nodes, scaling bounds, instance types, and VSwitch placement. |
| `alicloud_vpc` / `alicloud_vswitch` | Network placement when the user does not provide existing IDs. |

**Sketch**:

```hcl
resource "alicloud_cs_managed_kubernetes" "this" {
  name              = "${var.project_name}-ack"
  cluster_spec      = "ack.pro.small"
  worker_vswitch_ids = [alicloud_vswitch.app_a.id, alicloud_vswitch.app_b.id]
}

resource "alicloud_cs_kubernetes_node_pool" "default" {
  cluster_id            = alicloud_cs_managed_kubernetes.this.id
  node_pool_name        = "default"
  vswitch_ids           = [alicloud_vswitch.app_a.id, alicloud_vswitch.app_b.id]
  instance_types        = data.alicloud_instance_types.worker.ids
  desired_size          = var.node_pool_desired_size
  system_disk_category  = "cloud_essd"
  system_disk_size      = 120
}
```

---

## NAT Gateway — SNAT requires an EIP and SNAT entry

**Trigger phrases**: "公网出网 / SNAT / NAT 网关 / 私网 ECS 访问公网 /
egress internet".

**Non-obvious requirement**: a NAT gateway alone does not provide outbound
internet access. You must associate an EIP with the NAT gateway and create a
SNAT entry for the target VSwitch CIDR or VSwitch ID. For inbound publishing,
DNAT is a different feature and should not be generated unless requested.

| Resource | Purpose |
| --- | --- |
| `alicloud_nat_gateway` | NAT gateway in the VPC. |
| `alicloud_eip_address` + association | Public IP used by the NAT gateway. |
| `alicloud_snat_entry` | Enables outbound access for a VSwitch/CIDR. |

**Sketch**:

```hcl
resource "alicloud_nat_gateway" "this" {
  vpc_id           = alicloud_vpc.this.id
  nat_gateway_name = "${var.project_name}-nat"
  payment_type     = "PayAsYouGo"
}

resource "alicloud_eip_address" "nat" {
  address_name = "${var.project_name}-nat-eip"
}

resource "alicloud_snat_entry" "app" {
  snat_table_id     = alicloud_nat_gateway.this.snat_table_ids
  source_vswitch_id = alicloud_vswitch.app.id
  snat_ip           = alicloud_eip_address.nat.ip_address
}
```

---

## ALB / SLB — listener and backend group complete the load balancer

**Trigger phrases**: "负载均衡 / load balancer / ALB / SLB / listener /
后端服务器组 / backend server group".

**Non-obvious requirement**: creating only the load balancer is incomplete for
traffic. A usable ALB needs at least a server group, listener, and backend
server attachment. Classic SLB similarly needs listener configuration and
backend attachments. Do not mix ALB and classic SLB resources in one pattern.

| Product | Required resource pattern |
| --- | --- |
| ALB | `alicloud_alb_load_balancer` + `alicloud_alb_server_group` + listener + backend server attachment. |
| Classic SLB | `alicloud_slb_load_balancer` + listener + backend server attachment. |

**Sketch**:

```hcl
resource "alicloud_alb_load_balancer" "this" {
  load_balancer_name = "${var.project_name}-alb"
  load_balancer_edition = "Basic"
  vpc_id = alicloud_vpc.this.id
}

resource "alicloud_alb_server_group" "web" {
  server_group_name = "${var.project_name}-web"
  vpc_id            = alicloud_vpc.this.id
  protocol          = "HTTP"
}

resource "alicloud_alb_listener" "http" {
  load_balancer_id     = alicloud_alb_load_balancer.this.id
  listener_protocol    = "HTTP"
  listener_port        = 80
  default_actions {
    type = "ForwardGroup"
    forward_group_config {
      server_group_tuples {
        server_group_id = alicloud_alb_server_group.web.id
      }
    }
  }
}
```

---

## How to extend

Add a new `##` section per product when you find a pattern that:

1. Is a real product idiom (not a workaround for a bug).
2. Is not obvious from the provider doc alone — the doc technically
   documents it but does not emphasize it, so agents miss it.
3. Is NOT already captured as a rename / split / soft-split in
   `deprecated-fields.md` — that file owns deprecation-style patterns.

Each entry: trigger phrases → non-obvious requirement → table of
attributes → short HCL sketch.
