locals {
  lambda_function_name = "lambda-${var.classroom_name}-${var.environment}"
  s3_bucket_name       = "s3-${var.classroom_name}-${var.environment}"
}

module "iam" {
  source = "./iam"

  environment = var.environment
  owner       = var.owner
  region      = var.region
}

# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_role" {
  name = "classroom-lambda-execution-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_iam_policy" {
  name = "LambdaIAMManagementPolicy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:CreateUser",
          "iam:DeleteUser",
          "iam:GetUser",
          "iam:CreateAccessKey",
          "iam:DeleteAccessKey",
          "iam:ListUsers",
          "iam:ListAccessKeys",
          "iam:PutUserPolicy",
          "iam:AttachUserPolicy",
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "iam:*",
          "tag:*",
          "resource-groups:*",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "ec2:*",
          "ec2:DescribeImages",
          "ec2:DescribeInstances",
          "ec2:RunInstances",
          "ec2:StopInstances",
          "ec2:StartInstances",
          "ec2:TerminateInstances",
          "ec2:CreateTags",
          "ec2:DescribeTags",
          "secretsmanager:GetSecretValue"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/*"
      }
    ]
  })
}

# Add AWS Managed Policy for Lambda Basic Execution
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}



# Lambda Function
resource "aws_lambda_function" "user_management" {
  filename         = "../../functions/packages/testus_patronus_user_management.zip"
  function_name    = local.lambda_function_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "testus_patronus_user_management.lambda_handler"
  runtime          = "python3.9"
  timeout          = 60
  memory_size      = 256
  package_type     = "Zip"
  source_code_hash = filebase64sha256("../../functions/packages/testus_patronus_user_management.zip")

  environment {
    variables = {
      ENVIRONMENT        = var.environment
      STATUS_LAMBDA_URL  = aws_lambda_function_url.status_lambda_url.function_url
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy.lambda_iam_policy,
    aws_iam_role.lambda_role,
    aws_lambda_function.status_lambda
  ]
}

# Lambda Function URL
resource "aws_lambda_function_url" "create_user_url" {
  function_name      = aws_lambda_function.user_management.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}


# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for latest Amazon Linux 2 AMI
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# EC2 Pool Instances
resource "aws_instance" "classroom_pool" {
  count                  = var.ec2_pool_size
  #ami                    = var.ec2_ami_id
  ami                    = "ami-024f025478479ab03"
  instance_type          = var.ec2_instance_type
  vpc_security_group_ids = ["sg-09827f49936d1d7e5"]
  subnet_id              = var.ec2_subnet_id
  
  root_block_device {
    volume_size = 40
    volume_type = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_tokens = "required"
    http_endpoint = "enabled"
  }

  tags = {
    Name        = "classroom-pool-${count.index}"
    Status      = "available"
    Project     = "classroom"
    Environment = var.environment
    Owner       = var.owner
    Type        = "pool"
  }
  #user_data = file("${path.module}/user_data.sh")

  lifecycle {
    create_before_destroy = true
  }
}

# Stop instances after creation
resource "null_resource" "stop_instances" {
  count = var.ec2_pool_size

  triggers = {
    instance_id = aws_instance.classroom_pool[count.index].id
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws ec2 stop-instances --instance-ids ${aws_instance.classroom_pool[count.index].id} --region ${var.region}
    EOT
  }

  depends_on = [aws_instance.classroom_pool]
}

# Output the instance IDs for reference
output "pool_instance_ids" {
  description = "IDs of the EC2 instances in the pool"
  value       = aws_instance.classroom_pool[*].id
}

# Output the instance private IPs for reference
output "pool_instance_private_ips" {
  description = "Private IPs of the EC2 instances in the pool"
  value       = aws_instance.classroom_pool[*].private_ip
}

resource "aws_lambda_function" "status_lambda" {
  filename         = "../../functions/packages/testus_patronus_status.zip"
  function_name    = "status-lambda-${var.classroom_name}-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  handler          = "testus_patronus_status.lambda_handler"
  runtime          = "python3.9"
  timeout          = 30
  memory_size      = 128
  package_type     = "Zip"
  source_code_hash = filebase64sha256("../../functions/packages/testus_patronus_status.zip")

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy.lambda_iam_policy,
    aws_iam_role.lambda_role
  ]
}

resource "aws_lambda_function_url" "status_lambda_url" {
  function_name      = aws_lambda_function.status_lambda.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}

output "status_lambda_url" {
  description = "The URL of the status Lambda function"
  value       = aws_lambda_function_url.status_lambda_url.function_url
}

resource "aws_lambda_function" "stop_old_instances" {
  filename         = "../../functions/packages/testus_patronus_stop_old_instances.zip"
  function_name    = "stop-old-instances-${var.classroom_name}-${var.environment}"
  role             = aws_iam_role.lambda_role.arn
  handler          = "testus_patronus_stop_old_instances.lambda_handler"
  runtime          = "python3.9"
  timeout          = 60
  memory_size      = 128
  package_type     = "Zip"
  source_code_hash = filebase64sha256("../../functions/packages/testus_patronus_stop_old_instances.zip")

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy.lambda_iam_policy,
    aws_iam_role.lambda_role
  ]
}

resource "aws_cloudwatch_event_rule" "stop_old_instances_schedule" {
  name                = "stop-old-instances-schedule-${var.environment}"
  schedule_expression = "rate(10 minutes)" # or use cron() for more control
  description         = "Stop EC2 instances running for more than 3 hours"
}

resource "aws_cloudwatch_event_target" "stop_old_instances_target" {
  rule      = aws_cloudwatch_event_rule.stop_old_instances_schedule.name
  target_id = "stop-old-instances-lambda"
  arn       = aws_lambda_function.stop_old_instances.arn
}

resource "aws_lambda_permission" "allow_eventbridge_stop_old_instances" {
  statement_id  = "AllowExecutionFromEventBridgeStopOldInstances"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stop_old_instances.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stop_old_instances_schedule.arn
}

# 1. Create the API Gateway HTTP API
resource "aws_apigatewayv2_api" "testus_patronus_api" {
  name          = "testus-patronus-api"
  protocol_type = "HTTP"
}

# 2. Lambda Integration
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.testus_patronus_api.id
  integration_type        = "AWS_PROXY"
  integration_uri         = aws_lambda_function.user_management.invoke_arn
  integration_method      = "POST"
  payload_format_version  = "2.0"
}

# 3. Route for /testus-patronus/{proxy+}
resource "aws_apigatewayv2_route" "testus_patronus_route" {
  api_id    = aws_apigatewayv2_api.testus_patronus_api.id
  route_key = "ANY /testus-patronus/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# 4. Default Stage
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.testus_patronus_api.id
  name        = "$default"
  auto_deploy = true
}

# 5. Lambda Permission for API Gateway
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.user_management.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.testus_patronus_api.execution_arn}/*/*"
}

# 6. Custom Domain for API Gateway
resource "aws_apigatewayv2_domain_name" "custom" {
  domain_name = "infra.bassagan.com"
  domain_name_configuration {
    certificate_arn = aws_acm_certificate.infra_bassagan_com.arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
}

# 7. API Mapping for /testus-patronus
resource "aws_apigatewayv2_api_mapping" "custom" {
  api_id      = aws_apigatewayv2_api.testus_patronus_api.id
  domain_name = aws_apigatewayv2_domain_name.custom.id
  stage       = aws_apigatewayv2_stage.default.id
  api_mapping_key = "testus-patronus"
}

# ACM certificate (must be validated in us-east-1 for API Gateway custom domains)
resource "aws_acm_certificate" "infra_bassagan_com" {
  domain_name       = "infra.bassagan.com"
  validation_method = "DNS"
  # ... validation records ...
}

output "apigateway_custom_domain_target" {
  description = "API Gateway custom domain target domain name (use this as CNAME target in your DNS provider)"
  value       = aws_apigatewayv2_domain_name.custom.domain_name_configuration[0].target_domain_name
}

output "apigateway_custom_domain_hosted_zone_id" {
  description = "API Gateway custom domain hosted zone ID (for Route 53 alias records)"
  value       = aws_apigatewayv2_domain_name.custom.domain_name_configuration[0].hosted_zone_id
}
