locals {
  shared_core_prefix      = "/classroom/shared-core/${var.shared_core_environment}"
  shared_core_secret_name = "${local.shared_core_prefix}/deploy"
  shared_core_secret_values = {
    ssh_private_key        = var.shared_core_ssh_private_key
    gh_repo_token          = var.shared_core_gh_repo_token
    jenkins_admin_password = var.shared_core_jenkins_admin_password
    gitea_admin_password   = var.shared_core_gitea_admin_password
  }
  shared_core_secret_ready = alltrue([
    for value in values(local.shared_core_secret_values) : trimspace(value) != ""
  ])
}

resource "aws_secretsmanager_secret" "shared_core_deploy" {
  name                    = local.shared_core_secret_name
  description             = "Shared core deployment secret bundle for GitHub Actions"
  recovery_window_in_days = 0

  tags = {
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_secretsmanager_secret_version" "shared_core_deploy" {
  count = local.shared_core_secret_ready ? 1 : 0

  secret_id = aws_secretsmanager_secret.shared_core_deploy.id
  secret_string = jsonencode({
    ssh_private_key        = var.shared_core_ssh_private_key
    gh_repo_token          = var.shared_core_gh_repo_token
    jenkins_admin_password = var.shared_core_jenkins_admin_password
    gitea_admin_password   = var.shared_core_gitea_admin_password
  })
}
