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
