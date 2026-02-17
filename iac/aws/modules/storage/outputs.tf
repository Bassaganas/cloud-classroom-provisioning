output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for instance assignments"
  value       = aws_dynamodb_table.instance_assignments.name
}

output "instance_manager_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for instance manager password"
  value       = var.create_instance_manager_password_secret ? aws_secretsmanager_secret.instance_manager_password[0].arn : null
}

output "instance_manager_password_secret_name" {
  description = "Name of the Secrets Manager secret for instance manager password"
  value       = var.create_instance_manager_password_secret ? aws_secretsmanager_secret.instance_manager_password[0].name : null
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for instance assignments"
  value       = aws_dynamodb_table.instance_assignments.arn
}

output "tutorial_sessions_table_name" {
  description = "Name of the DynamoDB table for tutorial sessions"
  value       = aws_dynamodb_table.tutorial_sessions.name
}

output "tutorial_sessions_table_arn" {
  description = "ARN of the DynamoDB table for tutorial sessions"
  value       = aws_dynamodb_table.tutorial_sessions.arn
}

