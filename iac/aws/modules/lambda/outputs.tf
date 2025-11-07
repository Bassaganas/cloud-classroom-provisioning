output "user_management_function_arn" {
  description = "ARN of the user management Lambda function"
  value       = aws_lambda_function.user_management.arn
}

output "user_management_url" {
  description = "URL of the user management Lambda function"
  value       = aws_lambda_function_url.user_management_url.function_url
}

output "status_function_arn" {
  description = "ARN of the status Lambda function"
  value       = aws_lambda_function.status.arn
}

output "status_url" {
  description = "URL of the status Lambda function"
  value       = aws_lambda_function_url.status_url.function_url
}

output "stop_old_instances_function_arn" {
  description = "ARN of the stop old instances Lambda function"
  value       = aws_lambda_function.stop_old_instances.arn
}

output "instance_manager_function_arn" {
  description = "ARN of the instance manager Lambda function"
  value       = aws_lambda_function.instance_manager.arn
}

output "instance_manager_url" {
  description = "URL of the instance manager Lambda function"
  value       = aws_lambda_function_url.instance_manager_url.function_url
}

output "admin_cleanup_function_arn" {
  description = "ARN of the admin cleanup Lambda function"
  value       = aws_lambda_function.admin_cleanup.arn
}

output "dify_jira_api_function_arn" {
  description = "ARN of the dify jira API Lambda function"
  value       = aws_lambda_function.dify_jira_api.arn
}

output "dify_jira_api_url" {
  description = "URL of the dify jira API Lambda function"
  value       = aws_lambda_function_url.dify_jira_api_url.function_url
}




