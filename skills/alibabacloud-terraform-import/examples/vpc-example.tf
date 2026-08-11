# VPC 相关资源示例

resource "alicloud_vpc" "vpc_prod_main" {
  vpc_name    = "prod-main"
  cidr_block  = "10.0.0.0/8"
  description = "生产环境主 VPC"
  tags = {
    Env  = "production"
    Team = "infra"
  }
}

resource "alicloud_vswitch" "vsw_prod_a" {
  vswitch_name = "prod-a"
  vpc_id       = alicloud_vpc.vpc_prod_main.id
  cidr_block   = "10.0.1.0/24"
  zone_id      = "cn-hangzhou-h"
  tags = {
    Env = "production"
  }
}

resource "alicloud_vswitch" "vsw_prod_b" {
  vswitch_name = "prod-b"
  vpc_id       = alicloud_vpc.vpc_prod_main.id
  cidr_block   = "10.0.2.0/24"
  zone_id      = "cn-hangzhou-i"
  tags = {
    Env = "production"
  }
}

resource "alicloud_security_group" "sg_web" {
  security_group_name = "sg-web"
  vpc_id              = alicloud_vpc.vpc_prod_main.id
  description         = "Web 层安全组"
  tags = {}
}

resource "alicloud_security_group_rule" "sgr_web_ingress_80" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "80/80"
  security_group_id = alicloud_security_group.sg_web.id
  cidr_ip           = "0.0.0.0/0"
  policy            = "accept"
  priority          = 1
}

resource "alicloud_security_group_rule" "sgr_web_ingress_443" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "443/443"
  security_group_id = alicloud_security_group.sg_web.id
  cidr_ip           = "0.0.0.0/0"
  policy            = "accept"
  priority          = 1
}

resource "alicloud_security_group_rule" "sgr_web_egress_all" {
  type              = "egress"
  ip_protocol       = "all"
  port_range        = "-1/-1"
  security_group_id = alicloud_security_group.sg_web.id
  cidr_ip           = "0.0.0.0/0"
  policy            = "accept"
  priority          = 1
}

resource "alicloud_eip_address" "eip_nat" {
  address_name         = "eip-nat"
  payment_type         = "PayAsYouGo"
  internet_charge_type = "PayByTraffic"
  bandwidth            = "100"
  isp                  = "BGP"
  tags = {}
}

resource "alicloud_nat_gateway" "nat_prod" {
  vpc_id           = alicloud_vpc.vpc_prod_main.id
  vswitch_id       = alicloud_vswitch.vsw_prod_a.id
  nat_gateway_name = "nat-prod"
  nat_type         = "Enhanced"
  payment_type     = "PayAsYouGo"
  tags = {}
}

resource "alicloud_eip_association" "eip_assoc_nat" {
  allocation_id = alicloud_eip_address.eip_nat.id
  instance_id   = alicloud_nat_gateway.nat_prod.id
  instance_type = "Nat"
}

resource "alicloud_snat_entry" "snat_prod_a" {
  snat_table_id     = split(",", alicloud_nat_gateway.nat_prod.snat_table_ids)[0]
  source_vswitch_id = alicloud_vswitch.vsw_prod_a.id
  snat_ip           = alicloud_eip_address.eip_nat.ip_address
}

resource "alicloud_snat_entry" "snat_prod_b" {
  snat_table_id     = split(",", alicloud_nat_gateway.nat_prod.snat_table_ids)[0]
  source_vswitch_id = alicloud_vswitch.vsw_prod_b.id
  snat_ip           = alicloud_eip_address.eip_nat.ip_address
}
