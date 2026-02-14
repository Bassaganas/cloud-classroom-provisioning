# Shared/common infrastructure for all workshops.
# Add shared modules (e.g., EC2 manager/control plane) here.

data "aws_caller_identity" "current" {}

data "aws_route53_zone" "primary" {
  name         = "${var.base_domain}."
  private_zone = false
}

# Wildcard certificate for per-instance HTTPS (ALB)
resource "aws_acm_certificate" "instance_https" {
  domain_name       = "*.${var.base_domain}"
  validation_method = "DNS"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Resource Group for shared/common resources
resource "aws_resourcegroups_group" "shared" {
  name        = "workshop-${var.workshop_name}-${var.environment}"
  description = "Shared classroom infrastructure EC2 manager cleanup storage ${var.environment}"

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
  source = "../storage"

  environment                             = var.environment
  owner                                   = var.owner
  workshop_name                           = var.workshop_name
  instance_stop_timeout_minutes           = var.instance_stop_timeout_minutes
  instance_terminate_timeout_minutes      = var.instance_terminate_timeout_minutes
  instance_hard_terminate_timeout_minutes = var.hard_terminate_timeout_minutes
  instance_manager_password               = var.instance_manager_password
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
  instance_manager_password_secret_arn  = module.storage.instance_manager_password_secret_arn
  instance_manager_password_secret_name = module.storage.instance_manager_password_secret_name
}

# Compute Module - EC2 Instances, Security Groups, EC2 IAM
module "compute" {
  source = "../compute"

  environment           = var.environment
  owner                 = var.owner
  workshop_name         = var.workshop_name
  ec2_pool_size         = var.ec2_pool_size
  ec2_ami_id            = var.ec2_ami_id
  ec2_instance_type     = var.ec2_instance_type
  ec2_subnet_id         = var.ec2_subnet_id
  user_data_script_path = ""
}

# Lambda Module - EC2 manager functions only
module "lambda" {
  source = "../lambda"

  environment                             = var.environment
  owner                                   = var.owner
  workshop_name                           = var.workshop_name
  classroom_name                          = var.classroom_name
  region                                  = var.region
  lambda_role_arn                         = module.iam_lambda.lambda_role_arn
  subnet_id                               = module.compute.subnet_id
  security_group_ids                      = [module.compute.security_group_id]
  iam_instance_profile_name               = module.compute.ec2_iam_instance_profile_name
  instance_type                           = var.ec2_instance_type
  admin_cleanup_interval_days             = var.admin_cleanup_interval_days
  admin_cleanup_schedule                  = var.admin_cleanup_schedule
  functions_path                          = "../../../../functions/packages"
  instance_manager_password_secret_name   = module.storage.instance_manager_password_secret_name
  instance_manager_template_map_parameter = "/classroom/templates/${var.environment}"
  instance_manager_base_domain            = var.base_domain
  instance_manager_hosted_zone_id         = data.aws_route53_zone.primary.zone_id
  instance_manager_https_cert_arn         = aws_acm_certificate.instance_https.arn

  enable_status             = false
  enable_user_management    = false
  enable_dify_jira_api      = false
  enable_instance_manager   = true
  enable_stop_old_instances = true
  enable_admin_cleanup      = true

  instance_manager_memory_size = var.instance_manager_memory_size
  instance_manager_timeout     = var.instance_manager_timeout
}

# API Gateway Module - REST API for Instance Manager
module "api_gateway" {
  source = "../api-gateway"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  lambda_function_arn            = module.lambda.instance_manager_function_arn
  environment                     = var.environment
  owner                          = var.owner
  workshop_name                  = var.workshop_name
  domain_name                    = "ec2-management-${var.environment}.${var.base_domain}"
  api_custom_domain_name         = "ec2-management-api-${var.environment}.${var.base_domain}"
  base_domain                    = var.base_domain
  wait_for_certificate_validation = true # Enable to create API Gateway custom domain
}

# Monitoring Module - CloudWatch Events
module "monitoring" {
  source = "../monitoring"

  environment                   = var.environment
  owner                         = var.owner
  workshop_name                 = var.workshop_name
  stop_old_instances_lambda_arn = module.lambda.stop_old_instances_function_arn
  admin_cleanup_lambda_arn      = module.lambda.admin_cleanup_function_arn
  admin_cleanup_schedule        = var.admin_cleanup_schedule
}

# S3 Module - Frontend static hosting
module "s3_frontend" {
  source = "../s3"

  bucket_name   = "ec2-manager-frontend"
  environment   = var.environment
  owner         = var.owner
  workshop_name = var.workshop_name
}

# CloudFront Module - Custom Domain and CDN for Instance Manager
module "cloudfront_instance_manager" {
  source = "../cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment        = var.environment
  owner              = var.owner
  workshop_name      = var.workshop_name
  domain_name        = "ec2-management-${var.environment}.${var.base_domain}"
  # Use API Gateway custom domain if available, otherwise fall back to regional endpoint
  # Note: We determine use_api_gateway_custom_domain from input vars to avoid circular dependency
  use_api_gateway_custom_domain = module.api_gateway.api_custom_domain_name != "" && module.api_gateway.wait_for_certificate_validation
  # Always use the regional domain name (known at plan time)
  # When custom domain is created, we'll need to update CloudFront origin in a subsequent apply
  # or use a data source to get the custom domain CloudFront name after it's created
  api_gateway_domain            = module.api_gateway.api_gateway_domain_name
  s3_bucket_domain             = module.s3_frontend.bucket_regional_domain_name
  s3_origin_access_identity    = module.s3_frontend.origin_access_identity_path
  wait_for_certificate_validation = true
  # Disable CloudFront logging to avoid conflicts with existing resources
  # Logging is optional and only used for debugging
  enable_cloudwatch_logging = false
}
