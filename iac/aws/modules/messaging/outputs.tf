output "queue_url" {
  description = "URL of the SQS student-progress queue"
  value       = aws_sqs_queue.student_progress.url
}

output "queue_arn" {
  description = "ARN of the SQS student-progress queue"
  value       = aws_sqs_queue.student_progress.arn
}

output "dlq_arn" {
  description = "ARN of the SQS dead-letter queue"
  value       = aws_sqs_queue.student_progress_dlq.arn
}

output "producer_policy_arn" {
  description = "ARN of the IAM policy granting SendMessage to EC2 producers"
  value       = aws_iam_policy.sqs_producer.arn
}

output "ssm_queue_url_param_name" {
  description = "SSM Parameter Store key where the queue URL is stored (for EC2 user-data lookup)"
  value       = aws_ssm_parameter.student_progress_queue_url.name
}

output "leaderboard_table_name" {
  description = "DynamoDB table name for leaderboard data"
  value       = aws_dynamodb_table.leaderboard.name
}

output "leaderboard_table_arn" {
  description = "DynamoDB table ARN for leaderboard data"
  value       = aws_dynamodb_table.leaderboard.arn
}

output "lambda_consumer_arn" {
  description = "ARN of the leaderboard consumer Lambda function"
  value       = aws_lambda_function.leaderboard_consumer.arn
}

output "lambda_consumer_name" {
  description = "Name of the leaderboard consumer Lambda function"
  value       = aws_lambda_function.leaderboard_consumer.function_name
}
