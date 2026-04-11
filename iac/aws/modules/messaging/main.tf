# Shared messaging module — SQS queue for student progress events.
# Reusable across all tutorials/workshops. Each workshop gets its own
# queue (isolated message flow, independent cost tracking).
#
# Resources:
#   - SQS main queue  (student-progress-<workshop>-<env>-<region>)
#   - SQS dead-letter queue
#   - SQS queue policy (allow EC2 role to SendMessage)
#   - SSM Parameter      (queue URL discoverable by EC2 user-data)
#   - IAM policy         (producer policy reusable for ec2 / future publishers)

# Shared messaging module — SQS queue for student progress events.
# Reusable across all tutorials/workshops. Each workshop gets its own
# queue (isolated message flow, independent cost tracking).
#
# Resources:
#   - SQS main queue  (student-progress-<workshop>-<env>-<region>)
#   - SQS dead-letter queue
#   - SQS queue policy (allow EC2 role to SendMessage)
#   - SSM Parameter      (queue URL discoverable by EC2 user-data)
#   - IAM policy         (producer policy reusable for ec2 / future publishers)
#   - DynamoDB table     (leaderboard single-table)
#   - Lambda function    (SQS consumer, updates leaderboard)

# ── Data sources ──────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

locals {
  region_code     = replace(var.region, "-", "")
  name_suffix     = "${var.workshop_name}-${var.environment}-${local.region_code}"
  queue_name      = "sqs-student-progress-${local.name_suffix}"
  dlq_name        = "sqs-student-progress-dlq-${local.name_suffix}"
  ssm_param_name  = "/classroom/${var.workshop_name}/${var.environment}/messaging/student_progress_queue_url"
  iam_policy_name = "sqs-producer-policy-${local.name_suffix}"
  leaderboard_lambda_zip_path = "${path.root}/../../functions/packages/leaderboard_lambda.zip"
  leaderboard_api_zip_path    = "${path.root}/../../functions/packages/leaderboard_api.zip"
  use_local_leaderboard_zip   = fileexists(local.leaderboard_lambda_zip_path)
  use_local_leaderboard_api_zip = fileexists(local.leaderboard_api_zip_path)
}

# ── Dead-letter queue ─────────────────────────────────────────────────────────

resource "aws_sqs_queue" "student_progress_dlq" {
  name = local.dlq_name

  # Keep undeliverable messages for 3 days for debugging
  message_retention_seconds = 259200

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Component   = "messaging"
    Company     = "TestingFantasy"
  }
}

# ── Main queue ────────────────────────────────────────────────────────────────

resource "aws_sqs_queue" "student_progress" {
  name = local.queue_name

  # Progress events are lightweight and short-lived; keep 1 day
  message_retention_seconds  = 86400
  visibility_timeout_seconds = 60
  delay_seconds              = 0

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.student_progress_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Component   = "messaging"
    Company     = "TestingFantasy"
  }
}

# ── Queue resource policy (allow EC2 IAM role to send messages) ───────────────

resource "aws_sqs_queue_policy" "student_progress" {
  queue_url = aws_sqs_queue.student_progress.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEc2ProducerSendMessage"
        Effect = "Allow"
        Principal = {
          AWS = var.ec2_iam_role_arn
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.student_progress.arn
      },
      # Allow Lambda consumer to receive/delete messages
      {
        Sid    = "AllowLambdaConsumer"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.student_progress.arn
      }
    ]
  })
}

# ── IAM policy (attached to EC2 role by compute module) ──────────────────────

resource "aws_iam_policy" "sqs_producer" {
  name        = local.iam_policy_name
  description = "Allow student EC2 instances to publish progress events to SQS"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.student_progress.arn
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

# ── SSM Parameter — queue URL for EC2 user-data discovery ──────────────────

resource "aws_ssm_parameter" "student_progress_queue_url" {
  name        = local.ssm_param_name
  description = "SQS queue URL for student progress events (workshop: ${var.workshop_name}, env: ${var.environment})"
  type        = "String"
  value       = aws_sqs_queue.student_progress.url
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Component   = "messaging"
    Company     = "TestingFantasy"
  }
}

# ── DynamoDB leaderboard table ────────────────────────────────────────────────
# Single-table design: STUDENT#<id> records for aggregates,
# COMPLETION#<student>#<exercise> records for idempotent tracking.

resource "aws_dynamodb_table" "leaderboard" {
  name         = "dynamodb-leaderboard-${local.name_suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Component   = "messaging"
    Company     = "TestingFantasy"
  }
}

# ── Lambda IAM role for the consumer ─────────────────────────────────────────

resource "aws_iam_role" "leaderboard_lambda" {
  name = "iam-lambda-leaderboard-${local.name_suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

resource "aws_iam_role_policy" "leaderboard_lambda" {
  name = "leaderboard-lambda-policy-${local.name_suffix}"
  role = aws_iam_role.leaderboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.student_progress.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.leaderboard.arn,
          "${aws_dynamodb_table.leaderboard.arn}/index/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.leaderboard_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ── Lambda function ───────────────────────────────────────────────────────────

resource "aws_lambda_function" "leaderboard_consumer" {
  function_name = "lambda-leaderboard-consumer-${local.name_suffix}"
  role          = aws_iam_role.leaderboard_lambda.arn

  # Prefer local packaged artifact (same pattern as other classroom Lambdas).
  # Fall back to S3 artifact when local zip is unavailable.
  filename         = local.use_local_leaderboard_zip ? local.leaderboard_lambda_zip_path : null
  source_code_hash = local.use_local_leaderboard_zip ? filebase64sha256(local.leaderboard_lambda_zip_path) : null
  s3_bucket        = local.use_local_leaderboard_zip ? null : var.lambda_artifact_bucket
  s3_key           = local.use_local_leaderboard_zip ? null : var.lambda_artifact_key

  handler = "leaderboard_lambda.handler"
  runtime = "python3.12"
  timeout = 60

  environment {
    variables = {
      LEADERBOARD_TABLE = aws_dynamodb_table.leaderboard.name
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Component   = "messaging"
    Company     = "TestingFantasy"
  }

  lifecycle {
    precondition {
      condition     = local.use_local_leaderboard_zip || length(trimspace(var.lambda_artifact_bucket)) >= 3
      error_message = "Missing leaderboard Lambda artifact. Either package functions/packages/leaderboard_lambda.zip locally or set lambda_artifact_bucket with a valid S3 bucket name."
    }
  }
}

resource "aws_lambda_function" "leaderboard_api" {
  function_name = "lambda-leaderboard-api-${local.name_suffix}"
  role          = aws_iam_role.leaderboard_lambda.arn

  filename         = local.leaderboard_api_zip_path
  source_code_hash = filebase64sha256(local.leaderboard_api_zip_path)
  handler          = "leaderboard_api.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30

  environment {
    variables = {
      LEADERBOARD_TABLE = aws_dynamodb_table.leaderboard.name
      WORKSHOP_NAME     = var.workshop_name
      ENVIRONMENT       = var.environment
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Component   = "messaging"
    Company     = "TestingFantasy"
  }

  lifecycle {
    precondition {
      condition     = local.use_local_leaderboard_api_zip
      error_message = "Missing leaderboard API Lambda artifact. Package functions/packages/leaderboard_api.zip locally before deploying."
    }
  }
}

# ── SQS → Lambda event source mapping ────────────────────────────────────────

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn                   = aws_sqs_queue.student_progress.arn
  function_name                      = aws_lambda_function.leaderboard_consumer.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5

  # Return individual message failures so Lambda only retries failed records
  function_response_types = ["ReportBatchItemFailures"]
}


