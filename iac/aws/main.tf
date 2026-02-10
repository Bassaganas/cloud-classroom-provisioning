# Root module that includes all infrastructure
# This consolidates common, fellowship, and testus_patronus into a single state

# Provider for main region
provider "aws" {
  region = var.region
}

# Provider for us-east-1 (required for CloudFront ACM certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# Common Infrastructure Module
module "common" {
  source = "./modules/common"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment                        = var.environment
  owner                              = var.owner
  region                             = var.region
  base_domain                        = var.base_domain
  workshop_name                      = var.common_workshop_name
  classroom_name                     = var.common_classroom_name
  ec2_pool_size                      = var.common_ec2_pool_size
  ec2_ami_id                         = var.common_ec2_ami_id
  ec2_instance_type                  = var.common_ec2_instance_type
  ec2_subnet_id                      = var.common_ec2_subnet_id
  instance_stop_timeout_minutes      = var.common_instance_stop_timeout_minutes
  instance_terminate_timeout_minutes = var.common_instance_terminate_timeout_minutes
  hard_terminate_timeout_minutes     = var.common_hard_terminate_timeout_minutes
  admin_cleanup_interval_days        = var.common_admin_cleanup_interval_days
  admin_cleanup_schedule             = var.common_admin_cleanup_schedule
  instance_manager_password          = var.common_instance_manager_password
  instance_manager_memory_size       = var.common_instance_manager_memory_size
  instance_manager_timeout           = var.common_instance_manager_timeout
}

# Fellowship Workshop Module
module "workshop_fellowship" {
  source = "./modules/workshop"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  depends_on = [module.common]

  # Common infrastructure outputs
  common_subnet_id                             = module.common.subnet_id
  common_security_group_ids                    = [module.common.security_group_id]
  common_ec2_iam_instance_profile_name         = module.common.ec2_iam_instance_profile_name
  common_instance_manager_password_secret_name = module.common.instance_manager_password_secret_name
  common_instance_manager_password_secret_arn  = module.common.instance_manager_password_secret_arn

  # Workshop-specific variables
  environment                             = var.environment
  owner                                   = var.owner
  region                                  = var.region
  workshop_name                           = var.fellowship_workshop_name
  classroom_name                          = var.fellowship_classroom_name
  ec2_ami_id                              = var.fellowship_ec2_ami_id
  ec2_instance_type                       = var.fellowship_ec2_instance_type
  instance_stop_timeout_minutes           = var.fellowship_instance_stop_timeout_minutes
  instance_terminate_timeout_minutes      = var.fellowship_instance_terminate_timeout_minutes
  hard_terminate_timeout_minutes          = var.fellowship_hard_terminate_timeout_minutes
  admin_cleanup_interval_days             = var.fellowship_admin_cleanup_interval_days
  admin_cleanup_schedule                  = var.fellowship_admin_cleanup_schedule
  instance_manager_password               = var.fellowship_instance_manager_password
  skip_iam_user_creation                  = var.fellowship_skip_iam_user_creation
  user_management_memory_size             = var.fellowship_user_management_memory_size
  user_management_timeout                 = var.fellowship_user_management_timeout
  user_management_provisioned_concurrency = var.fellowship_user_management_provisioned_concurrency
  user_management_reserved_concurrency    = var.fellowship_user_management_reserved_concurrency
  instance_manager_memory_size            = var.fellowship_instance_manager_memory_size
  instance_manager_timeout                = var.fellowship_instance_manager_timeout
  user_management_domain                  = var.fellowship_user_management_domain
  dify_jira_domain                        = var.fellowship_dify_jira_domain
  wait_for_certificate_validation         = var.fellowship_wait_for_certificate_validation

  # Security group rules for Jenkins (8080) and MailHog (8025)
  security_group_rules = {
    jenkins = {
      from_port   = 8080
      to_port     = 8080
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
      description = "Jenkins access for fellowship workshop"
    }
    mailhog = {
      from_port   = 8025
      to_port     = 8025
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
      description = "MailHog web UI access for fellowship workshop"
    }
  }
}

# Testus Patronus Workshop Module
module "workshop_testus_patronus" {
  source = "./modules/workshop"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  depends_on = [module.common]

  # Common infrastructure outputs
  common_subnet_id                             = module.common.subnet_id
  common_security_group_ids                    = [module.common.security_group_id]
  common_ec2_iam_instance_profile_name         = module.common.ec2_iam_instance_profile_name
  common_instance_manager_password_secret_name = module.common.instance_manager_password_secret_name
  common_instance_manager_password_secret_arn  = module.common.instance_manager_password_secret_arn

  # Workshop-specific variables
  environment                             = var.environment
  owner                                   = var.owner
  region                                  = var.region
  workshop_name                           = var.testus_patronus_workshop_name
  classroom_name                          = var.testus_patronus_classroom_name
  ec2_ami_id                              = var.testus_patronus_ec2_ami_id
  ec2_instance_type                       = var.testus_patronus_ec2_instance_type
  instance_stop_timeout_minutes           = var.testus_patronus_instance_stop_timeout_minutes
  instance_terminate_timeout_minutes      = var.testus_patronus_instance_terminate_timeout_minutes
  hard_terminate_timeout_minutes          = var.testus_patronus_hard_terminate_timeout_minutes
  admin_cleanup_interval_days             = var.testus_patronus_admin_cleanup_interval_days
  admin_cleanup_schedule                  = var.testus_patronus_admin_cleanup_schedule
  instance_manager_password               = var.testus_patronus_instance_manager_password
  skip_iam_user_creation                  = var.testus_patronus_skip_iam_user_creation
  user_management_memory_size             = var.testus_patronus_user_management_memory_size
  user_management_timeout                 = var.testus_patronus_user_management_timeout
  user_management_provisioned_concurrency = var.testus_patronus_user_management_provisioned_concurrency
  user_management_reserved_concurrency    = var.testus_patronus_user_management_reserved_concurrency
  instance_manager_memory_size            = var.testus_patronus_instance_manager_memory_size
  instance_manager_timeout                = var.testus_patronus_instance_manager_timeout
  user_management_domain                  = var.testus_patronus_user_management_domain
  dify_jira_domain                        = var.testus_patronus_dify_jira_domain
  wait_for_certificate_validation         = var.testus_patronus_wait_for_certificate_validation

  # No additional security group rules for testus_patronus
  security_group_rules = {}
}
