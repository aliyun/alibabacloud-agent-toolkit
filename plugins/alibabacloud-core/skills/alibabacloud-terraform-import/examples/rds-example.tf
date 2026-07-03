# 数据库相关资源示例

variable "rds_password"   { sensitive = true }
variable "redis_password" { sensitive = true }
variable "mongo_password" { sensitive = true }

# RDS MySQL
resource "alicloud_db_instance" "rds_app" {
  engine           = "MySQL"
  engine_version   = "8.0"
  instance_type    = "rds.mysql.s2.large"
  instance_storage = 20
  instance_name    = "rds-app"
  vswitch_id       = alicloud_vswitch.vsw_prod_a.id
  security_ips     = ["10.0.0.0/8"]
  payment_type     = "Postpaid"
  tags = {
    Env = "production"
  }
  lifecycle {
    ignore_changes = [instance_storage]
  }
}

resource "alicloud_db_database" "db_app_main" {
  instance_id   = alicloud_db_instance.rds_app.id
  name          = "app_main"
  character_set = "utf8mb4"
  description   = "主业务数据库"
}

resource "alicloud_db_account" "dba_app" {
  db_instance_id   = alicloud_db_instance.rds_app.id
  account_name     = "app_user"
  account_password = var.rds_password
  account_type     = "Normal"
  lifecycle {
    ignore_changes = [account_password]
  }
}

# Redis（KVStore）
resource "alicloud_kvstore_instance" "redis_cache" {
  db_instance_class = "redis.master.small.default"
  instance_name     = "redis-cache"
  vswitch_id        = alicloud_vswitch.vsw_prod_a.id
  engine_version    = "7.0"
  instance_type     = "Redis"
  payment_type      = "PostPaid"
  security_ips      = ["10.0.0.0/8"]
  tags = {
    Env = "production"
  }
  lifecycle {
    ignore_changes = [password]
  }
}

# MongoDB（DDS）
resource "alicloud_mongodb_instance" "mongo_app" {
  engine_version      = "6.0"
  db_instance_class   = "dds.mongo.mid"
  db_instance_storage = 10
  name                = "mongo-app"
  vswitch_id          = alicloud_vswitch.vsw_prod_a.id
  security_ip_list    = ["10.0.0.0/8"]
  payment_type        = "PostPaid"
  tags = {
    Env = "production"
  }
  lifecycle {
    ignore_changes = [account_password]
  }
}
