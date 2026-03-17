# Locals for normalized naming
locals {
  # Normalize tutorial names: testus_patronus -> testus-patronus, fellowship-of-the-build -> fellowship, shared -> common
  normalized_tutorial_name = replace(
    replace(
      replace(var.workshop_name, "testus_patronus", "testus-patronus"),
      "fellowship-of-the-build",
      "fellowship"
    ),
    "shared",
    "common"
  )
  # Convert region to region code (eu-west-1 -> euwest1)
  region_code = replace(var.region, "-", "")
}

# S3 Bucket for workshop setup scripts (fellowship SUT or testus_patronus setup script)
resource "aws_s3_bucket" "sut" {
  bucket = var.workshop_name == "testus_patronus" ? "s3-testus-patronus-setup-${var.environment}-${local.region_code}" : "s3-fellowship-sut-${var.environment}-${local.region_code}"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
    Purpose     = var.workshop_name == "testus_patronus" ? "testus-patronus-setup-script" : "fellowship-sut-deployment"
  }
}

# Block public access (only EC2 instances with IAM role can access)
resource "aws_s3_bucket_public_access_block" "sut" {
  bucket = aws_s3_bucket.sut.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning for rollback capability
resource "aws_s3_bucket_versioning" "sut" {
  bucket = aws_s3_bucket.sut.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle policy to clean old versions (optional, for cost optimization)
resource "aws_s3_bucket_lifecycle_configuration" "sut" {
  bucket = aws_s3_bucket.sut.id

  rule {
    id     = "cleanup-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}
