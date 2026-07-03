# OSS 相关资源示例

resource "alicloud_oss_bucket" "bucket_assets" {
  bucket          = "my-assets-bucket"
  acl             = "private"
  force_destroy   = false
  redundancy_type = "LRS"

  versioning {
    status = "Enabled"
  }

  lifecycle_rule {
    id      = "expire-logs"
    enabled = true
    prefix  = "logs/"
    expiration {
      days = 30
    }
  }

  lifecycle_rule {
    id      = "expire-tmp"
    enabled = true
    prefix  = "tmp/"
    expiration {
      days = 7
    }
  }

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["https://example.com"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }

  server_side_encryption_rule {
    sse_algorithm = "AES256"
  }

  tags = {
    Env     = "production"
    Purpose = "static-assets"
  }
}

resource "alicloud_oss_bucket" "bucket_backup" {
  bucket          = "my-backup-bucket"
  acl             = "private"
  force_destroy   = false
  redundancy_type = "LRS"

  versioning {
    status = "Enabled"
  }

  lifecycle_rule {
    id      = "transition-to-ia"
    enabled = true
    prefix  = ""
    transitions {
      days          = 30
      storage_class = "IA"
    }
    transitions {
      days          = 90
      storage_class = "Archive"
    }
  }

  tags = {
    Env     = "production"
    Purpose = "backup"
  }
}
