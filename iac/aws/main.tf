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
          "ec2:*"
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

# Student Policy
resource "aws_iam_policy" "student_policy" {
  name = "student-policy-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.lambda_code.arn,
          "${aws_s3_bucket.lambda_code.arn}/*"
        ]
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Lambda Function
resource "aws_lambda_function" "user_management" {
  filename         = "../../functions/packages/lambda_function.zip"
  function_name    = local.lambda_function_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  timeout          = 60
  memory_size      = 256
  package_type     = "Zip"
  source_code_hash = filebase64sha256("../../functions/packages/lambda_function.zip")

  environment {
    variables = {
      ENVIRONMENT        = var.environment
      STUDENT_POLICY_ARN = aws_iam_policy.student_policy.arn
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

# S3 Bucket for Lambda code
resource "aws_s3_bucket" "lambda_code" {
  bucket = local.s3_bucket_name

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
