# Shared-Core Provisioning Module
#
# Async student lifecycle management via SQS + Lambda.
# This decouples the instance-manager API from the slow Jenkins/Gitea
# provisioning operations. Flow:
#
#   instance-manager  ──SQS message──►  shared-core-provisioner Lambda
#         (returns request_id)                  │
#                                               ▼
#                                      SSM Run Command on shared-core EC2
#                                               │
#                                               ▼
#                               DynamoDB status table (trackable by request_id)
#
# Resources created:
#   - SQS queue  + DLQ
#   - DynamoDB status table
#   - IAM role + policy for provisioner Lambda
#   - Lambda function (SQS-triggered)
#   - SQS event source mapping
#   - SSM Parameter (queue URL for discovery)

data "aws_caller_identity" "current" {}

locals {
  region_code   = replace(var.region, "-", "")
  name_suffix   = "${var.environment}-${local.region_code}"
  queue_name    = "sqs-shared-core-provisioning-${local.name_suffix}"
  dlq_name      = "sqs-shared-core-provisioning-dlq-${local.name_suffix}"
  table_name    = "dynamodb-shared-core-provisioning-status-${local.name_suffix}"
  function_name = "lambda-shared-core-provisioner-${local.name_suffix}"
  # SSM parameter so instance-manager can discover queue URL at runtime
  ssm_queue_url_param = "/classroom/shared-core/${var.environment}/provisioning-queue-url"
  lambda_zip_path     = "${path.root}/../../functions/packages/shared_core_provisioner.zip"
}

# ── Dead-letter queue ─────────────────────────────────────────────────────────

resource "aws_sqs_queue" "provisioning_dlq" {
  name = local.dlq_name

  # Retain undeliverable messages 3 days so we can investigate failures
  message_retention_seconds = 259200

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "shared-core-provisioning"
    Company     = "TestingFantasy"
  }
}

# ── Main provisioning queue ───────────────────────────────────────────────────

resource "aws_sqs_queue" "provisioning" {
  name = local.queue_name

  # Provisioning tasks can take up to 90 s; hide message while being processed
  visibility_timeout_seconds = 200
  message_retention_seconds  = 3600 # 1 hour — tasks are ephemeral
  delay_seconds              = 0

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.provisioning_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "shared-core-provisioning"
    Company     = "TestingFantasy"
  }
}

# ── SQS queue policy — allow instance-manager Lambda to send ─────────────────

resource "aws_sqs_queue_policy" "provisioning" {
  queue_url = aws_sqs_queue.provisioning.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowInstanceManagerSend"
        Effect = "Allow"
        Principal = {
          AWS = var.instance_manager_lambda_role_arn
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.provisioning.arn
      },
      {
        Sid    = "AllowProvisionerConsume"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.provisioner.arn
        }
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.provisioning.arn
      }
    ]
  })
}

# ── DynamoDB status table ─────────────────────────────────────────────────────
# PK: request_id (UUID). Attributes: action, student_id, status, timestamps.

resource "aws_dynamodb_table" "provisioning_status" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  # TTL: auto-expire records after 7 days
  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "shared-core-provisioning"
    Company     = "TestingFantasy"
  }
}

# ── IAM role for provisioner Lambda ──────────────────────────────────────────

resource "aws_iam_role" "provisioner" {
  name = "iam-shared-core-provisioner-${local.name_suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "shared-core-provisioning"
    Company     = "TestingFantasy"
  }
}

resource "aws_iam_role_policy_attachment" "provisioner_basic" {
  role       = aws_iam_role.provisioner.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "provisioner_policy" {
  name = "iam-shared-core-provisioner-policy-${local.name_suffix}"
  role = aws_iam_role.provisioner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # SQS — consume provisioning requests
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          aws_sqs_queue.provisioning.arn,
          aws_sqs_queue.provisioning_dlq.arn
        ]
      },
      # DynamoDB — write status updates
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.provisioning_status.arn
      },
      # SSM — send commands to shared-core EC2 + read parameters
      {
        Effect = "Allow"
        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:ListCommandInvocations"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/classroom/*"
      },
      # Secrets Manager — read shared-core admin credentials
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:/classroom/shared-core/*"
      },
      # CloudWatch Logs — structured logging
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.function_name}:*"
      }
    ]
  })
}

# ── Lambda function — shared-core provisioner ─────────────────────────────────

resource "aws_lambda_function" "provisioner" {
  filename      = local.lambda_zip_path
  function_name = local.function_name
  role          = aws_iam_role.provisioner.arn
  handler       = "shared_core_provisioner.lambda_handler"
  runtime       = "python3.9"
  timeout       = 180 # 3 min — SSM polling can take up to 90 s + retry
  memory_size   = 256
  package_type  = "Zip"

  source_code_hash = fileexists(local.lambda_zip_path) ? filebase64sha256(local.lambda_zip_path) : null

  environment {
    variables = {
      ENVIRONMENT               = var.environment
      CLASSROOM_REGION          = var.region
      PROVISIONING_STATUS_TABLE = local.table_name
      # Workshop name stored in SSM at /classroom/shared-core/{env}/instance-id
      # The Lambda reads credentials and instance ID from SSM at runtime
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "shared-core-provisioning"
    Company     = "TestingFantasy"
  }
}

# ── SQS → Lambda event source mapping ────────────────────────────────────────

resource "aws_lambda_event_source_mapping" "provisioning_sqs" {
  event_source_arn = aws_sqs_queue.provisioning.arn
  function_name    = aws_lambda_function.provisioner.arn
  batch_size       = 1 # Process one request at a time for clear per-student tracking
  enabled          = true

  depends_on = [aws_iam_role_policy.provisioner_policy]
}

# ── SSM Parameter — queue URL for runtime discovery ───────────────────────────

resource "aws_ssm_parameter" "provisioning_queue_url" {
  name        = local.ssm_queue_url_param
  description = "SQS queue URL for async shared-core student provisioning (env: ${var.environment})"
  type        = "String"
  value       = aws_sqs_queue.provisioning.url
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "shared-core-provisioning"
    Company     = "TestingFantasy"
  }
}

# ── CloudWatch alarm — DLQ depth (signal for stuck/failed provisioning) ───────

resource "aws_cloudwatch_metric_alarm" "provisioning_dlq_depth" {
  alarm_name          = "alarm-shared-core-provisioning-dlq-${local.name_suffix}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Messages in shared-core provisioning DLQ — student provisioning is failing"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.provisioning_dlq.name
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "shared-core-provisioning"
    Company     = "TestingFantasy"
  }
}
