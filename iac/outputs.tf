
output "lambda_function_arn" {
  description = "ARN of the Lambda function (AWS only)"
  value       = try(module.aws_infrastructure[0].lambda_function_arn, null)
}

output "lambda_function_url" {
  description = "URL of the Lambda function (AWS only)"
  value       = try(module.aws_infrastructure[0].lambda_function_url, null)
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket (AWS only)"
  value       = try(module.aws_infrastructure[0].s3_bucket_arn, null)
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket (AWS only)"
  value       = try(module.aws_infrastructure[0].s3_bucket_name, null)
}

output "function_app_id" {
  description = "ID of the Function App (Azure only)"
  value       = try(module.azure_infrastructure[0].function_app_id, null)
}

output "function_app_url" {
  description = "URL of the Function App (Azure only)"
  value       = try(module.azure_infrastructure[0].function_app_url, null)
}

output "storage_account_id" {
  description = "ID of the Storage Account (Azure only)"
  value       = try(module.azure_infrastructure[0].storage_account_id, null)
}

output "key_vault_id" {
  description = "ID of the Key Vault (Azure only)"
  value       = try(module.azure_infrastructure[0].key_vault_id, null)
}
