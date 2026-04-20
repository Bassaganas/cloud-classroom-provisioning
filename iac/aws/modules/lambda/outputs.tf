output "user_management_function_arn" {
  description = "ARN of the user management Lambda function"
  value       = try(aws_lambda_function.user_management[0].arn, null)
}

output "user_management_url" {
  description = "URL of the user management Lambda function"
  value       = try(aws_lambda_function_url.user_management_url[0].function_url, null)
}

output "status_function_arn" {
  description = "ARN of the status Lambda function"
  value       = try(aws_lambda_function.status[0].arn, null)
}

output "status_url" {
  description = "URL of the status Lambda function"
  value       = try(aws_lambda_function_url.status_url[0].function_url, null)
}

output "stop_old_instances_function_arn" {
  description = "ARN of the stop old instances Lambda function"
  value       = try(aws_lambda_function.stop_old_instances[0].arn, null)
}

output "instance_manager_function_arn" {
  description = "ARN of the instance manager Lambda function"
  value       = try(aws_lambda_function.instance_manager[0].arn, null)
}

output "instance_manager_url" {
  description = "URL of the instance manager Lambda function"
  value       = try(aws_lambda_function_url.instance_manager_url[0].function_url, null)
}

output "admin_cleanup_function_arn" {
  description = "ARN of the admin cleanup Lambda function"
  value       = try(aws_lambda_function.admin_cleanup[0].arn, null)
}

output "dify_jira_api_function_arn" {
  description = "ARN of the dify jira API Lambda function"
  value       = try(aws_lambda_function.dify_jira_api[0].arn, null)
}

output "dify_jira_api_url" {
  description = "URL of the dify jira API Lambda function"
  value       = try(aws_lambda_function_url.dify_jira_api_url[0].function_url, null)
}

output "fellowship_student_assignment_function_arn" {
  description = "ARN of the fellowship student assignment Lambda function"
  value       = try(aws_lambda_function.fellowship_student_assignment[0].arn, null)
}

output "fellowship_student_assignment_url" {
  description = "URL of the fellowship student assignment Lambda function"
  value       = try(aws_lambda_function_url.fellowship_student_assignment_url[0].function_url, null)
}




