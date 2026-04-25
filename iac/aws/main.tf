# OAC for the Docusaurus docs site (modern replacement for OAI)
resource "aws_cloudfront_origin_access_control" "docs" {
  name                              = "docs-fellowship-${var.environment}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ─────────────────────────────────────────────────────────────────────────────
# Leadership Board — S3 + CloudFront + Route53
# ─────────────────────────────────────────────────────────────────────────────

module "leadership" {
  source = "./modules/leadership"

  environment = var.environment
  owner       = var.owner
}

module "leadership_cloudfront" {
  source = "./modules/cloudfront"

  providers = {
    aws.us_east_1 = aws.us_east_1
  }

  environment                     = var.environment
  owner                           = var.owner
  workshop_name                   = "leadership"
  domain_name                     = "leadership.fellowship.testingfantasy.com"
  s3_origin_bucket                = module.leadership.s3_bucket_name
  s3_origin_access_control_id     = module.leadership.oac_id
  enable_s3_path_rewrite          = true
  wait_for_certificate_validation = var.enable_docs_dns_records
  enable_route53_records          = var.enable_docs_dns_records
  zone_name                       = "testingfantasy.com"

  depends_on = [module.leadership]
}

resource "aws_s3_bucket_policy" "leadership" {
  bucket = module.leadership.s3_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipalReadOnly"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::${module.leadership.s3_bucket_name}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = module.leadership_cloudfront.cloudfront_distribution_arn
          }
        }
      }
    ]
  })

  depends_on = [module.leadership_cloudfront]
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
  s3_origin_bucket                = "docusaurus-docs-bucket-${var.environment}"
  s3_origin_access_control_id     = aws_cloudfront_origin_access_control.docs.id
  wait_for_certificate_validation = var.enable_docs_dns_records
  enable_route53_records          = var.enable_docs_dns_records
  zone_name                       = "testingfantasy.com"

  depends_on = [aws_s3_bucket.docs]
}

resource "aws_s3_bucket" "docs" {
  # Name must stay in sync with DOCS_S3_BUCKET in palantir-jenkins-ai/deploy-docusaurus.yml.
  # The docs site is environment-independent (always "prod" bucket for the live docs site),
  # but we keep the environment suffix so dev applies can create a dev bucket without collision.
  bucket = "docusaurus-docs-bucket-${var.environment}"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = "docs"
    Company     = "TestingFantasy"
  }
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket = aws_s3_bucket.docs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "docs" {
  bucket = aws_s3_bucket.docs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipalReadOnly"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::docusaurus-docs-bucket-${var.environment}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = module.docs_cloudfront.cloudfront_distribution_arn
          }
        }
      }
    ]
  })

  depends_on = [module.docs_cloudfront, aws_s3_bucket_public_access_block.docs]
}

# Publish docs CloudFront distribution ID to SSM so palantir-jenkins-ai/deploy-docusaurus.yml
# can read it as vars.DOCS_CF_DISTRIBUTION_ID without hardcoding a value in the workflow.
resource "aws_ssm_parameter" "docs_cf_distribution_id" {
  name        = "/cloud-classroom/docs/cloudfront-distribution-id"
  description = "CloudFront distribution ID for the Docusaurus docs site (read by deploy-docusaurus.yml)"
  type        = "String"
  value       = module.docs_cloudfront.cloudfront_distribution_id
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }

  depends_on = [module.docs_cloudfront]
}

resource "aws_ssm_parameter" "docs_s3_bucket" {
  name        = "/cloud-classroom/docs/s3-bucket"
  description = "S3 bucket name for the Docusaurus docs site (read by deploy-docusaurus.yml)"
  type        = "String"
  value       = aws_s3_bucket.docs.id
  overwrite   = true

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }

  depends_on = [aws_s3_bucket.docs]
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
  tier      = "Standard"
  overwrite = true
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

# ─────────────────────────────────────────────────────────────────────────────
# Shared-core group — only applied when manage_shared_core = true.
# Automated dev CI sets manage_shared_core = false so that a routine push to
# main never touches the production Jenkins/Gitea host or its OIDC role.
# Use the deploy_manual workflow (workflow_dispatch, environment=prod) or a
# local terraform apply to manage these resources intentionally.
# ─────────────────────────────────────────────────────────────────────────────

module "jenkins_agent_ecs" {
  # Always-on — not gated by manage_shared_core — so that automated dev CI runs
  # (manage_shared_core=false) never destroy the ECS cluster while Jenkins agent
  # tasks are still running. Same rationale as the ECR repository below.

  source = "./modules/jenkins-agent-ecs"

  depends_on = [module.common]

  environment                   = var.environment
  owner                         = var.owner
  region                        = var.region
  vpc_id                        = module.common.vpc_id
  subnet_id                     = module.common.subnet_id
  shared_core_security_group_id = module.common.shared_core_security_group_id
  shared_core_ec2_role_name     = module.common.ec2_iam_role_name
  # ECR repo is managed here (always-on) so it is never destroyed by dev CI runs
  ecr_repository_url = aws_ecr_repository.jenkins_agent.repository_url
}

# Migrate state: the module was previously count-gated (instance [0]).
# This moved block lets Terraform update the state file in-place without
# destroying and recreating the ECS cluster.
moved {
  from = module.jenkins_agent_ecs[0]
  to   = module.jenkins_agent_ecs
}

# ── ECR repository (always-on — not gated by manage_shared_core) ─────────────
#
# Kept outside the jenkins_agent_ecs module so that automated dev CI runs
# (manage_shared_core=false) never destroy the repo and lose pushed images.
resource "aws_ecr_repository" "jenkins_agent" {
  name                 = "fellowship-jenkins-agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "jenkins-agent"
    Company     = "TestingFantasy"
  }

  # Allow Terraform to manage existing repositories without attempting to recreate them
  lifecycle {
    ignore_changes = []
  }
}

resource "aws_ecr_lifecycle_policy" "jenkins_agent" {
  repository = aws_ecr_repository.jenkins_agent.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

module "shared_core_compute" {
  count = var.manage_shared_core ? 1 : 0

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
  count = var.manage_shared_core ? 1 : 0

  source = "./modules/shared-core-secrets"

  owner                              = var.owner
  shared_core_environment            = var.shared_core_environment
  shared_core_ssh_private_key        = var.shared_core_ssh_private_key
  shared_core_gh_repo_token          = var.shared_core_gh_repo_token
  shared_core_jenkins_admin_password = var.shared_core_jenkins_admin_password
  shared_core_gitea_admin_password   = var.shared_core_gitea_admin_password
}

module "shared_core_iam" {
  count = var.manage_shared_core ? 1 : 0

  source = "./modules/shared-core-iam"

  environment                    = var.environment
  owner                          = var.owner
  region                         = var.region
  shared_core_environment        = var.shared_core_environment
  shared_core_github_owner       = var.shared_core_github_owner
  shared_core_github_repo        = var.shared_core_github_repo
  shared_core_github_environment = var.shared_core_github_environment
  shared_core_deploy_secret_arn  = module.shared_core_secrets[0].deploy_secret_arn
}

module "shared_core_config" {
  count = var.manage_shared_core ? 1 : 0

  source = "./modules/shared-core-config"

  owner                         = var.owner
  shared_core_environment       = var.shared_core_environment
  shared_core_instance_id       = module.shared_core_compute[0].instance_id
  shared_core_ssh_host          = module.shared_core_compute[0].ssh_host
  shared_core_jenkins_domain    = var.shared_core_jenkins_domain
  shared_core_gitea_domain      = var.shared_core_gitea_domain
  shared_core_security_group_id = module.shared_core_compute[0].security_group_id
  shared_core_hosted_zone_id    = var.shared_core_hosted_zone_id != "" ? var.shared_core_hosted_zone_id : module.shared_core_compute[0].hosted_zone_id
  shared_core_private_ip        = module.shared_core_compute[0].private_ip
  shared_core_gitea_admin_user  = var.shared_core_gitea_admin_user
  shared_core_gitea_admin_email = var.shared_core_gitea_admin_email
  shared_core_gitea_org_name    = var.shared_core_gitea_org_name

  # Jenkins ECS agent pool SSM parameters
  jenkins_agent_ecs_cluster_arn         = module.jenkins_agent_ecs.ecs_cluster_arn
  jenkins_agent_ecr_image               = aws_ecr_repository.jenkins_agent.repository_url
  jenkins_agent_ecs_security_group_id   = module.jenkins_agent_ecs.agent_security_group_id
  jenkins_agent_task_execution_role_arn = module.jenkins_agent_ecs.task_execution_role_arn
  jenkins_agent_task_role_arn           = module.jenkins_agent_ecs.task_role_arn
  jenkins_agent_subnet_id               = module.common.subnet_id
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
  common_instance_manager_url                  = module.common.instance_manager_url

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
  fellowship_lambdas_memory_size          = var.fellowship_lambdas_memory_size
  fellowship_lambdas_timeout              = var.fellowship_lambdas_timeout
  user_management_domain                  = var.fellowship_user_management_domain
  dify_jira_domain                        = var.fellowship_dify_jira_domain
  leaderboard_api_domain                  = var.fellowship_leaderboard_api_domain
  fellowship_user_management_domain       = var.fellowship_student_assignment_domain
  fellowship_sut_domain                   = var.fellowship_sut_domain
  fellowship_jenkins_domain               = var.fellowship_jenkins_domain
  fellowship_gitea_domain                 = var.fellowship_gitea_domain
  fellowship_gitea_api_domain             = var.fellowship_gitea_api_domain
  fellowship_gitea_org                    = var.fellowship_gitea_org
  destroy_key                             = var.fellowship_destroy_key
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
  common_instance_manager_url                  = module.common.instance_manager_url

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
