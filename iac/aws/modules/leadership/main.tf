# ─────────────────────────────────────────────────────────────────────────────
# Leadership Board S3 and Origin Access Control
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "leadership" {
  bucket = "leadership-board-site-${var.environment}"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = "leadership"
    Company     = "TestingFantasy"
  }
}

resource "aws_s3_bucket_public_access_block" "leadership" {
  bucket = aws_s3_bucket.leadership.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "leadership" {
  name                              = "leadership-fellowship-${var.environment}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
