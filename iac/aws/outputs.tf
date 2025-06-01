output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.user_management.arn
}

output "lambda_function_url" {
  description = "URL of the Lambda function"
  value       = aws_lambda_function_url.create_user_url.function_url
}

