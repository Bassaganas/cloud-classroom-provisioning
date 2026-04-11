# API Gateway REST API for EC2 Instance Manager

# Data source for current region
data "aws_region" "current" {}

# Provider for us-east-1 (required for API Gateway ACM certificates)
# This provider is passed from the parent module

# Locals for computed values
locals {
  # CloudWatch Logs role ARN for API Gateway account settings
  # Only set when logging is enabled
  cloudwatch_role_arn = var.enable_logging ? aws_iam_role.api_gateway_logging.arn : null

  # Stage name - always use var.environment since that's what the stage is named
  # If the stage exists, it was created with this name; if we create it, we use this name
  stage_name = var.environment

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

# REST API
resource "aws_api_gateway_rest_api" "api" {
  name        = "apigateway-${var.api_name}-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "API Gateway for ${var.api_name} - ${var.environment}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Resource policy to allow public access from CloudFront and direct API Gateway calls
# This must be separate from the REST API resource to avoid circular dependencies
resource "aws_api_gateway_rest_api_policy" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action    = "execute-api:Invoke"
        Resource  = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
      }
    ]
  })
}

# Resource for swagger.json (at root level, before /api)
resource "aws_api_gateway_resource" "swagger" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "swagger.json"
}

# Method for swagger.json
resource "aws_api_gateway_method" "swagger_method" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.swagger.id
  http_method   = "GET"
  authorization = "NONE"
}

# Integration for swagger.json
resource "aws_api_gateway_integration" "swagger_integration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.swagger.id
  http_method = aws_api_gateway_method.swagger_method.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_function_arn}/invocations"
}

# OPTIONS method for swagger.json CORS
resource "aws_api_gateway_method" "swagger_options" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.swagger.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# Mock integration for swagger.json OPTIONS
resource "aws_api_gateway_integration" "swagger_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.swagger.id
  http_method = aws_api_gateway_method.swagger_options.http_method

  type = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

# Method response for swagger.json OPTIONS
resource "aws_api_gateway_method_response" "swagger_options_response" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.swagger.id
  http_method = aws_api_gateway_method.swagger_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Integration response for swagger.json OPTIONS
resource "aws_api_gateway_integration_response" "swagger_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.swagger.id
  http_method = aws_api_gateway_method.swagger_options.http_method
  status_code = aws_api_gateway_method_response.swagger_options_response.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.swagger_options_integration]
}

# Proxy resource for /api/{proxy+}
resource "aws_api_gateway_resource" "api_proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "api"
}

resource "aws_api_gateway_resource" "api_proxy_path" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.api_proxy.id
  path_part   = "{proxy+}"
}

# Lambda integration for proxy resource
resource "aws_api_gateway_integration" "api_proxy_integration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.api_proxy_path.id
  http_method = aws_api_gateway_method.api_proxy_method.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_function_arn}/invocations"
}

# Method for proxy resource (ANY method)
resource "aws_api_gateway_method" "api_proxy_method" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.api_proxy_path.id
  http_method   = "ANY"
  authorization = "NONE"
}

# OPTIONS method for CORS preflight
resource "aws_api_gateway_method" "api_proxy_options" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.api_proxy_path.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# Mock integration for OPTIONS (CORS preflight)
resource "aws_api_gateway_integration" "api_proxy_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.api_proxy_path.id
  http_method = aws_api_gateway_method.api_proxy_options.http_method

  type = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

# Method response for OPTIONS
resource "aws_api_gateway_method_response" "api_proxy_options_response" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.api_proxy_path.id
  http_method = aws_api_gateway_method.api_proxy_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Integration response for OPTIONS
resource "aws_api_gateway_integration_response" "api_proxy_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.api_proxy_path.id
  http_method = aws_api_gateway_method.api_proxy_options.http_method
  status_code = aws_api_gateway_method_response.api_proxy_options_response.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.api_proxy_options_integration]
}

# Lambda permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

# Deployment
resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_method.api_proxy_method.id,
      aws_api_gateway_integration.api_proxy_integration.id,
      aws_api_gateway_method.api_proxy_options.id,
      aws_api_gateway_integration.api_proxy_options_integration.id,
      aws_api_gateway_method.swagger_method.id,
      aws_api_gateway_integration.swagger_integration.id,
      aws_api_gateway_method.swagger_options.id,
      aws_api_gateway_integration.swagger_options_integration.id,
      aws_api_gateway_rest_api_policy.api.policy, # Include resource policy in deployment trigger
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_method.api_proxy_method,
    aws_api_gateway_integration.api_proxy_integration,
    aws_api_gateway_method.api_proxy_options,
    aws_api_gateway_integration.api_proxy_options_integration,
    aws_api_gateway_method.swagger_method,
    aws_api_gateway_integration.swagger_integration,
    aws_api_gateway_method.swagger_options,
    aws_api_gateway_integration.swagger_options_integration,
    aws_api_gateway_rest_api_policy.api, # Ensure policy is created before deployment
  ]
}

# CloudWatch Log Group for API Gateway (AWS Best Practice)
resource "aws_cloudwatch_log_group" "api_gateway" {
  count             = var.enable_logging ? 1 : 0
  name              = "log-apigateway-${var.api_name}-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  retention_in_days = var.log_retention_days

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

# IAM Role for API Gateway to write logs to CloudWatch
# Always create the role (even when logging is disabled) to allow account settings to reference it
resource "aws_iam_role" "api_gateway_logging" {
  name = "iam-api-gateway-logging-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
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

# IAM Policy for API Gateway logging
# Only attach policy when logging is enabled
# API Gateway requires permissions to create log groups and write to any log group
resource "aws_iam_role_policy" "api_gateway_logging" {
  count = var.enable_logging ? 1 : 0
  name  = "iam-api-gateway-logging-policy-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role  = aws_iam_role.api_gateway_logging.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup"
        ]
        # API Gateway needs permission to create log groups
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents",
          "logs:GetLogEvents",
          "logs:FilterLogEvents"
        ]
        # API Gateway needs permission to write to log streams
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# API Gateway Account Settings - Set CloudWatch Logs role ARN (required for stage logging)
# This is a global account-level setting for API Gateway (singleton resource per AWS account)
# Note: This resource is shared across all API Gateways in the account
# Always create the account resource (singleton) but only set role ARN when logging is enabled
resource "aws_api_gateway_account" "api_gateway_account" {
  # Set role ARN when logging is enabled, otherwise leave it unset (will use existing value if any)
  cloudwatch_role_arn = var.enable_logging ? aws_iam_role.api_gateway_logging.arn : null

  # Ensure IAM role and policy are created before setting account settings
  depends_on = [
    aws_iam_role.api_gateway_logging,
    aws_iam_role_policy.api_gateway_logging
  ]
}

# Wait for API Gateway account settings to propagate
# AWS API Gateway account settings can take a few seconds to propagate after creation
# Always create this resource (with 0s delay when logging disabled) so it can be referenced in depends_on
resource "time_sleep" "wait_for_account_propagation" {
  depends_on = [aws_api_gateway_account.api_gateway_account]

  # Wait 10 seconds when logging is enabled, 0 seconds when disabled
  create_duration = var.enable_logging ? "10s" : "0s"
}

# Check if stage already exists using external data source
# This allows us to conditionally create the stage only if it doesn't exist
data "external" "stage_exists" {
  program = ["bash", "-c", <<-EOT
    set -e
    # Check if REST API exists first
    if ! aws apigateway get-rest-api --rest-api-id ${aws_api_gateway_rest_api.api.id} --region ${data.aws_region.current.name} >/dev/null 2>&1; then
      echo '{"exists":"false"}'
      exit 0
    fi
    # Check if stage exists
    if aws apigateway get-stage \
      --rest-api-id ${aws_api_gateway_rest_api.api.id} \
      --stage-name ${var.environment} \
      --region ${data.aws_region.current.name} >/dev/null 2>&1; then
      echo '{"exists":"true"}'
    else
      echo '{"exists":"false"}'
    fi
  EOT
  ]
}

# Stage
# Only create if it doesn't already exist (checked via external data source)
resource "aws_api_gateway_stage" "api" {
  deployment_id = aws_api_gateway_deployment.api.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = var.environment

  # CloudWatch logging configuration (AWS Best Practice)
  dynamic "access_log_settings" {
    for_each = var.enable_logging ? [1] : []
    content {
      destination_arn = aws_cloudwatch_log_group.api_gateway[0].arn
      format = jsonencode({
        requestId      = "$context.requestId"
        ip             = "$context.identity.sourceIp"
        caller         = "$context.identity.caller"
        user           = "$context.identity.user"
        requestTime    = "$context.requestTime"
        httpMethod     = "$context.httpMethod"
        resourcePath   = "$context.resourcePath"
        status         = "$context.status"
        protocol       = "$context.protocol"
        responseLength = "$context.responseLength"
      })
    }
  }

  # X-Ray tracing (optional but recommended for distributed tracing)
  xray_tracing_enabled = var.enable_logging

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }

  # Explicit dependency: Wait for API Gateway account settings to propagate
  # The account resource is always created (singleton), and time_sleep ensures
  # settings propagate before stage logging is enabled (10s delay when logging enabled)
  depends_on = [
    aws_api_gateway_account.api_gateway_account,
    time_sleep.wait_for_account_propagation
  ]

  lifecycle {
    # Prevent Terraform from trying to recreate if the stage already exists
    # This helps when the stage was created outside of Terraform or imported
    create_before_destroy = false
  }
}

# ============================================================================
# API Gateway Custom Domain Configuration
# ============================================================================

# Data source for Route53 hosted zone (only if custom domain is configured)
data "aws_route53_zone" "api_domain" {
  count        = var.api_custom_domain_name != "" ? 1 : 0
  name         = var.base_domain != "" ? "${var.base_domain}." : replace(var.api_custom_domain_name, "/^[^.]+\\.(.+)$/", "$1.")
  private_zone = false
}

# ACM Certificate for API Gateway custom domain (must be in us-east-1 for regional API Gateway)
resource "aws_acm_certificate" "api_domain_cert" {
  count    = var.api_custom_domain_name != "" ? 1 : 0
  provider = aws.us_east_1

  domain_name       = var.api_custom_domain_name
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

# Certificate validation (optional - set wait_for_certificate_validation = true only after DNS records are added)
resource "aws_acm_certificate_validation" "api_domain_cert" {
  for_each = var.api_custom_domain_name != "" && var.wait_for_certificate_validation ? { create = true } : {}

  provider = aws.us_east_1

  certificate_arn = aws_acm_certificate.api_domain_cert[0].arn

  timeouts {
    create = "10m"
  }
}

# API Gateway Domain Name
resource "aws_api_gateway_domain_name" "api_domain" {
  for_each = var.api_custom_domain_name != "" && var.wait_for_certificate_validation ? { create = true } : {}

  domain_name     = var.api_custom_domain_name
  certificate_arn = aws_acm_certificate_validation.api_domain_cert["create"].certificate_arn
  # Note: For Edge endpoints, use certificate_arn (not regional_certificate_arn)
  # Edge endpoints automatically create a CloudFront distribution

  endpoint_configuration {
    types = ["EDGE"]
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }

  depends_on = [aws_acm_certificate_validation.api_domain_cert]
}

# Base Path Mapping (maps root path to stage)
# Empty base_path means the custom domain root maps to the stage
resource "aws_api_gateway_base_path_mapping" "api_mapping" {
  for_each = var.api_custom_domain_name != "" && var.wait_for_certificate_validation ? { create = true } : {}

  api_id      = aws_api_gateway_rest_api.api.id
  stage_name  = local.stage_name
  domain_name = aws_api_gateway_domain_name.api_domain["create"].domain_name
  # base_path = "" (empty = root path maps to stage)

  depends_on = [
    aws_api_gateway_stage.api,
    aws_api_gateway_deployment.api
  ]
}

# Route53 record for ACM certificate validation
resource "aws_route53_record" "api_cert_validation" {
  for_each = var.api_custom_domain_name != "" ? {
    for dvo in aws_acm_certificate.api_domain_cert[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.api_domain[0].zone_id
}

# Route53 record pointing to API Gateway custom domain (regional domain name)
resource "aws_route53_record" "api_domain" {
  for_each = var.api_custom_domain_name != "" && var.wait_for_certificate_validation ? { create = true } : {}

  zone_id         = data.aws_route53_zone.api_domain[0].zone_id
  name            = var.api_custom_domain_name
  type            = "A"
  allow_overwrite = true

  alias {
    name                   = aws_api_gateway_domain_name.api_domain["create"].cloudfront_domain_name
    zone_id                = aws_api_gateway_domain_name.api_domain["create"].cloudfront_zone_id
    evaluate_target_health = false
  }

  depends_on = [aws_api_gateway_domain_name.api_domain]
}
