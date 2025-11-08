# S3 Bucket for static website hosting
resource "aws_s3_bucket" "website" {
  bucket = "${var.domain_name}-website"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "testing-fantasy"
  }
}

# Block public access (CloudFront will access via OAI)
resource "aws_s3_bucket_public_access_block" "website" {
  bucket = aws_s3_bucket.website.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Note: We use S3 REST endpoint with OAI, not website endpoint
# CloudFront handles SPA routing via custom error responses

# CloudFront Origin Access Identity (OAI) for S3
resource "aws_cloudfront_origin_access_identity" "website" {
  comment = "OAI for ${var.domain_name}"
}

# S3 Bucket Policy - Allow CloudFront OAI to read
resource "aws_s3_bucket_policy" "website" {
  bucket = aws_s3_bucket.website.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.website.iam_arn
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.website.arn}/*"
      }
    ]
  })
}

# ACM Certificate for custom domain (must be in us-east-1 for CloudFront)
resource "aws_acm_certificate" "cert" {
  provider = aws.us_east_1

  domain_name       = var.domain_name
  validation_method = "DNS"

  # Include www subdomain
  subject_alternative_names = ["www.${var.domain_name}"]

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "testing-fantasy"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Certificate validation
resource "aws_acm_certificate_validation" "cert" {
  for_each = var.wait_for_certificate_validation ? { create = true } : {}

  provider = aws.us_east_1

  certificate_arn = aws_acm_certificate.cert.arn

  timeouts {
    create = "10m"
  }
}

# CloudFront Distribution for static website
resource "aws_cloudfront_distribution" "website" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "CloudFront distribution for ${var.domain_name}"
  default_root_object = "index.html"

  # Only set aliases if certificate is validated (CloudFront requires validated cert for custom domains)
  aliases = var.wait_for_certificate_validation ? [var.domain_name, "www.${var.domain_name}"] : []

  origin {
    domain_name = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.website.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.website.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.website.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # Custom error responses for SPA routing
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Viewer certificate configuration
  # When validation is enabled: use ACM certificate for custom domain
  # When validation is not enabled: use default certificate (no custom domain aliases)
  viewer_certificate {
    acm_certificate_arn      = var.wait_for_certificate_validation ? aws_acm_certificate_validation.cert["create"].certificate_arn : null
    ssl_support_method       = var.wait_for_certificate_validation ? "sni-only" : null
    minimum_protocol_version = var.wait_for_certificate_validation ? "TLSv1.2_2021" : null
    cloudfront_default_certificate = !var.wait_for_certificate_validation
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "testing-fantasy"
  }

  depends_on = [aws_s3_bucket_policy.website]
}

