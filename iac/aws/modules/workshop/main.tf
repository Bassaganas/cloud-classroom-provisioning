# Parameterized workshop module
# This module creates all resources for a specific workshop

data "aws_caller_identity" "current" {}

# Data source for latest Amazon Linux 2 AMI (used if ec2_ami_id is not provided)
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

# Resource Group for this workshop
resource "aws_resourcegroups_group" "workshop" {
  name        = "resourcegroup-workshop-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
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

  environment                             = var.environment
  owner                                   = var.owner
  workshop_name                           = var.workshop_name
  region                                  = var.region
  instance_stop_timeout_minutes           = var.instance_stop_timeout_minutes
  instance_terminate_timeout_minutes      = var.instance_terminate_timeout_minutes
  instance_hard_terminate_timeout_minutes = var.hard_terminate_timeout_minutes
  instance_manager_password               = var.instance_manager_password
  create_instance_manager_password_secret = false # Workshops use the common/shared secret
}

# IAM Module for User Restrictions
module "iam" {
  source = "../iam"

  environment   = var.environment
  owner         = var.owner
  region        = var.region
  workshop_name = var.workshop_name
}

# IAM Lambda Module - Lambda Execution Role
module "iam_lambda" {
  source = "../iam-lambda"

  environment                           = var.environment
  owner                                 = var.owner
  workshop_name                         = var.workshop_name
  account_id                            = data.aws_caller_identity.current.account_id
  region                                = var.region
  secrets_manager_secret_arn            = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:azure/llm/configs*"
  instance_manager_password_secret_arn  = var.common_instance_manager_password_secret_arn
  instance_manager_password_secret_name = var.common_instance_manager_password_secret_name
}

# Lambda Module - All Lambda Functions
module "lambda" {
  source = "../lambda"

  environment                           = var.environment
  owner                                 = var.owner
  workshop_name                         = var.workshop_name
  classroom_name                        = var.classroom_name
  region                                = var.region
  lambda_role_arn                       = module.iam_lambda.lambda_role_arn
  status_lambda_url                     = "" # Module will use its own status URL internally
  subnet_id                             = var.common_subnet_id
  security_group_ids                    = var.common_security_group_ids
  iam_instance_profile_name             = var.common_ec2_iam_instance_profile_name
  instance_type                         = var.ec2_instance_type
  admin_cleanup_interval_days           = var.admin_cleanup_interval_days
  admin_cleanup_schedule                = var.admin_cleanup_schedule
  functions_path                        = "../../../../functions/packages"
  instance_manager_password_secret_name = var.common_instance_manager_password_secret_name
  skip_iam_user_creation                = var.skip_iam_user_creation

  enable_instance_manager   = false
  enable_stop_old_instances = false
  enable_admin_cleanup      = false

  # Lambda scaling and performance configuration
  user_management_memory_size             = var.user_management_memory_size
  user_management_timeout                 = var.user_management_timeout
  user_management_provisioned_concurrency = var.user_management_provisioned_concurrency
  user_management_reserved_concurrency    = var.user_management_reserved_concurrency
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

  environment                     = var.environment
  owner                           = var.owner
  workshop_name                   = var.workshop_name
  domain_name                     = var.user_management_domain
  lambda_function_url             = module.lambda.user_management_url
  wait_for_certificate_validation = var.wait_for_certificate_validation
  # Disable CloudFront logging to avoid conflicts with existing resources
  # Logging is optional and only used for debugging
  enable_cloudwatch_logging = false
}

# CloudFront Module - Custom Domain and CDN for Dify Jira API
module "cloudfront_dify_jira" {
  source = "../cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment                     = var.environment
  owner                           = var.owner
  workshop_name                   = var.workshop_name
  domain_name                     = var.dify_jira_domain
  lambda_function_url             = module.lambda.dify_jira_api_url
  wait_for_certificate_validation = var.wait_for_certificate_validation
  # Disable CloudFront logging to avoid conflicts with existing resources
  # Logging is optional and only used for debugging
  enable_cloudwatch_logging = false
}

# S3 Module - Fellowship SUT deployment (only for fellowship workshop)
module "s3_sut" {
  count = var.workshop_name == "fellowship" || var.workshop_name == "fellowship-of-the-build" ? 1 : 0
  source = "../s3-sut"
  
  environment   = var.environment
  owner         = var.owner
  workshop_name = var.workshop_name
  region        = var.region
}

# SSM Parameter for SUT bucket name (only for fellowship workshop)
resource "aws_ssm_parameter" "sut_bucket_name" {
  count = var.workshop_name == "fellowship" || var.workshop_name == "fellowship-of-the-build" ? 1 : 0
  
  name        = "/classroom/fellowship/sut-bucket"
  description = "Name of the S3 bucket containing Fellowship SUT files"
  type        = "String"
  value       = module.s3_sut[0].bucket_name
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# IAM Policy for S3 access to Fellowship SUT bucket (attached to common EC2 IAM role)
# Get the role name from the instance profile
data "aws_iam_instance_profile" "common_profile" {
  count = (var.workshop_name == "fellowship" || var.workshop_name == "fellowship-of-the-build") && var.common_ec2_iam_instance_profile_name != "" ? 1 : 0
  name  = var.common_ec2_iam_instance_profile_name
}

resource "aws_iam_role_policy" "ec2_sut_access" {
  count = (var.workshop_name == "fellowship" || var.workshop_name == "fellowship-of-the-build") && length(data.aws_iam_instance_profile.common_profile) > 0 ? 1 : 0
  name  = "ec2-sut-s3-access-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role  = data.aws_iam_instance_profile.common_profile[0].role_name

  # Explicit dependency on S3 bucket to ensure it exists before policy is created
  depends_on = [module.s3_sut]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject"]
      Resource = "${module.s3_sut[0].bucket_arn}/*"
    }]
  })
}
