# Locals for normalized naming
locals {
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

# DynamoDB table for instance assignments
resource "aws_dynamodb_table" "instance_assignments" {
  name         = "dynamodb-instance-assignments-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  billing_mode = "PAY_PER_REQUEST"

  key_schema {
    attribute_name = "instance_id"
    key_type       = "HASH"
  }

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
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Parameter Store parameters for instance timeouts
resource "aws_ssm_parameter" "instance_stop_timeout" {
  name        = "/classroom/${var.workshop_name}/${var.environment}/instance_stop_timeout_minutes"
  description = "Timeout in minutes before stopping unassigned running instances"
  type        = "String"
  value       = tostring(var.instance_stop_timeout_minutes)
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "instance_terminate_timeout" {
  name        = "/classroom/${var.workshop_name}/${var.environment}/instance_terminate_timeout_minutes"
  description = "Timeout in minutes before terminating stopped instances"
  type        = "String"
  value       = tostring(var.instance_terminate_timeout_minutes)
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "instance_hard_terminate_timeout" {
  name        = "/classroom/${var.workshop_name}/${var.environment}/instance_hard_terminate_timeout_minutes"
  description = "Timeout in minutes before hard terminating any instance"
  type        = "String"
  value       = tostring(var.instance_hard_terminate_timeout_minutes)
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Null resource to ensure any existing secret is deleted before creation (for one-shot deployment)
# This handles the case where a secret exists outside Terraform state
resource "null_resource" "cleanup_existing_secret" {
  count = var.create_instance_manager_password_secret ? 1 : 0

  triggers = {
    secret_name = "classroom/${var.workshop_name}/${var.environment}/instance-manager/password"
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Try to delete existing secret if it exists (ignore errors if it doesn't)
      aws secretsmanager describe-secret --secret-id "classroom/${var.workshop_name}/${var.environment}/instance-manager/password" >/dev/null 2>&1 && \
      aws secretsmanager delete-secret --secret-id "classroom/${var.workshop_name}/${var.environment}/instance-manager/password" --force-delete-without-recovery || \
      echo "Secret does not exist, proceeding with creation"
    EOT
  }
}

# Secrets Manager secret for instance manager password (only created if create_instance_manager_password_secret is true)
resource "aws_secretsmanager_secret" "instance_manager_password" {
  count = var.create_instance_manager_password_secret ? 1 : 0

  depends_on = [null_resource.cleanup_existing_secret]

  name        = "classroom/${var.workshop_name}/${var.environment}/instance-manager/password"
  description = "Password for EC2 Instance Manager authentication"

  # Allow immediate deletion for clean redeployment
  recovery_window_in_days = 0

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

# Secret value (initial password - should be changed after first deployment)
resource "aws_secretsmanager_secret_version" "instance_manager_password" {
  count = var.create_instance_manager_password_secret ? 1 : 0

  secret_id     = aws_secretsmanager_secret.instance_manager_password[0].id
  secret_string = var.instance_manager_password != "" ? var.instance_manager_password : random_password.instance_manager_password[0].result
}

# Generate random password if not provided
resource "random_password" "instance_manager_password" {
  count = var.create_instance_manager_password_secret ? 1 : 0

  length           = 32
  special          = true
  override_special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
}

# DynamoDB table for tutorial sessions
resource "aws_dynamodb_table" "tutorial_sessions" {
  name         = "dynamodb-tutorial-sessions-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  billing_mode = "PAY_PER_REQUEST"

  key_schema {
    attribute_name = "session_id"
    key_type       = "HASH"
  }

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "workshop_name"
    type = "S"
  }

  global_secondary_index {
    name            = "workshop_name-index"
    hash_key        = "workshop_name"
    projection_type = "ALL"
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

