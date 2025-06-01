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

# DynamoDB table for instance assignments
resource "aws_dynamodb_table" "instance_assignments" {
  name         = "instance-assignments-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "instance_id"

  attribute {
    name = "instance_id"
    type = "S"
  }

  attribute {
    name = "student_name"
    type = "S"
  }

  global_secondary_index {
    name            = "student_name-index"
    hash_key        = "student_name"
    projection_type = "ALL"
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Parameter Store parameters for instance timeouts
resource "aws_ssm_parameter" "instance_stop_timeout" {
  name        = "/classroom/${var.environment}/instance_stop_timeout_minutes"
  description = "Timeout in minutes before stopping unassigned running instances"
  type        = "String"
  value       = "60" # 1 hours
  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

resource "aws_ssm_parameter" "instance_terminate_timeout" {
  name        = "/classroom/${var.environment}/instance_terminate_timeout_minutes"
  description = "Timeout in minutes before terminating stopped instances"
  type        = "String"
  value       = "20"
  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

resource "aws_ssm_parameter" "instance_hard_terminate_timeout" {
  name        = "/classroom/${var.environment}/instance_hard_terminate_timeout_minutes"
  description = "Timeout in minutes before hard terminating any instance"
  type        = "String"
  value       = "240" # 4 hours
  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Update Lambda IAM policy to allow SSM Parameter Store access
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
          "ssm:*",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances",
          "ec2:CreateTags",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeTags",
          "ec2:ModifyInstanceAttribute",
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "ssm:GetParameter",
          "ssm:GetParameters"
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
      ENVIRONMENT       = var.environment
      STATUS_LAMBDA_URL = aws_lambda_function_url.status_lambda_url.function_url
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
    aws_lambda_function.status_lambda,
    aws_lambda_function_url.status_lambda_url
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

# IAM Role for EC2 instances
resource "aws_iam_role" "ec2_ssm_role" {
  name = "ec2-ssm-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
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

# Attach SSM policy to EC2 role
resource "aws_iam_role_policy_attachment" "ssm_policy" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Create instance profile
resource "aws_iam_instance_profile" "ec2_ssm_profile" {
  name = "ec2-ssm-profile-${var.environment}"
  role = aws_iam_role.ec2_ssm_role.name
}

# EC2 Pool Instances
resource "aws_instance" "classroom_pool" {
  count                  = var.ec2_pool_size
  ami                    = "ami-024f025478479ab03"
  instance_type          = var.ec2_instance_type
  vpc_security_group_ids = ["sg-09827f49936d1d7e5"]
  subnet_id              = var.ec2_subnet_id
  iam_instance_profile   = aws_iam_instance_profile.ec2_ssm_profile.name

  root_block_device {
    volume_size           = 40
    volume_type           = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  user_data = <<-EOF
              #!/bin/bash
              # Install SSM agent
              yum install -y amazon-ssm-agent
              systemctl enable amazon-ssm-agent
              systemctl start amazon-ssm-agent
              EOF

  tags = {
    Name        = "classroom-pool-${count.index}"
    Status      = "available"
    Project     = "classroom"
    Environment = var.environment
    Owner       = var.owner
    Type        = "pool"
  }

  lifecycle {
    create_before_destroy = true
  }
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
  timeout          = 300
  memory_size      = 256
  package_type     = "Zip"
  source_code_hash = filebase64sha256("../../functions/packages/testus_patronus_stop_old_instances.zip")

  environment {
    variables = {
      ENVIRONMENT      = var.environment
      PARAMETER_PREFIX = "/classroom/${var.environment}"
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

resource "aws_iam_policy" "lambda_secretsmanager_policy" {
  name        = "lambda-secretsmanager-policy"
  description = "Allow Lambda to get Azure LLM configs from Secrets Manager"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:eu-west-3:087559609246:secret:azure/llm/configs*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_secretsmanager_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_secretsmanager_policy.arn
}
