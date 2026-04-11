# OAI for the Docusaurus docs site (required so CloudFront can access the private S3 bucket)
resource "aws_cloudfront_origin_access_identity" "docs" {
  comment = "OAI for docusaurus-docs-bucket-default (docs.fellowship.testingfantasy.com)"
}

resource "aws_s3_bucket_policy" "docs" {
  bucket = "docusaurus-docs-bucket-default"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAI"
        Effect = "Allow"
        Principal = {
          CanonicalUser = aws_cloudfront_origin_access_identity.docs.s3_canonical_user_id
        }
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::docusaurus-docs-bucket-default/*"
      }
    ]
  })
}

# Docusaurus Docs CloudFront Distribution
module "docs_cloudfront" {
  source = "./modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment                     = var.environment
  owner                           = var.owner
  workshop_name                   = "docs"
  domain_name                     = "docs.fellowship.testingfantasy.com"
  s3_origin_bucket                = "docusaurus-docs-bucket-default"
  s3_origin_access_identity       = aws_cloudfront_origin_access_identity.docs.cloudfront_access_identity_path
  wait_for_certificate_validation = var.enable_docs_dns_records
  enable_route53_records          = var.enable_docs_dns_records
  zone_name                       = "testingfantasy.com"
}
resource "aws_ssm_parameter" "tutorial_always_on_links" {
  name        = "/cloud-classroom/tutorial-always-on-links"
  description = "Always-on environment links for tutorials (used by EC2 Manager frontend)"
  type        = "String"
  value = jsonencode({
    fellowship = [
      {
        label = "LOTR SUT"
        link  = "https://lotr.testingfantasy.com/"
      }
    ]
  })
  tier = "Standard"
}

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
  shared_core_mode                   = var.shared_core_mode
  shared_core_jenkins_domain         = var.shared_core_jenkins_domain
  shared_core_gitea_domain           = var.shared_core_gitea_domain
}

module "shared_core_compute" {
  source = "./modules/shared-core-compute"

  depends_on = [module.common]

  owner                                = var.owner
  base_domain                          = var.base_domain
  shared_core_environment              = var.shared_core_environment
  shared_core_ami_id                   = var.shared_core_ami_id
  shared_core_instance_type            = var.shared_core_instance_type
  shared_core_subnet_id                = var.shared_core_subnet_id
  shared_core_key_name                 = var.shared_core_key_name
  shared_core_ssh_host                 = var.shared_core_ssh_host
  shared_core_jenkins_domain           = var.shared_core_jenkins_domain
  shared_core_gitea_domain             = var.shared_core_gitea_domain
  shared_core_manage_route53_records   = var.shared_core_manage_route53_records
  shared_core_security_group_id        = var.shared_core_security_group_id
  common_subnet_id                     = module.common.subnet_id
  common_shared_core_security_group_id = module.common.shared_core_security_group_id
  common_ec2_iam_instance_profile_name = module.common.ec2_iam_instance_profile_name
}

module "shared_core_secrets" {
  source = "./modules/shared-core-secrets"

  owner                              = var.owner
  shared_core_environment            = var.shared_core_environment
  shared_core_ssh_private_key        = var.shared_core_ssh_private_key
  shared_core_gh_repo_token          = var.shared_core_gh_repo_token
  shared_core_jenkins_admin_password = var.shared_core_jenkins_admin_password
  shared_core_gitea_admin_password   = var.shared_core_gitea_admin_password
}

module "shared_core_iam" {
  source = "./modules/shared-core-iam"

  environment                    = var.environment
  owner                          = var.owner
  region                         = var.region
  shared_core_environment        = var.shared_core_environment
  shared_core_github_owner       = var.shared_core_github_owner
  shared_core_github_repo        = var.shared_core_github_repo
  shared_core_github_environment = var.shared_core_github_environment
  shared_core_deploy_secret_arn  = module.shared_core_secrets.deploy_secret_arn
}

module "shared_core_config" {
  source = "./modules/shared-core-config"

  owner                         = var.owner
  shared_core_environment       = var.shared_core_environment
  shared_core_instance_id       = module.shared_core_compute.instance_id
  shared_core_ssh_host          = module.shared_core_compute.ssh_host
  shared_core_jenkins_domain    = var.shared_core_jenkins_domain
  shared_core_gitea_domain      = var.shared_core_gitea_domain
  shared_core_security_group_id = module.shared_core_compute.security_group_id
  shared_core_hosted_zone_id    = module.shared_core_compute.hosted_zone_id
  shared_core_gitea_admin_user  = var.shared_core_gitea_admin_user
  shared_core_gitea_admin_email = var.shared_core_gitea_admin_email
  shared_core_gitea_org_name    = var.shared_core_gitea_org_name
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
  common_ec2_iam_role_arn                      = module.common.ec2_iam_role_arn
  common_instance_manager_password_secret_name = module.common.instance_manager_password_secret_name
  common_instance_manager_password_secret_arn  = module.common.instance_manager_password_secret_arn

  # Workshop-specific variables
  environment                             = var.environment
  owner                                   = var.owner
  region                                  = var.region
  base_domain                             = var.base_domain
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
  leaderboard_api_domain                  = var.fellowship_leaderboard_api_domain
  wait_for_certificate_validation         = var.fellowship_wait_for_certificate_validation

  # Palantir event-sourcing artifact
  lambda_artifact_bucket = var.lambda_artifact_bucket
  lambda_artifact_key    = var.lambda_artifact_key

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
  common_ec2_iam_role_arn                      = module.common.ec2_iam_role_arn
  common_instance_manager_password_secret_name = module.common.instance_manager_password_secret_name
  common_instance_manager_password_secret_arn  = module.common.instance_manager_password_secret_arn

  # Workshop-specific variables
  environment                             = var.environment
  owner                                   = var.owner
  region                                  = var.region
  base_domain                             = var.base_domain
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
  leaderboard_api_domain                  = var.testus_patronus_leaderboard_api_domain
  wait_for_certificate_validation         = var.testus_patronus_wait_for_certificate_validation

  # Palantir event-sourcing artifact
  lambda_artifact_bucket = var.lambda_artifact_bucket
  lambda_artifact_key    = var.lambda_artifact_key

  # No additional security group rules for testus_patronus
  security_group_rules = {}
}
