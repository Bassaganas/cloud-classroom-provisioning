# ACM Certificate for custom domain (must be in us-east-1 for CloudFront)
resource "aws_acm_certificate" "cert" {
  provider = aws.us_east_1

  domain_name       = var.domain_name
  validation_method = "DNS"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Certificate validation (manual DNS validation required)
# This is optional - set wait_for_certificate_validation = true only after DNS records are added
# Using for_each instead of count to avoid Terraform evaluation issues
resource "aws_acm_certificate_validation" "cert" {
  for_each = { create = true }

  provider = aws.us_east_1

  certificate_arn = aws_acm_certificate.cert.arn

  # Increase timeout to 10 minutes to allow time for DNS propagation
  timeouts {
    create = "10m"
  }
}

# CloudFront Distribution
# Only create if wait_for_certificate_validation is true (certificate must be validated)
# CloudFront requires a validated certificate to work with custom domains
# Using for_each instead of count to avoid Terraform evaluation issues
resource "aws_cloudfront_distribution" "distribution" {
  for_each = { create = true }

  enabled             = true
  is_ipv6_enabled      = true
  comment              = "CloudFront distribution for ${var.domain_name}"
  # Don't set default_root_object for Lambda Function URLs - they handle paths directly
  # default_root_object  = "index.html"

  aliases = [var.domain_name]

  origin {
    domain_name = replace(replace(var.lambda_function_url, "https://", ""), "/", "")
    origin_id   = "lambda-function-url"

    custom_origin_config {
      http_port              = 443
      https_port              = 443
      origin_protocol_policy  = "https-only"
      origin_ssl_protocols    = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD", "OPTIONS"]
    target_origin_id       = "lambda-function-url"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    # Use legacy forwarded_values - forward query strings and cookies, but NOT headers
    # Lambda Function URLs require CloudFront to set the Host header automatically
    # Forwarding headers (especially Host) causes 403 errors
    forwarded_values {
      query_string = true
      # Don't forward headers - let CloudFront set Host header automatically
      headers      = []
      cookies {
        forward = "all"
      }
    }

    min_ttl     = 0
    default_ttl = 0  # Don't cache API responses
    max_ttl     = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    # CloudFront requires a validated certificate - use the validation resource
    # If certificate is already validated, this will complete immediately
    acm_certificate_arn      = aws_acm_certificate_validation.cert["create"].certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version  = "TLSv1.2_2021"
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }

  # CloudFront will only be created when certificate validation is enabled
  # The validation resource will complete immediately if certificate is already validated
  depends_on = [aws_acm_certificate_validation.cert]
}

