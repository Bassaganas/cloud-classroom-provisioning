output "provisioning_queue_url" {
  description = "URL of the SQS provisioning queue (used by instance-manager Lambda env var)"
  value       = aws_sqs_queue.provisioning.url
}

output "provisioning_queue_arn" {
  description = "ARN of the SQS provisioning queue"
  value       = aws_sqs_queue.provisioning.arn
}

output "provisioning_dlq_arn" {
  description = "ARN of the SQS provisioning dead-letter queue"
  value       = aws_sqs_queue.provisioning_dlq.arn
}

output "provisioning_status_table_name" {
  description = "Name of the DynamoDB table tracking provisioning request status"
  value       = aws_dynamodb_table.provisioning_status.name
}

output "provisioner_lambda_function_name" {
  description = "Name of the shared-core provisioner Lambda function"
  value       = aws_lambda_function.provisioner.function_name
}

output "ssm_queue_url_param" {
  description = "SSM parameter name storing the provisioning queue URL"
  value       = aws_ssm_parameter.provisioning_queue_url.name
}
