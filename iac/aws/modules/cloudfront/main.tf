# Data source for Route53 hosted zone
data "aws_route53_zone" "domain" {
  name         = replace(var.domain_name, "/^[^.]+\\.(.+)$/", "$1")
  private_zone = false
}

# CloudWatch Log Group for CloudFront logs
resource "aws_cloudwatch_log_group" "cloudfront_logs" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name              = "/aws/cloudfront/${var.environment}-${var.workshop_name}"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# IAM role for CloudFront to write to CloudWatch Logs
resource "aws_iam_role" "cloudfront_logging" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name = "cloudfront-logging-${var.environment}-${var.workshop_name}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
  lifecycle {
    create_before_destroy = true
  }
}

# IAM policy for CloudFront to write to CloudWatch Logs
resource "aws_iam_role_policy" "cloudfront_logging" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name = "cloudfront-logging-policy-${var.environment}-${var.workshop_name}"
  role = aws_iam_role.cloudfront_logging[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "${aws_cloudwatch_log_group.cloudfront_logs[0].arn}:*"
      }
    ]
  })
}

# CloudFront real-time log configuration
resource "aws_cloudfront_realtime_log_config" "cloudfront_realtime_logs" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name   = "${var.environment}-${var.workshop_name}-realtime-logs"
  fields = [
    "timestamp",
    "c-ip",
    "time-to-first-byte",
    "sc-status",
    "sc-bytes",
    "cs-method",
    "cs-protocol",
    "cs-host",
    "cs-uri-stem",
    "cs-bytes",
    "x-edge-location",
    "x-edge-request-id",
    "x-host-header",
    "cs-protocol-version",
    "c-country",
    "cs-user-agent",
    "cs-referer",
    "cs-cookie",
    "cs-uri-query",
    "x-edge-response-result-type",
    "x-forwarded-for",
    "ssl-protocol",
    "ssl-cipher",
    "x-edge-result-type",
    "fle-encrypted-fields",
    "fle-status",
    "sc-content-type",
    "sc-content-len",
    "sc-range-start",
    "sc-range-end"
  ]

  sampling_rate = var.cloudfront_log_sampling_rate

  endpoint {
    stream_type = "Kinesis"

    kinesis_stream_config {
      role_arn   = aws_iam_role.cloudfront_logging[0].arn
      stream_arn = aws_kinesis_stream.cloudfront_logs[0].arn
    }
  }
  lifecycle {
    create_before_destroy = true
    ignore_changes = [name]
  }
}

# Kinesis Data Stream for CloudFront real-time logs
resource "aws_kinesis_stream" "cloudfront_logs" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name             = "cloudfront-logs-${var.environment}-${var.workshop_name}"
  shard_count      = var.kinesis_shard_count
  retention_period = var.kinesis_retention_hours

  shard_level_metrics = [
    "IncomingRecords",
    "OutgoingRecords"
  ]

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# IAM policy for CloudFront to write to Kinesis
resource "aws_iam_role_policy" "cloudfront_kinesis" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name = "cloudfront-kinesis-policy-${var.environment}-${var.workshop_name}"
  role = aws_iam_role.cloudfront_logging[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:DescribeStreamSummary",
          "kinesis:PutRecord",
          "kinesis:PutRecords"
        ]
        Resource = aws_kinesis_stream.cloudfront_logs[0].arn
      }
    ]
  })
}

# Lambda function to process Kinesis logs and send to CloudWatch Logs
resource "aws_lambda_function" "cloudfront_log_processor" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  filename         = "${path.module}/cloudfront_log_processor.zip"
  function_name    = "cloudfront-log-processor-${var.environment}-${var.workshop_name}"
  role            = aws_iam_role.lambda_log_processor[0].arn
  handler         = "index.handler"
  runtime         = "python3.11"
  timeout         = 60
  memory_size     = 256

  source_code_hash = data.archive_file.cloudfront_log_processor[0].output_base64sha256

  environment {
    variables = {
      LOG_GROUP_NAME = aws_cloudwatch_log_group.cloudfront_logs[0].name
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
  lifecycle {
    create_before_destroy = true
    ignore_changes = [filename, source_code_hash]  # Allow code updates without replacement
  }
}

# Archive file for Lambda function
data "archive_file" "cloudfront_log_processor" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  type        = "zip"
  source_file = "${path.module}/index.py"
  output_path = "${path.module}/cloudfront_log_processor.zip"
}

# IAM role for Lambda to write to CloudWatch Logs
resource "aws_iam_role" "lambda_log_processor" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name = "lambda-log-processor-${var.environment}-${var.workshop_name}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# IAM policy for Lambda to write to CloudWatch Logs and read from Kinesis
resource "aws_iam_role_policy" "lambda_log_processor" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  name = "lambda-log-processor-policy-${var.environment}-${var.workshop_name}"
  role = aws_iam_role.lambda_log_processor[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.cloudfront_logs[0].arn}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:GetShardIterator",
          "kinesis:GetRecords",
          "kinesis:ListShards"
        ]
        Resource = aws_kinesis_stream.cloudfront_logs[0].arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Event source mapping for Lambda to process Kinesis stream
resource "aws_lambda_event_source_mapping" "cloudfront_logs" {
  count = var.enable_cloudwatch_logging ? 1 : 0

  event_source_arn  = aws_kinesis_stream.cloudfront_logs[0].arn
  function_name     = aws_lambda_function.cloudfront_log_processor[0].arn
  starting_position = "LATEST"
  batch_size        = 100
  maximum_batching_window_in_seconds = 5
  lifecycle {
    create_before_destroy = true
    # Prevent errors if mapping already exists
    ignore_changes = [event_source_arn, function_name]
  }
}

# CloudFront Function to rewrite API Gateway paths to include stage
# This adds the stage prefix (e.g., /dev) to API requests before forwarding to API Gateway
# Only needed when using regional API Gateway endpoint (not custom domain)
resource "aws_cloudfront_function" "api_path_rewrite" {
  count = var.api_gateway_domain != "" && !var.use_api_gateway_custom_domain ? 1 : 0

  name    = "api-path-rewrite-${var.environment}-${var.workshop_name}"
  runtime = "cloudfront-js-1.0"
  code    = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      
      // Only rewrite paths that start with /api/ or /swagger.json
      if (uri.startsWith('/api/') || uri === '/swagger.json') {
        // Add stage prefix (e.g., /dev) to the path
        var stage = '${var.environment}';
        request.uri = '/' + stage + uri;
      }
      
      return request;
    }
  EOF

  comment = "Rewrite API paths to include API Gateway stage prefix (only for regional endpoints)"
}

# Data sources for AWS-managed CloudFront policies (AWS Best Practice)
data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

# ACM Certificate for custom domain (must be in us-east-1 for CloudFront)
resource "aws_acm_certificate" "cert" {
  provider = aws.us_east_1

  domain_name       = var.domain_name
  validation_method = "DNS"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Certificate validation (manual DNS validation required)
# This is optional - set wait_for_certificate_validation = true only after DNS records are added
# Using for_each instead of count to avoid Terraform evaluation issues
resource "aws_acm_certificate_validation" "cert" {
  for_each = var.wait_for_certificate_validation ? { create = true } : {}

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
  for_each = var.wait_for_certificate_validation ? { create = true } : {}

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "CloudFront distribution for ${var.domain_name}"
  default_root_object = "index.html" # For SPA routing

  aliases = [var.domain_name]

  # API Gateway origin for API (preferred)
  dynamic "origin" {
    for_each = var.api_gateway_domain != "" ? [1] : []
    content {
      domain_name = var.api_gateway_domain
      origin_id   = "api-gateway"
      # No origin_path - API Gateway stage will be added via CloudFront Function if needed
      # CloudFront forwards /api/* directly to API Gateway
      # Note: API Gateway REST API requires stage in path, so we use origin_request_policy
      # to rewrite the path, or rely on API Gateway's base path mapping if using custom domain

      custom_origin_config {
        http_port              = 443
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  # Lambda Function URL origin for API (fallback/backward compatibility)
  dynamic "origin" {
    for_each = var.api_gateway_domain == "" && var.lambda_function_url != "" ? [1] : []
    content {
      domain_name = replace(replace(var.lambda_function_url, "https://", ""), "/", "")
      origin_id   = "lambda-function-url"

      custom_origin_config {
        http_port              = 443
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  # S3 origin for frontend (if provided)
  dynamic "origin" {
    for_each = var.s3_bucket_domain != "" ? [1] : []
    content {
      domain_name = var.s3_bucket_domain
      origin_id   = "s3-frontend"

      s3_origin_config {
        origin_access_identity = var.s3_origin_access_identity
      }
    }
  }

  # Cache behavior for API routes - route to API Gateway (or Lambda Function URL as fallback)
  # IMPORTANT: ordered_cache_behavior blocks are evaluated BEFORE default_cache_behavior
  # This MUST be defined before default_cache_behavior to ensure /api/* paths are matched first
  # Only create this when API Gateway is used - Lambda Function URL-only distributions use default_cache_behavior
  # Using AWS-managed policies (AWS Best Practice) instead of legacy forwarded_values
  # CloudFront Function rewrites /api/* to /{environment}/api/* before forwarding to API Gateway (only for regional endpoints)
  dynamic "ordered_cache_behavior" {
    for_each = var.api_gateway_domain != "" ? [1] : []
    content {
      path_pattern             = "/api/*"
      allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
      cached_methods           = ["GET", "HEAD", "OPTIONS"]
      target_origin_id         = "api-gateway"
      compress                 = false # Don't compress API responses
      viewer_protocol_policy   = "redirect-to-https"
      cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
      realtime_log_config_arn  = var.enable_cloudwatch_logging ? aws_cloudfront_realtime_log_config.cloudfront_realtime_logs[0].arn : null
      
      # Only use path rewriting function when NOT using custom domain
      dynamic "function_association" {
        for_each = !var.use_api_gateway_custom_domain ? [1] : []
        content {
          event_type   = "viewer-request"
          function_arn = aws_cloudfront_function.api_path_rewrite[0].arn
        }
      }
      # Ensure query strings and headers are forwarded for authentication
      # Managed-AllViewer policy already forwards all viewer headers, query strings, and cookies
    }
  }

  # Cache behavior for swagger.json - also route to API Gateway
  dynamic "ordered_cache_behavior" {
    for_each = var.api_gateway_domain != "" ? [1] : []
    content {
      path_pattern             = "/swagger.json"
      allowed_methods          = ["GET", "HEAD", "OPTIONS"]
      cached_methods           = ["GET", "HEAD"]
      target_origin_id         = "api-gateway"
      compress                 = false
      viewer_protocol_policy   = "redirect-to-https"
      cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
      realtime_log_config_arn  = var.enable_cloudwatch_logging ? aws_cloudfront_realtime_log_config.cloudfront_realtime_logs[0].arn : null
      
      # Only use path rewriting function when NOT using custom domain
      dynamic "function_association" {
        for_each = !var.use_api_gateway_custom_domain ? [1] : []
        content {
          event_type   = "viewer-request"
          function_arn = aws_cloudfront_function.api_path_rewrite[0].arn
        }
      }
    }
  }

  # Lifecycle: Create before destroy to minimize downtime during updates
  lifecycle {
    create_before_destroy = true
  }

  # Default cache behavior - route to S3 (frontend) if available, otherwise API Gateway/Lambda
  # This is evaluated AFTER all ordered_cache_behavior blocks
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = var.s3_bucket_domain != "" ? "s3-frontend" : (var.api_gateway_domain != "" ? "api-gateway" : "lambda-function-url")
    compress               = true
    viewer_protocol_policy = "redirect-to-https"
    realtime_log_config_arn = var.enable_cloudwatch_logging ? aws_cloudfront_realtime_log_config.cloudfront_realtime_logs[0].arn : null

    forwarded_values {
      query_string = var.s3_bucket_domain != "" ? false : true
      headers      = []
      cookies {
        forward = var.s3_bucket_domain != "" ? "none" : "all"
      }
    }

    min_ttl     = var.s3_bucket_domain != "" ? 0 : 0
    default_ttl = var.s3_bucket_domain != "" ? 3600 : 0 # Cache static assets
    max_ttl     = var.s3_bucket_domain != "" ? 86400 : 0
  }

  # Custom error responses for SPA routing
  # Convert 404 to index.html for SPA routing (non-API paths)
  # This handles frontend routing where all paths should serve index.html
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  # Convert 403 to 404, then 404 handler will serve index.html for frontend SPA routing
  # This handles missing static assets (like vite.svg) that S3 returns as 403
  # Note: 403 errors from API endpoints will still be returned as 403 since they match /api/* pattern first
  custom_error_response {
    error_code         = 403
    response_code      = 404
    response_page_path = "/index.html"
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
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }

  # CloudFront will only be created when certificate validation is enabled
  # The validation resource will complete immediately if certificate is already validated
  depends_on = [aws_acm_certificate_validation.cert]
}

# Route53 record for ACM certificate validation
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.domain.zone_id
}

# Route53 CNAME record pointing to CloudFront distribution
resource "aws_route53_record" "cloudfront_alias" {
  for_each = var.wait_for_certificate_validation ? { create = true } : {}

  zone_id = data.aws_route53_zone.domain.zone_id
  name    = var.domain_name
  type    = "CNAME"
  ttl     = 300
  records = [aws_cloudfront_distribution.distribution[each.key].domain_name]

  depends_on = [aws_cloudfront_distribution.distribution]
}
