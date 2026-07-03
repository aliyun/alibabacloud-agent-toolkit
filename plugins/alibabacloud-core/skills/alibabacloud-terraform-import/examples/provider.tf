terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.284.0"
    }
  }

  # 本地 state（默认）
  # backend "local" {}

  # 远程 state（OSS，推荐生产环境使用）
  # backend "oss" {
  #   bucket   = "my-terraform-state"
  #   prefix   = "alicloud-import"
  #   key      = "terraform.tfstate"
  #   region   = "cn-hangzhou"
  #   endpoint = "oss-cn-hangzhou.aliyuncs.com"
  # }
}

provider "alicloud" {
  # 凭证优先级：环境变量 > provider 配置 > shared_credentials_file
  # 若设置了 ALICLOUD_ACCESS_KEY / ALICLOUD_SECRET_KEY 环境变量，provider 将优先使用环境变量
  # 若需要使用 CLI profile，须确保环境变量未设置，或显式指定 profile：
  # profile                 = "default"
  # shared_credentials_file = pathexpand("~/.aliyun/config.json")
  region               = var.region
  configuration_source = "AlibabaCloud-Agent-Skills/alibabacloud-terraform-import"
}

variable "region" {
  description = "Alibaba Cloud Region"
  default     = "cn-hangzhou"
}
