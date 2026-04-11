output "deploy_secret_name" {
  description = "Secrets Manager secret name for shared-core deploy credentials"
  value       = aws_secretsmanager_secret.shared_core_deploy.name
}

output "deploy_secret_arn" {
  description = "Secrets Manager secret ARN for shared-core deploy credentials"
  value       = aws_secretsmanager_secret.shared_core_deploy.arn
}
