# Provider for us-east-1 (required for CloudFront ACM certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Remote state for shared/common infrastructure (EC2 manager)
data "terraform_remote_state" "common" {
  backend = "s3"
  config = {
    bucket         = var.common_state_bucket
    key            = var.common_state_key
    region         = var.common_state_region
    dynamodb_table = var.common_state_dynamodb_table
  }
}

# Resource Group for this workshop
resource "aws_resourcegroups_group" "workshop" {
  name = "workshop-${var.workshop_name}-${var.environment}"
  description = "Workshop resources for ${var.workshop_name} in ${var.environment}"

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
  source = "../../modules/storage"

  environment                        = var.environment
  owner                             = var.owner
  workshop_name                      = var.workshop_name
  instance_stop_timeout_minutes     = var.instance_stop_timeout_minutes
  instance_terminate_timeout_minutes = var.instance_terminate_timeout_minutes
  instance_hard_terminate_timeout_minutes = var.hard_terminate_timeout_minutes
  instance_manager_password         = var.instance_manager_password
}

# IAM Module for User Restrictions (existing)
module "iam" {
  source = "../../iam"

  environment = var.environment
  owner       = var.owner
  region      = var.region
  workshop_name = var.workshop_name
}

# IAM Lambda Module - Lambda Execution Role
# Note: We pass both ARN and name - name is used for count check (to avoid dependency issues),
# ARN is used in the actual policy
module "iam_lambda" {
  source = "../../modules/iam-lambda"

  environment              = var.environment
  owner                    = var.owner
  workshop_name            = var.workshop_name
  account_id               = data.aws_caller_identity.current.account_id
  region                   = var.region
  # Allow access to both Azure LLM configs and instance manager password secrets
  secrets_manager_secret_arn = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:azure/llm/configs*"
  instance_manager_password_secret_arn = module.storage.instance_manager_password_secret_arn
  instance_manager_password_secret_name = module.storage.instance_manager_password_secret_name
}


# Lambda Module - All Lambda Functions
# The module handles the dependency: status Lambda is created first, then user_management uses its URL
module "lambda" {
  source = "../../modules/lambda"

  environment              = var.environment
  owner                    = var.owner
  workshop_name            = var.workshop_name
  classroom_name           = var.classroom_name
  region                   = var.region
  lambda_role_arn          = module.iam_lambda.lambda_role_arn
  status_lambda_url        = ""  # Module will use its own status URL internally
  subnet_id                = try(data.terraform_remote_state.common.outputs.subnet_id, "")
  security_group_ids       = try([data.terraform_remote_state.common.outputs.security_group_id], [])
  iam_instance_profile_name = try(data.terraform_remote_state.common.outputs.ec2_iam_instance_profile_name, "")
  instance_type            = var.ec2_instance_type
  admin_cleanup_interval_days = var.admin_cleanup_interval_days
  admin_cleanup_schedule   = var.admin_cleanup_schedule
  functions_path           = "../../../../functions/packages"
  instance_manager_password_secret_name = module.storage.instance_manager_password_secret_name
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

# Monitoring Module - CloudWatch Events

# CloudFront Module - Custom Domain and CDN for User Management
module "cloudfront_user_management" {
  source = "../../modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
  workshop_name     = var.workshop_name
  domain_name      = "testus-patronus.testingfantasy.com"
  lambda_function_url = module.lambda.user_management_url
  # Set to true only after DNS validation records are added to Route 53
  # After adding the DNS record, wait 5-10 minutes, then set this to true and run terraform apply
  wait_for_certificate_validation = true
}

# CloudFront Module - Custom Domain and CDN for Dify Jira API
module "cloudfront_dify_jira" {
  source = "../../modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
  workshop_name     = var.workshop_name
  domain_name      = "dify-jira.testingfantasy.com"
  lambda_function_url = module.lambda.dify_jira_api_url
  # Set to true only after DNS validation records are added to Route 53
  # After adding the DNS record, wait 5-10 minutes, then set this to true and run terraform apply
  wait_for_certificate_validation = true
}

# Static Website Module - Root Domain (testingfantasy.com)
# DISABLED: The testing_fantasy application is now deployed with AWS Amplify
# 
# Why this is disabled:
# - Amplify automatically creates and manages its own ACM certificate for custom domains
# - Amplify handles SSL/TLS certificates, so Terraform-managed certificate is not needed
# - Route 53 DNS records for Amplify are configured in the Amplify console, not Terraform
# - This avoids duplicate certificates and conflicts
#
# If you need to manage the root domain with Terraform CloudFront instead of Amplify,
# uncomment this module and ensure Amplify custom domain is removed first.
#
# module "static_website" {
#   source = "../../modules/static-website"
#
#   providers = {
#     aws.us_east_1 = aws.us_east_1
#   }
#
#   environment      = var.environment
#   owner            = var.owner
#   workshop_name     = var.workshop_name
#   domain_name      = "testingfantasy.com"
#   wait_for_certificate_validation = true
# }
