#!/bin/bash
# 按依赖顺序批量执行 terraform import
# 使用前：替换所有 <xxx> 占位符为实际资源 ID

set -e
REGION="cn-hangzhou"

# 幂等性检查：若资源已在 state 中则跳过
import_if_not_exists() {
  local resource="$1"
  local id="$2"
  if terraform state list 2>/dev/null | grep -q "^${resource}$"; then
    echo "  [跳过] $resource 已在 state 中"
  else
    echo "  [导入] $resource <- $id"
    terraform import "$resource" "$id"
  fi
}

echo "=== 批次 1: 网络基础 ==="
import_if_not_exists "alicloud_vpc.vpc_prod_main"        "vpc-bp1xxxxxxxxxxxxxxx"
import_if_not_exists "alicloud_vswitch.vsw_prod_a"       "vsw-bp1xxxxxxxxxxxxxxx"
import_if_not_exists "alicloud_vswitch.vsw_prod_b"       "vsw-bp2xxxxxxxxxxxxxxx"
import_if_not_exists "alicloud_security_group.sg_web"    "sg-bp1xxxxxxxxxxxxxxxx"
import_if_not_exists "alicloud_security_group.sg_db"     "sg-bp2xxxxxxxxxxxxxxxx"

echo ""
echo "=== 批次 2: 网络附属 ==="
import_if_not_exists "alicloud_eip_address.eip_nat"      "eip-bp1xxxxxxxxxxxxxxx"
import_if_not_exists "alicloud_nat_gateway.nat_prod"     "ngw-bp1xxxxxxxxxxxxxx"

echo ""
echo "=== 批次 3: 计算资源 ==="
import_if_not_exists "alicloud_instance.ecs_web_01"      "i-bp1xxxxxxxxxxxxxxxx"
import_if_not_exists "alicloud_instance.ecs_web_02"      "i-bp2xxxxxxxxxxxxxxxx"

echo ""
echo "=== 批次 4: 存储资源 ==="
import_if_not_exists "alicloud_oss_bucket.bucket_assets" "my-assets-bucket"
import_if_not_exists "alicloud_disk.disk_data_01"        "d-bp1xxxxxxxxxxxxxxxx"

echo ""
echo "=== 批次 5: 数据库资源 ==="
import_if_not_exists "alicloud_db_instance.rds_app"      "rm-bp1xxxxxxxxxxxxxx"
import_if_not_exists "alicloud_kvstore_instance.redis_cache" "r-bp1xxxxxxxxxxxxxxx"
import_if_not_exists "alicloud_mongodb_instance.mongo_app"   "dds-bp1xxxxxxxxxxxxx"

echo ""
echo "=== 批次 6: 负载均衡 ==="
import_if_not_exists "alicloud_slb_load_balancer.slb_web" "lb-bp1xxxxxxxxxxxxxxx"

echo ""
echo "=== 批次 7: DNS ==="
import_if_not_exists "alicloud_dns_domain.domain_example" "example.com"

echo ""
echo "=== 导入完成，执行验证 ==="
terraform state list | wc -l | xargs -I{} echo "State 中共 {} 个资源"
echo "运行 terraform plan 验证..."
terraform plan -refresh=true
