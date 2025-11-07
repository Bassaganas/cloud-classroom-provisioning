output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for instance assignments"
  value       = aws_dynamodb_table.instance_assignments.name
}

output "instance_manager_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for instance manager password"
  value       = aws_secretsmanager_secret.instance_manager_password.arn
}

output "instance_manager_password_secret_name" {
  description = "Name of the Secrets Manager secret for instance manager password"
  value       = aws_secretsmanager_secret.instance_manager_password.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for instance assignments"
  value       = aws_dynamodb_table.instance_assignments.arn
}

