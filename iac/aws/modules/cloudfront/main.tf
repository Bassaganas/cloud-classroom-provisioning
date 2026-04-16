# Current AWS region (needed for OAC S3 regional endpoint)
data "aws_region" "current" {}

# Data source for Route53 hosted zone
data "aws_route53_zone" "domain" {
  count        = var.enable_route53_records ? 1 : 0
  name         = var.zone_name != "" ? "${var.zone_name}." : replace(var.domain_name, "/^[^.]+\\.(.+)$/", "$1")
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

  name = "${var.environment}-${var.workshop_name}-realtime-logs"
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
    ignore_changes        = [name]
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

  filename      = "${path.module}/cloudfront_log_processor.zip"
  function_name = "cloudfront-log-processor-${var.environment}-${var.workshop_name}"
  role          = aws_iam_role.lambda_log_processor[0].arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 256

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
    ignore_changes        = [filename, source_code_hash] # Allow code updates without replacement
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

  event_source_arn                   = aws_kinesis_stream.cloudfront_logs[0].arn
  function_name                      = aws_lambda_function.cloudfront_log_processor[0].arn
  starting_position                  = "LATEST"
  batch_size                         = 100
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
# CloudFront Function to rewrite directory-style paths for static S3 sites
# e.g., /getting-started/quick-start  →  /getting-started/quick-start/index.html
# Required because S3 only serves DefaultRootObject at the true root; sub-paths
# using directory-style URLs must explicitly resolve to their index.html.
resource "aws_cloudfront_function" "s3_directory_index" {
  count = var.enable_s3_path_rewrite ? 1 : 0

  name    = "s3-dir-index-${var.environment}-${replace(replace(var.domain_name, ".testingfantasy.com", ""), ".", "-")}"
  runtime = "cloudfront-js-2.0"
  comment = "Rewrite extensionless paths to .html for Docusaurus trailingSlash:false builds"
  code    = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;

      // Root is handled by DefaultRootObject (index.html), nothing to do
      if (uri === '/') {
        return request;
      }

      // Strip trailing slash so /path/ and /path are treated identically
      if (uri.endsWith('/')) {
        uri = uri.slice(0, -1);
      }

      // Check whether the last segment already carries a file extension
      var lastSlash = uri.lastIndexOf('/');
      var lastSegment = uri.substring(lastSlash + 1);
      if (!lastSegment.includes('.')) {
        // No extension → Docusaurus page; append .html (trailingSlash: false)
        uri += '.html';
      }

      request.uri = uri;
      return request;
    }
  EOF
}

# Extract a unique identifier from domain name to avoid conflicts when multiple CloudFront distributions
# use the same workshop_name (e.g., user_management vs dify_jira)
locals {
  # Extract a short unique identifier from domain name
  # e.g., "testus-patronus.testingfantasy.com" -> "testus-patronus"
  #      "dify-jira.testingfantasy.com" -> "dify-jira"
  #      "fellowship-of-the-build.testingfantasy.com" -> "fellowship-of-the-build"
  domain_identifier = replace(replace(var.domain_name, ".testingfantasy.com", ""), ".", "-")
  # Function name using domain identifier for uniqueness
  function_name = "api-path-rewrite-${var.environment}-${local.domain_identifier}"
  # Old function name (for cleanup) - used workshop_name which caused conflicts
  old_function_name = "api-path-rewrite-${var.environment}-${var.workshop_name}"
}

# Null resource to cleanup existing CloudFront Functions (for one-shot deployment)
# Handles both old naming (workshop_name) and new naming (domain_identifier)
resource "null_resource" "cleanup_existing_cloudfront_function" {
  count = !var.use_api_gateway_custom_domain ? 1 : 0

  triggers = {
    function_name = local.function_name
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Try to delete existing CloudFront Function with new name if it exists
      if aws cloudfront describe-function --name "${local.function_name}" >/dev/null 2>&1; then
        echo "Found existing CloudFront Function ${local.function_name}, deleting..."
        ETAG=$(aws cloudfront describe-function --name "${local.function_name}" --query 'ETag' --output text 2>/dev/null)
        if [ ! -z "$ETAG" ] && [ "$ETAG" != "None" ]; then
          aws cloudfront delete-function --name "${local.function_name}" --if-match "$ETAG" 2>/dev/null || \
          echo "Failed to delete function (may be in use)"
        fi
      fi
      
      # Also try to delete old function name (from previous deployments with workshop_name)
      if aws cloudfront describe-function --name "${local.old_function_name}" >/dev/null 2>&1; then
        echo "Found old CloudFront Function ${local.old_function_name}, deleting..."
        ETAG=$(aws cloudfront describe-function --name "${local.old_function_name}" --query 'ETag' --output text 2>/dev/null)
        if [ ! -z "$ETAG" ] && [ "$ETAG" != "None" ]; then
          aws cloudfront delete-function --name "${local.old_function_name}" --if-match "$ETAG" 2>/dev/null || \
          echo "Failed to delete old function (may be in use)"
        fi
      fi
      
      echo "CloudFront Function cleanup complete, proceeding with creation"
    EOT
  }
}

resource "aws_cloudfront_function" "api_path_rewrite" {
  count = !var.use_api_gateway_custom_domain ? 1 : 0

  depends_on = [null_resource.cleanup_existing_cloudfront_function]

  name    = local.function_name
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

# CloudFront Function to rewrite directory-style paths for Docusaurus SSG on S3
# When CloudFront uses S3 REST API (OAI), it does NOT auto-serve index.html for sub-directories.
# e.g. /getting-started/quick-start → S3 key not found (403) unless rewritten to
#      /getting-started/quick-start/index.html which IS the actual Docusaurus build artifact.
resource "aws_cloudfront_function" "s3_path_rewrite" {
  count = var.enable_s3_path_rewrite ? 1 : 0

  name    = "s3-path-rewrite-${var.environment}-${local.domain_identifier}"
  runtime = "cloudfront-js-1.0"
  comment = "Append /index.html to extensionless paths for Docusaurus SSG (S3+OAI)"

  code = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;

      // If the URI ends with '/', serve the index document of that directory.
      if (uri.endsWith('/')) {
        request.uri += 'index.html';
      }
      // If the URI has no file extension, treat it as a directory and append /index.html.
      // This covers Docusaurus routes like /getting-started/quick-start
      else if (!uri.includes('.')) {
        request.uri += '/index.html';
      }

      return request;
    }
  EOF
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

# Null resource to check for and disable existing CloudFront distributions with the same CNAME
# This handles the case where a distribution exists outside Terraform state (for one-shot deployment)
resource "null_resource" "cleanup_existing_cloudfront" {
  for_each = var.wait_for_certificate_validation ? { create = true } : {}

  triggers = {
    domain_name = var.domain_name
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Find existing CloudFront distributions with the same alias
      DIST_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items[?@=='${var.domain_name}']].Id" --output text 2>/dev/null | head -n1)
      
      if [ ! -z "$DIST_ID" ] && [ "$DIST_ID" != "None" ]; then
        echo "Found existing CloudFront distribution $DIST_ID with alias ${var.domain_name}"
        echo "Note: CloudFront distributions must be disabled manually before deletion"
        echo "Please disable distribution $DIST_ID in AWS Console or use:"
        echo "  aws cloudfront get-distribution-config --id $DIST_ID > /tmp/dist-config.json"
        echo "  # Edit /tmp/dist-config.json to set Enabled: false"
        echo "  aws cloudfront update-distribution --id $DIST_ID --if-match <ETag> --distribution-config file:///tmp/dist-config.json"
        echo "Then wait for deployment and delete with:"
        echo "  aws cloudfront delete-distribution --id $DIST_ID --if-match <ETag>"
        exit 1
      else
        echo "No existing CloudFront distribution found with alias ${var.domain_name}, proceeding with creation"
      fi
    EOT
  }
}

# CloudFront Distribution
# Only create if wait_for_certificate_validation is true (certificate must be validated)
# CloudFront requires a validated certificate to work with custom domains
# Using for_each instead of count to avoid Terraform evaluation issues
resource "aws_cloudfront_distribution" "distribution" {
  for_each = var.wait_for_certificate_validation ? { create = true } : {}

  depends_on = [null_resource.cleanup_existing_cloudfront, aws_acm_certificate_validation.cert]

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
  # OAC requires the regional S3 endpoint; OAI works with the global endpoint
  dynamic "origin" {
    for_each = var.s3_bucket_domain != "" || var.s3_origin_bucket != "" ? [1] : []
    content {
      domain_name = var.s3_bucket_domain != "" ? var.s3_bucket_domain : (
        var.s3_origin_access_control_id != "" ?
        "${var.s3_origin_bucket}.s3.${data.aws_region.current.name}.amazonaws.com" :
        "${var.s3_origin_bucket}.s3.amazonaws.com"
      )
      origin_id                = "s3-frontend"
      origin_access_control_id = var.s3_origin_access_control_id != "" ? var.s3_origin_access_control_id : null

      s3_origin_config {
        origin_access_identity = var.s3_origin_access_control_id != "" ? "" : var.s3_origin_access_identity
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
    # Prevent replacement if only tags change
    ignore_changes = [tags, tags_all]
  }

  # Default cache behavior - route to S3 (frontend) if available, otherwise API Gateway/Lambda
  # This is evaluated AFTER all ordered_cache_behavior blocks
  default_cache_behavior {
    allowed_methods         = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods          = ["GET", "HEAD"]
    target_origin_id        = var.s3_bucket_domain != "" || var.s3_origin_bucket != "" ? "s3-frontend" : (var.api_gateway_domain != "" ? "api-gateway" : "lambda-function-url")
    compress                = true
    viewer_protocol_policy  = "redirect-to-https"
    realtime_log_config_arn = var.enable_cloudwatch_logging ? aws_cloudfront_realtime_log_config.cloudfront_realtime_logs[0].arn : null

    forwarded_values {
      query_string = var.s3_bucket_domain != "" || var.s3_origin_bucket != "" ? false : true
      headers      = []
      cookies {
        forward = var.s3_bucket_domain != "" || var.s3_origin_bucket != "" ? "none" : "all"
      }
    }

    min_ttl     = var.s3_bucket_domain != "" || var.s3_origin_bucket != "" ? 0 : 0
    default_ttl = var.s3_bucket_domain != "" || var.s3_origin_bucket != "" ? 3600 : 0 # Cache static assets
    max_ttl     = var.s3_bucket_domain != "" || var.s3_origin_bucket != "" ? 86400 : 0

    # Attach the directory-index rewrite function for S3 static sites
    dynamic "function_association" {
      for_each = var.enable_s3_path_rewrite ? [1] : []
      content {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.s3_directory_index[0].arn
      }
    }
  }

  # Custom error responses for SPA routing
  # Convert 404 to index.html for SPA routing (non-API paths)
  # This handles frontend routing where all paths should serve index.html
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  # Convert 403 (S3 private bucket missing-key) to 200 + index.html for SSG/SPA routing
  # S3 never returns 404 for missing objects on a private bucket — it returns 403.
  # Note: 403 errors from API endpoints will still be returned as 403 since they match /api/* pattern first
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
  # (depends_on is already set at the top of the resource block)
}

# Route53 record for ACM certificate validation
# Use static key (domain name) to avoid for_each issues with unknown domain_validation_options
# The validation options are only known after the certificate is created, so we use a static key
# and access the first validation option by converting the set to a list
resource "aws_route53_record" "cert_validation" {
  # Use static key based on known domain name (known at plan time)
  for_each = var.enable_route53_records && var.domain_name != "" ? toset([var.domain_name]) : toset([])

  allow_overwrite = true
  # Access the first (and only) validation option
  # Convert set to list to access by index - this will be populated after certificate creation
  name    = try(tolist(aws_acm_certificate.cert.domain_validation_options)[0].resource_record_name, "")
  records = [try(tolist(aws_acm_certificate.cert.domain_validation_options)[0].resource_record_value, "")]
  ttl     = 60
  type    = try(tolist(aws_acm_certificate.cert.domain_validation_options)[0].resource_record_type, "CNAME")
  zone_id = data.aws_route53_zone.domain[0].zone_id
}

# Route53 CNAME record pointing to CloudFront distribution
resource "aws_route53_record" "cloudfront_alias" {
  for_each = var.wait_for_certificate_validation && var.enable_route53_records ? { create = true } : {}

  zone_id         = data.aws_route53_zone.domain[0].zone_id
  name            = var.domain_name
  type            = "CNAME"
  ttl             = 300
  allow_overwrite = true
  records         = [aws_cloudfront_distribution.distribution[each.key].domain_name]

  depends_on = [aws_cloudfront_distribution.distribution]
}
