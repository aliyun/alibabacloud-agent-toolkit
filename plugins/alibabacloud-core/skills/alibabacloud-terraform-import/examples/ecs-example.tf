# ECS 相关资源示例

variable "ecs_password" {
  description = "ECS 实例登录密码"
  sensitive   = true
  default     = ""
}

resource "alicloud_instance" "ecs_web_01" {
  instance_name        = "web-01"
  instance_type        = "ecs.c6.large"
  image_id             = "aliyun_3_x64_20G_alibase_20240528.vhd"
  system_disk_category = "cloud_essd"
  system_disk_size     = 40

  vswitch_id        = alicloud_vswitch.vsw_prod_a.id
  security_groups   = [alicloud_security_group.sg_web.id]
  availability_zone = "cn-hangzhou-h"

  internet_max_bandwidth_out = 0
  internet_charge_type       = "PayByTraffic"

  key_name    = "my-key-pair"
  description = "Web 服务器 01"
  host_name   = "web-01"

  tags = {
    Env  = "production"
    Role = "web"
  }

  lifecycle {
    ignore_changes = [image_id, password, user_data]
  }
}

resource "alicloud_instance" "ecs_web_02" {
  instance_name        = "web-02"
  instance_type        = "ecs.c6.large"
  image_id             = "aliyun_3_x64_20G_alibase_20240528.vhd"
  system_disk_category = "cloud_essd"
  system_disk_size     = 40

  vswitch_id        = alicloud_vswitch.vsw_prod_b.id
  security_groups   = [alicloud_security_group.sg_web.id]
  availability_zone = "cn-hangzhou-i"

  internet_max_bandwidth_out = 0
  internet_charge_type       = "PayByTraffic"

  key_name    = "my-key-pair"
  description = "Web 服务器 02"
  host_name   = "web-02"

  tags = {
    Env  = "production"
    Role = "web"
  }

  lifecycle {
    ignore_changes = [image_id, password, user_data]
  }
}

resource "alicloud_disk" "disk_data_01" {
  disk_name         = "data-disk-01"
  availability_zone = "cn-hangzhou-h"
  category          = "cloud_essd"
  size              = 100
  performance_level = "PL1"
  description       = "web-01 数据盘"
  tags = {
    Env = "production"
  }
}

resource "alicloud_disk_attachment" "disk_attach_01" {
  disk_id     = alicloud_disk.disk_data_01.id
  instance_id = alicloud_instance.ecs_web_01.id
}

# 弹性伸缩组示例
resource "alicloud_ess_scaling_group" "asg_web" {
  scaling_group_name = "asg-web"
  min_size           = 2
  max_size           = 10
  desired_capacity   = 2
  vswitch_ids        = [
    alicloud_vswitch.vsw_prod_a.id,
    alicloud_vswitch.vsw_prod_b.id,
  ]
  removal_policies   = ["OldestScalingConfiguration", "OldestInstance"]
  tags = {
    Env = "production"
  }
}

resource "alicloud_ess_scaling_configuration" "asg_web_config" {
  scaling_group_id  = alicloud_ess_scaling_group.asg_web.id
  image_id          = "aliyun_3_x64_20G_alibase_20240528.vhd"
  instance_type     = "ecs.c6.large"
  security_group_id = alicloud_security_group.sg_web.id
  active            = true

  system_disk_category = "cloud_essd"
  system_disk_size     = 40

  internet_max_bandwidth_in  = 200
  internet_max_bandwidth_out = 0
  internet_charge_type       = "PayByTraffic"

  lifecycle {
    ignore_changes = [image_id]
  }
}
