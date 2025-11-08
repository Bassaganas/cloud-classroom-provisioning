# Provider for us-east-1 (required for CloudFront ACM certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# IAM Module for User Restrictions (existing)
module "iam" {
  source = "./iam"

  environment = var.environment
  owner       = var.owner
  region      = var.region
}

# IAM Lambda Module - Lambda Execution Role
# Note: We pass both ARN and name - name is used for count check (to avoid dependency issues),
# ARN is used in the actual policy
module "iam_lambda" {
  source = "./modules/iam-lambda"

  environment              = var.environment
  owner                    = var.owner
  account_id               = data.aws_caller_identity.current.account_id
  # Allow access to both Azure LLM configs and instance manager password secrets
  secrets_manager_secret_arn = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:azure/llm/configs*"
  instance_manager_password_secret_arn = module.storage.instance_manager_password_secret_arn
  instance_manager_password_secret_name = module.storage.instance_manager_password_secret_name
}

# Storage Module - DynamoDB, SSM Parameters, and Secrets Manager
module "storage" {
  source = "./modules/storage"

  environment                        = var.environment
  owner                             = var.owner
  instance_stop_timeout_minutes     = var.instance_stop_timeout_minutes
  instance_terminate_timeout_minutes = var.instance_terminate_timeout_minutes
  instance_hard_terminate_timeout_minutes = var.hard_terminate_timeout_minutes
  instance_manager_password         = var.instance_manager_password
}

# Compute Module - EC2 Instances, Security Groups, EC2 IAM
module "compute" {
  source = "./modules/compute"

  environment         = var.environment
  owner               = var.owner
  ec2_pool_size       = var.ec2_pool_size
  ec2_ami_id          = var.ec2_ami_id
  ec2_instance_type   = var.ec2_instance_type
  ec2_subnet_id       = var.ec2_subnet_id
  user_data_script_path = "${path.module}/user_data.sh"
}

# Lambda Module - All Lambda Functions
# The module handles the dependency: status Lambda is created first, then user_management uses its URL
module "lambda" {
  source = "./modules/lambda"

  environment              = var.environment
  owner                    = var.owner
  classroom_name           = var.classroom_name
  region                   = var.region
  lambda_role_arn          = module.iam_lambda.lambda_role_arn
  status_lambda_url        = ""  # Module will use its own status URL internally
  subnet_id                = module.compute.subnet_id
  security_group_ids       = [module.compute.security_group_id]
  iam_instance_profile_name = module.compute.ec2_iam_instance_profile_name
  instance_type            = var.ec2_instance_type
  admin_cleanup_interval_days = var.admin_cleanup_interval_days
  admin_cleanup_schedule   = var.admin_cleanup_schedule
  functions_path           = "../../functions/packages"
  instance_manager_password_secret_name = module.storage.instance_manager_password_secret_name
}

# Monitoring Module - CloudWatch Events
module "monitoring" {
  source = "./modules/monitoring"

  environment                = var.environment
  stop_old_instances_lambda_arn = module.lambda.stop_old_instances_function_arn
  admin_cleanup_lambda_arn   = module.lambda.admin_cleanup_function_arn
  admin_cleanup_schedule     = var.admin_cleanup_schedule
}

# CloudFront Module - Custom Domain and CDN for Instance Manager
module "cloudfront_instance_manager" {
  source = "./modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
  domain_name      = "ec2-management.testingfantasy.com"
  lambda_function_url = module.lambda.instance_manager_url
  # Set to true only after DNS validation records are added to Route 53
  # After adding the DNS record, wait 5-10 minutes, then set this to true and run terraform apply
  wait_for_certificate_validation = true
}

# CloudFront Module - Custom Domain and CDN for User Management
module "cloudfront_user_management" {
  source = "./modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
  domain_name      = "testus-patronus.testingfantasy.com"
  lambda_function_url = module.lambda.user_management_url
  # Set to true only after DNS validation records are added to Route 53
  # After adding the DNS record, wait 5-10 minutes, then set this to true and run terraform apply
  wait_for_certificate_validation = false
}

# CloudFront Module - Custom Domain and CDN for Dify Jira API
module "cloudfront_dify_jira" {
  source = "./modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
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
#   source = "./modules/static-website"
#
#   providers = {
#     aws.us_east_1 = aws.us_east_1
#   }
#
#   environment      = var.environment
#   owner            = var.owner
#   domain_name      = "testingfantasy.com"
#   wait_for_certificate_validation = false
# }
