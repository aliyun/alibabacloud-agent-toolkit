# ResourceCenter API Guide

Four APIs form the complete resource discovery and relationship building pipeline, with native product APIs as fallback.
IaCService `get-provider-document` is an on-demand supplement for long-tail
resources, import ID formats, and provider field references.

> Execution rule: run all `aliyun iacservice ...` and
> `aliyun resourcecenter ...` commands in this document through the
> alibabacloud-core MCP CallCLI-compatible tool. Treat code blocks as command
> references; pass one resolved `aliyun ...` command per CallCLI invocation.
> Always include `--endpoint resourcecenter.aliyuncs.com` on ResourceCenter
> commands; some CLI plugin versions do not auto-resolve this endpoint.

API documentation entry: `https://api.aliyun.com/api/ResourceCenter/2022-12-01/`

---

## Prerequisite API: IaCService ListResourceTypes

**Called once during Phase 3 initialization to build a `terraformResourceType <-> ResourceCode` mapping table, cached to `.import/resource-type-mapping.json` for use throughout the session.**

```bash
aliyun iacservice list-resource-types \
  --endpoint iacservice.aliyuncs.com \
  --status Available \
  --max-results 200
```

If results exceed 200 entries, use `nextToken` to paginate and retrieve all data.

**Key return fields:**

```json
{
  "resourceTypes": [
    {
      "terraformResourceType": "alicloud_eip_address",
      "resourceType": "ALIYUN::EIP::Address",
      "product": "EIP",
      "supportTerraformer": true,
      "status": "Available"
    }
  ]
}
```

**Mapping rules:**

Replace the `ALIYUN` prefix in the `resourceType` field with `ACS` to get the ResourceCode required by ResourceCenter APIs:

```
ALIYUN::EIP::Address  ->  ACS::EIP::Address
ALIYUN::VPC::VPC      ->  ACS::VPC::VPC
ALIYUN::ECS::Instance ->  ACS::ECS::Instance
```

**Mapping table structure (`.import/resource-type-mapping.json`):**

```json
{
  "byTerraformType": {
    "alicloud_eip_address": {
      "resourceCode": "ACS::EIP::Address",
      "product": "EIP",
      "supportTerraformer": true
    },
    "alicloud_vpc": {
      "resourceCode": "ACS::VPC::VPC",
      "product": "VPC",
      "supportTerraformer": true
    }
  },
  "byResourceCode": {
    "ACS::EIP::Address": "alicloud_eip_address",
    "ACS::VPC::VPC": "alicloud_vpc"
  }
}
```

**Usage:**

- Phase 4: Known `terraformResourceType` -> Look up `byTerraformType` -> Get `resourceCode` -> Call search-resources
- Phase 6: ResourceCenter returns `ResourceType` -> Look up `byResourceCode` -> Get `terraformResourceType` -> Generate correct HCL resource type. If `byResourceCode` has no match, check the **ResourceCenter Type Alias Table** (below the static mapping table) for an alias entry before falling back to LLM reasoning
- Unsupported-resource detection: if a ResourceCenter `ResourceType` is absent
  from the IaCService mapping table and the alias table, treat it as not covered
  by the standard import path. Check provider docs for a matching resource before
  attempting manual tfstate construction; if none exists, report that Terraform
  import is currently unsupported for that cloud resource type.

**Fallback conditions:**

- Call fails or insufficient permissions -> Fall back to the static mapping table at the end of this file
- Mapping table has no corresponding entry AND alias table has no match -> Skip API A/B, use native product API directly
- ResourceCenter can discover a resource but no Terraform mapping exists -> do
  not generate HCL from ResourceCenter metadata alone; either find a provider
  resource in docs or mark the resource unsupported for standard import

---

## Provider Documentation API: IaCService GetProviderDocument

Use this API on demand for long-tail resources, uncertain HCL fields, or import
ID formats not covered by `references/resource-types.md`. Do not call it for
every resource on the fast path.

```bash
aliyun iacservice get-provider-document \
  --resource-type alicloud_<name> \
  --endpoint iac.cn-zhangjiakou.aliyuncs.com
```

When available, `--provider-version <version>` may be added after resolving the
provider version from the initialized working directory or IaCService provider
version metadata. If omitted, IaCService should use its default/latest supported
provider documentation.

**Extraction rules:**

- Read only the sections required for the current action: `Import`, `Argument
  Reference`, and `Attributes Reference`.
- Cache one compact entry per `terraformResourceType` in
  `.import/provider-doc-index.json`.
- For import command generation, trust the `Import` section over memory. If the
  document has no `Import` section, do not run `terraform import` blindly.
- If the API fails, fall back to local references for common resources or the
  provider registry/GitHub documentation only when the host environment has an
  approved documentation fetch path.

---

## API One: list-resource-types

Query resource types supported by ResourceCenter, used to determine the support scope of API A (search-resources) and API B (list-resource-relationships).

**Called once before Phase 4 begins, results cached for use throughout the session.**

```bash
aliyun resourcecenter list-resource-types --endpoint resourcecenter.aliyuncs.com
```

**Key return fields:**

```json
{
  "ResourceTypes": [
    {
      "ResourceType": "ACS::ECS::Instance"
    }
  ]
}
```

Do not rely on a `SupportedFeatures` field to determine API A/B support. Some
accounts or CLI/plugin versions return only `ResourceType`. Treat this API as a
candidate type list, then probe `search-resources` or
`list-resource-relationships` for the target resource type. Cache successful and
failed probes for the session to avoid repeated calls.

**Fallback conditions:**

- Call returns permission error (`AccessDenied`) -> Fall back for the entire session, skip API A and API B
- Call times out or returns empty list -> Same as above

---

## API A: search-resources

Search resources accessible by the current account. **Returns basic resource metadata, not business attributes** (such as VPC CidrBlock, ECS InstanceType, etc.). Phase 6 HCL generation still requires native product API calls for complete attributes; search-resources is only used during Phase 4 resource discovery.

**Basic usage:**

```bash
aliyun resourcecenter search-resources \
  --endpoint resourcecenter.aliyuncs.com \
  --filter '[{"Key":"ResourceType","MatchType":"Equals","Value":["ACS::ECS::Instance"]}]' \
  --max-results 50
```

**Supported filter conditions:**

| Filter Parameter | Supported Match Types |
|---------|-------------|
| `ResourceType` | Equals |
| `RegionId` | Equals |
| `ResourceId` | Equals, Prefix |
| `ResourceName` | Equals, Contains |
| `Tag` | Contains, NotContains, NotExists (JSON format: `{"key":"k","value":"v"}`) |
| `VpcId` | Equals |
| `VSwitchId` | Equals |
| `IpAddress` | Equals, Contains |
| `ResourceGroupId` | Equals, Exists, NotExists |

Multiple filter conditions have AND relationship; multiple values within the same condition have OR relationship.

**Filter by Region + resource type:**

```bash
aliyun resourcecenter search-resources \
  --endpoint resourcecenter.aliyuncs.com \
  --filter '[{"Key":"ResourceType","MatchType":"Equals","Value":["ACS::ECS::Instance"]},{"Key":"RegionId","MatchType":"Equals","Value":["cn-hangzhou"]}]' \
  --max-results 50
```

**Query by resource ID (to confirm resource type):**

```bash
aliyun resourcecenter search-resources \
  --endpoint resourcecenter.aliyuncs.com \
  --filter '[{"Key":"ResourceId","MatchType":"Equals","Value":["vpc-bp1xxx"]}]' \
  --max-results 1
```

**Pagination:**

```bash
aliyun resourcecenter search-resources \
  --endpoint resourcecenter.aliyuncs.com \
  --filter '[...]' \
  --max-results 50 \
  --next-token <NextToken from previous page>
```

No `NextToken` in results indicates no more data. MaxResults maximum is 500.

**Return fields:**

```json
{
  "Resources": [
    {
      "AccountId": "151266687691****",
      "ResourceId": "vtb-bp1xxx",
      "ResourceType": "ACS::VPC::RouteTable",
      "ResourceName": "group1",
      "RegionId": "cn-hangzhou",
      "ZoneId": "cn-hangzhou-k",
      "ResourceGroupId": "rg-acfmzawhxxc****",
      "CreateTime": "2021-06-30T09:20:08Z",
      "ExpireTime": "2021-07-30T09:20:08Z",
      "IpAddresses": ["192.168.1.2"],
      "IpAddressAttributes": [
        {"IpAddress": "192.168.1.2", "NetworkType": "Public", "Version": "Ipv4"}
      ],
      "Tags": [{"Key": "test_key", "Value": "test_value"}],
      "Deleted": false
    }
  ],
  "NextToken": "eyJzZWFyY2hBZnRlcnMiOlsiMTAwMTU2Nzk4MTU1OSJd****"
}
```

Note: Whether fields like `ZoneId`, `CreateTime`, `IpAddresses` are returned depends on each cloud service; not guaranteed for all resource types.

**Resource type format (`ACS::<Product>::<ResourceType>`):**

| Cloud Product | ResourceCenter Type |
|--------|-------------------|
| VPC | `ACS::VPC::VPC` |
| VSwitch | `ACS::VPC::VSwitch` |
| Route Table | `ACS::VPC::RouteTable` |
| EIP | `ACS::VPC::EipAddress` |

Complete list obtained dynamically via `iacservice list-resource-types`. Static fallback mapping table below:

| Terraform Resource Type | ResourceCode |
|-------------------|-------------|
| `alicloud_vpc` | `ACS::VPC::VPC` |
| `alicloud_vswitch` | `ACS::VPC::VSwitch` |
| `alicloud_route_table` | `ACS::VPC::RouteTable` |
| `alicloud_eip_address` | `ACS::EIP::Address` |
| `alicloud_nat_gateway` | `ACS::VPC::NatGateway` |
| `alicloud_instance` | `ACS::ECS::Instance` |
| `alicloud_security_group` | `ACS::ECS::SecurityGroup` |
| `alicloud_db_instance` | `ACS::RDS::DBInstance` |
| `alicloud_kvstore_instance` | `ACS::KVStore::Instance` |
| `alicloud_mongodb_instance` | `ACS::DDS::DBInstance` |
| `alicloud_oss_bucket` | `ACS::OSS::Bucket` |
| `alicloud_slb_load_balancer` | `ACS::SLB::LoadBalancer` |
| `alicloud_cs_managed_kubernetes` | `ACS::CS::KubernetesCluster` |

**ResourceCenter Type Alias Table (code inconsistency fix):**

The following resource types use different codes in ResourceCenter vs IaCService mapping table. When building `.import/resource-type-mapping.json` in Phase 3, these aliases must also be written into `byResourceCode` so that Phase 4/6 lookups succeed without falling back to LLM reasoning.

| ResourceCenter Type (actual) | IaCService Equivalent Code | Terraform Resource |
|------------------------------|---------------------------|-------------------|
| `ACS::EIP::EipAddress` | `ACS::EIP::Address` | `alicloud_eip_address` |
| `ACS::NAT::NatGateway` | `ACS::VPC::NatGateway` | `alicloud_nat_gateway` |
| `ACS::MongoDB::DBInstance` | `ACS::DDS::DBInstance` | `alicloud_mongodb_instance` |
| `ACS::ESS::ScalingGroup` | `ACS::ESS::ScalingGroup` | `alicloud_ess_scaling_group` |
| `ACS::VPN::VpnGateway` | `ACS::VPN::VpnGateway` | `alicloud_vpn_gateway` |
| `ACS::VPN::CustomerGateway` | `ACS::VPN::CustomerGateway` | `alicloud_vpn_customer_gateway` |
| `ACS::VPN::VpnConnection` | `ACS::VPN::VpnConnection` | `alicloud_vpn_connection` |
| `ACS::VPN::SslVpnServer` | `ACS::VPN::SslVpnServer` | `alicloud_ssl_vpn_server` |
| `ACS::VPN::SslVpnClientCert` | `ACS::VPN::SslVpnClientCert` | `alicloud_ssl_vpn_client_cert` |
| `ACS::SLS::Project` | `ACS::SLS::Project` | `alicloud_log_project` |
| `ACS::SLB::CACertificate` | `ACS::SLB::CACertificate` | `alicloud_slb_ca_certificate` |
| `ACS::CR::Instance` | `ACS::CR::Instance` | `alicloud_cr_ee_instance` |
| `ACS::CR::Repository` | `ACS::CR::Repository` | `alicloud_cr_ee_repo` |
| `ACS::CEN::RouteMap` | `ACS::CEN::RouteMap` | `alicloud_cen_route_map` |
| `ACS::ACK::Cluster` | `ACS::CS::ManagedKubernetes` | `alicloud_cs_managed_kubernetes` |

Known ResourceCenter gaps:

- `ACS::NAT::NatGateway` may appear in mapping or alias tables but still be
  unavailable through `search-resources` in some accounts. Use native
  `vpc describe-nat-gateways` as the discovery fallback.

**Fallback conditions:**

- Resource type is not in the list returned by `list-resource-types`
- Call returns `NoPermission` or other errors
- In these cases, fall back to native product APIs in `references/api-commands.md`
- Resource type is returned by ResourceCenter but has no IaCService/alias
  Terraform mapping: use it for inventory reporting only, not HCL generation.

---

## API B: list-resource-relationships

Query relationships between a specified resource and its related resources, used to dynamically build the resource dependency graph. **`RegionId`, `ResourceType`, and `ResourceId` are all required parameters.**

Results are a flat list where each record represents an association between "current resource" and "a related resource". **Direction is not distinguished** (no parent-child or lateral distinction); the caller determines dependency direction based on business semantics.

**Basic usage:**

```bash
aliyun resourcecenter list-resource-relationships \
  --endpoint resourcecenter.aliyuncs.com \
  --biz-region-id cn-hangzhou \
  --resource-type ACS::VPC::VPC \
  --resource-id vpc-bp1xxx
```

**Filter by related resource type (only VSwitch):**

```bash
aliyun resourcecenter list-resource-relationships \
  --endpoint resourcecenter.aliyuncs.com \
  --biz-region-id cn-hangzhou \
  --resource-type ACS::VPC::VPC \
  --resource-id vpc-bp1xxx \
  --related-resource-filter '[{"Key":"RelatedResourceType","MatchType":"Equals","Value":["ACS::VPC::VSwitch"]}]'
```

**Pagination:**

```bash
aliyun resourcecenter list-resource-relationships \
  --endpoint resourcecenter.aliyuncs.com \
  --biz-region-id cn-hangzhou \
  --resource-type ACS::VPC::VPC \
  --resource-id vpc-bp1xxx \
  --max-results 50 \
  --next-token <NextToken from previous page>
```

MaxResults range is 1-500, default 20.

**Supported RelatedResourceFilter parameters:**

| Parameter | Description | Supported Match Types |
|------|------|-------------|
| `RelatedResourceRegionId` | Related resource region ID | Equals |
| `RelatedResourceType` | Related resource type | Equals |
| `RelatedResourceId` | Related resource ID | Equals |

**Return fields:**

```json
{
  "ResourceRelationships": [
    {
      "RegionId": "cn-hangzhou",
      "ResourceType": "ACS::ACK::Cluster",
      "ResourceId": "m-eb3hji****",
      "RelatedResourceRegionId": "cn-shanghai",
      "RelatedResourceType": "ACS::VPC::VPC",
      "RelatedResourceId": "vpc-uf6m5okksddm6c9lh7***"
    }
  ],
  "NextToken": "eyJzZWFyY2hBZnRlcnMiOlsiMTAwMTU2Nzk4MTU1OSJd****"
}
```

Note: Related resources may be in different Regions (`RelatedResourceRegionId` differs from the requested `RegionId`); be aware of cross-Region associations.

**Phase 5 usage:**

1. From Phase 4 discovered resources, identify root resources (VPC, OSS Bucket, DNS domains, RAM users, etc. with no parent dependencies)
2. For each root resource, call API B to get all related resources
3. Recursively call API B for related resources until no new resources appear, building the complete relationship graph
4. Dependency direction is determined by business semantics: VPC -> VSwitch (VSwitch depends on VPC), VSwitch -> ECS (ECS depends on VSwitch), etc. Refer to `references/dependency-rules.md`
5. Topologically sort the relationship graph to generate import order

**Phase 6 usage:**

For related resources discovered via API B, their dependency relationships are already determined. Combined with the reference field whitelist extracted in Phase 3, find the corresponding `_id` fields in the current resource and directly replace with terraform resource address, without guessing.

**Fallback conditions:**

- Resource type is not in the list returned by `list-resource-types`
- Call returns `NoPermission` or other errors
- In these cases, fall back to static rules in `references/dependency-rules.md`
