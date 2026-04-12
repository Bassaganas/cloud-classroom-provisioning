locals {
  shared_core_prefix = "/classroom/shared-core/${var.shared_core_environment}"
}

resource "aws_ssm_parameter" "shared_core_instance_id" {
  name        = "${local.shared_core_prefix}/instance-id"
  description = "EC2 instance ID for the shared core host"
  type        = "String"
  value       = var.shared_core_instance_id
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_ssh_host" {
  name        = "${local.shared_core_prefix}/ssh-host"
  description = "SSH host for the shared core EC2 instance"
  type        = "String"
  value       = var.shared_core_ssh_host
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_jenkins_domain" {
  count = try(trimspace(var.shared_core_jenkins_domain), "") != "" ? 1 : 0

  name        = "${local.shared_core_prefix}/jenkins-domain"
  description = "Public Jenkins domain for the shared core stack"
  type        = "String"
  value       = var.shared_core_jenkins_domain
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_gitea_domain" {
  count = try(trimspace(var.shared_core_gitea_domain), "") != "" ? 1 : 0

  name        = "${local.shared_core_prefix}/gitea-domain"
  description = "Public Gitea domain for the shared core stack"
  type        = "String"
  value       = var.shared_core_gitea_domain
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_security_group_id" {
  name        = "${local.shared_core_prefix}/security-group-id"
  description = "Security group ID used by the shared core EC2 instance"
  type        = "String"
  value       = var.shared_core_security_group_id
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_hosted_zone_id" {
  count = try(trimspace(var.shared_core_hosted_zone_id), "") != "" ? 1 : 0

  name        = "${local.shared_core_prefix}/hosted-zone-id"
  description = "Route53 hosted zone ID for shared-core Jenkins and Gitea records"
  type        = "String"
  value       = var.shared_core_hosted_zone_id
  tier        = "Standard"
  overwrite   = true

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_gitea_admin_user" {
  name        = "${local.shared_core_prefix}/gitea-admin-user"
  description = "Gitea admin username for the shared core stack"
  type        = "String"
  value       = var.shared_core_gitea_admin_user
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_gitea_admin_email" {
  name        = "${local.shared_core_prefix}/gitea-admin-email"
  description = "Gitea admin email for the shared core stack"
  type        = "String"
  value       = var.shared_core_gitea_admin_email
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "shared_core_gitea_org_name" {
  name        = "${local.shared_core_prefix}/gitea-org-name"
  description = "Gitea organisation name for the shared core stack"
  type        = "String"
  value       = var.shared_core_gitea_org_name
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

# ── Jenkins ECS Fargate agent pool parameters ─────────────────────────────────
# These are read by deploy-shared-core.yml and passed to docker-compose as
# JENKINS_AGENT_* environment variables so the JCasC ECS cloud block resolves.

resource "aws_ssm_parameter" "jenkins_agent_ecs_cluster_arn" {
  name        = "${local.shared_core_prefix}/agent/ecs-cluster-arn"
  description = "ARN of the ECS cluster used for Jenkins Fargate build agents"
  type        = "String"
  value       = var.jenkins_agent_ecs_cluster_arn
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "jenkins_agent_ecr_image" {
  name        = "${local.shared_core_prefix}/agent/ecr-agent-image"
  description = "ECR repository URL for the custom Jenkins inbound-agent image"
  type        = "String"
  value       = "${var.jenkins_agent_ecr_image}:latest"
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "jenkins_agent_ecs_security_group_id" {
  name        = "${local.shared_core_prefix}/agent/agent-security-group-id"
  description = "Security group ID for ECS Jenkins Fargate agent tasks"
  type        = "String"
  value       = var.jenkins_agent_ecs_security_group_id
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "jenkins_agent_task_execution_role_arn" {
  name        = "${local.shared_core_prefix}/agent/task-execution-role-arn"
  description = "ARN of the ECS task execution role for Jenkins agent tasks"
  type        = "String"
  value       = var.jenkins_agent_task_execution_role_arn
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_ssm_parameter" "jenkins_agent_task_role_arn" {
  name        = "${local.shared_core_prefix}/agent/task-role-arn"
  description = "ARN of the ECS task role (runtime permissions for Jenkins agent containers)"
  type        = "String"
  value       = var.jenkins_agent_task_role_arn
  tier        = "Standard"

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}
