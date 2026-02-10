# Parameterized workshop module
# This module creates all resources for a specific workshop

data "aws_caller_identity" "current" {}

# Resource Group for this workshop
resource "aws_resourcegroups_group" "workshop" {
  name = "workshop-${var.workshop_name}-${var.environment}"
  description = "Workshop resources for ${var.workshop_name} ${var.environment}"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters = [
        {
          Key    = "WorkshopID"
          Values = [var.workshop_name]
        }
      ]
    })
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Storage Module - DynamoDB, SSM Parameters, and Secrets Manager (per-workshop)
module "storage" {
  source = "../storage"

  environment                        = var.environment
  owner                             = var.owner
  workshop_name                      = var.workshop_name
  instance_stop_timeout_minutes     = var.instance_stop_timeout_minutes
  instance_terminate_timeout_minutes = var.instance_terminate_timeout_minutes
  instance_hard_terminate_timeout_minutes = var.hard_terminate_timeout_minutes
  instance_manager_password         = var.instance_manager_password
  create_instance_manager_password_secret = false  # Workshops use the common/shared secret
}

# IAM Module for User Restrictions
module "iam" {
  source = "../iam"

  environment = var.environment
  owner       = var.owner
  region      = var.region
  workshop_name = var.workshop_name
}

# IAM Lambda Module - Lambda Execution Role
module "iam_lambda" {
  source = "../iam-lambda"

  environment              = var.environment
  owner                    = var.owner
  workshop_name            = var.workshop_name
  account_id               = data.aws_caller_identity.current.account_id
  region                   = var.region
  secrets_manager_secret_arn = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:azure/llm/configs*"
  instance_manager_password_secret_arn = var.common_instance_manager_password_secret_arn
  instance_manager_password_secret_name = var.common_instance_manager_password_secret_name
}

# Lambda Module - All Lambda Functions
module "lambda" {
  source = "../lambda"

  environment              = var.environment
  owner                    = var.owner
  workshop_name            = var.workshop_name
  classroom_name           = var.classroom_name
  region                   = var.region
  lambda_role_arn          = module.iam_lambda.lambda_role_arn
  status_lambda_url        = ""  # Module will use its own status URL internally
  subnet_id                = var.common_subnet_id
  security_group_ids       = var.common_security_group_ids
  iam_instance_profile_name = var.common_ec2_iam_instance_profile_name
  instance_type            = var.ec2_instance_type
  admin_cleanup_interval_days = var.admin_cleanup_interval_days
  admin_cleanup_schedule   = var.admin_cleanup_schedule
  functions_path           = "../../../../functions/packages"
  instance_manager_password_secret_name = var.common_instance_manager_password_secret_name
  skip_iam_user_creation   = var.skip_iam_user_creation

  enable_instance_manager   = false
  enable_stop_old_instances = false
  enable_admin_cleanup      = false
  
  # Lambda scaling and performance configuration
  user_management_memory_size              = var.user_management_memory_size
  user_management_timeout                  = var.user_management_timeout
  user_management_provisioned_concurrency  = var.user_management_provisioned_concurrency
  user_management_reserved_concurrency     = var.user_management_reserved_concurrency
  instance_manager_memory_size            = var.instance_manager_memory_size
  instance_manager_timeout                = var.instance_manager_timeout
}

# Security Group Rules - Optional additional ports (e.g., Jenkins, MailHog)
# Only create if security_group_rules are provided
resource "aws_security_group_rule" "additional_ingress" {
  for_each = var.security_group_rules

  type              = "ingress"
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  protocol          = each.value.protocol
  cidr_blocks       = each.value.cidr_blocks
  security_group_id = var.common_security_group_ids[0]
  description       = each.value.description
}

# CloudFront Module - Custom Domain and CDN for User Management
module "cloudfront_user_management" {
  source = "../cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
  workshop_name     = var.workshop_name
  domain_name      = var.user_management_domain
  lambda_function_url = module.lambda.user_management_url
  wait_for_certificate_validation = var.wait_for_certificate_validation
}

# CloudFront Module - Custom Domain and CDN for Dify Jira API
module "cloudfront_dify_jira" {
  source = "../cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
  workshop_name     = var.workshop_name
  domain_name      = var.dify_jira_domain
  lambda_function_url = module.lambda.dify_jira_api_url
  wait_for_certificate_validation = var.wait_for_certificate_validation
}
