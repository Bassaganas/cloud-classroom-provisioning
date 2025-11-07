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
  value       = tostring(var.instance_stop_timeout_minutes)

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
  value       = tostring(var.instance_terminate_timeout_minutes)

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
  value       = tostring(var.instance_hard_terminate_timeout_minutes)

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Secrets Manager secret for instance manager password
resource "aws_secretsmanager_secret" "instance_manager_password" {
  name        = "classroom/${var.environment}/instance-manager/password"
  description = "Password for EC2 Instance Manager authentication"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Secret value (initial password - should be changed after first deployment)
resource "aws_secretsmanager_secret_version" "instance_manager_password" {
  secret_id = aws_secretsmanager_secret.instance_manager_password.id
  secret_string = var.instance_manager_password != "" ? var.instance_manager_password : random_password.instance_manager_password.result
}

# Generate random password if not provided
resource "random_password" "instance_manager_password" {
  length  = 32
  special = true
  override_special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
}

