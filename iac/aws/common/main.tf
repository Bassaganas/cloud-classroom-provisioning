# Shared/common infrastructure for all workshops.
# Add shared modules (e.g., EC2 manager/control plane) here.

provider "aws" {
  region = var.region
}

# Provider for us-east-1 (required for CloudFront ACM certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}

# Resource Group for shared/common resources
resource "aws_resourcegroups_group" "shared" {
  name = "workshop-${var.workshop_name}-${var.environment}"
  description = "Shared classroom infrastructure (EC2 manager, cleanup, storage) for ${var.environment}"

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

# Storage Module - DynamoDB, SSM Parameters, and Secrets Manager
module "storage" {
  source = "../modules/storage"

  environment                        = var.environment
  owner                             = var.owner
  workshop_name                      = var.workshop_name
  instance_stop_timeout_minutes     = var.instance_stop_timeout_minutes
  instance_terminate_timeout_minutes = var.instance_terminate_timeout_minutes
  instance_hard_terminate_timeout_minutes = var.hard_terminate_timeout_minutes
  instance_manager_password         = var.instance_manager_password
}

# IAM Lambda Module - Lambda Execution Role
module "iam_lambda" {
  source = "../modules/iam-lambda"

  environment              = var.environment
  owner                    = var.owner
  workshop_name            = var.workshop_name
  account_id               = data.aws_caller_identity.current.account_id
  region                   = var.region
  secrets_manager_secret_arn = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:azure/llm/configs*"
  instance_manager_password_secret_arn = module.storage.instance_manager_password_secret_arn
  instance_manager_password_secret_name = module.storage.instance_manager_password_secret_name
}

# Compute Module - EC2 Instances, Security Groups, EC2 IAM
module "compute" {
  source = "../modules/compute"

  environment         = var.environment
  owner               = var.owner
  workshop_name       = var.workshop_name
  ec2_pool_size       = var.ec2_pool_size
  ec2_ami_id          = var.ec2_ami_id
  ec2_instance_type   = var.ec2_instance_type
  ec2_subnet_id       = var.ec2_subnet_id
  user_data_script_path = ""
}

# Lambda Module - EC2 manager functions only
module "lambda" {
  source = "../modules/lambda"

  environment              = var.environment
  owner                    = var.owner
  workshop_name            = var.workshop_name
  classroom_name           = var.classroom_name
  region                   = var.region
  lambda_role_arn          = module.iam_lambda.lambda_role_arn
  subnet_id                = module.compute.subnet_id
  security_group_ids       = [module.compute.security_group_id]
  iam_instance_profile_name = module.compute.ec2_iam_instance_profile_name
  instance_type            = var.ec2_instance_type
  admin_cleanup_interval_days = var.admin_cleanup_interval_days
  admin_cleanup_schedule   = var.admin_cleanup_schedule
  functions_path           = "../../../functions/packages"
  instance_manager_password_secret_name = module.storage.instance_manager_password_secret_name

  enable_status            = false
  enable_user_management   = false
  enable_dify_jira_api      = false
  enable_instance_manager  = true
  enable_stop_old_instances = true
  enable_admin_cleanup     = true

  instance_manager_memory_size = var.instance_manager_memory_size
  instance_manager_timeout     = var.instance_manager_timeout
}

# Monitoring Module - CloudWatch Events
module "monitoring" {
  source = "../modules/monitoring"

  environment                = var.environment
  owner                       = var.owner
  workshop_name               = var.workshop_name
  stop_old_instances_lambda_arn = module.lambda.stop_old_instances_function_arn
  admin_cleanup_lambda_arn   = module.lambda.admin_cleanup_function_arn
  admin_cleanup_schedule     = var.admin_cleanup_schedule
}

# CloudFront Module - Custom Domain and CDN for Instance Manager
module "cloudfront_instance_manager" {
  source = "../modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment      = var.environment
  owner            = var.owner
  workshop_name     = var.workshop_name
  domain_name      = "ec2-management.testingfantasy.com"
  lambda_function_url = module.lambda.instance_manager_url
  wait_for_certificate_validation = true
}
