# Lambda Outputs
output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.lambda.user_management_function_arn
}

output "lambda_function_url" {
  description = "URL of the Lambda function"
  value       = module.lambda.user_management_url
}

output "status_lambda_url" {
  description = "URL of the status Lambda function"
  value       = module.lambda.status_url
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for instance assignments"
  value       = module.storage.dynamodb_table_name
}

output "instance_manager_url" {
  description = "URL for the EC2 instance pool management Lambda (frontend at /ui)"
  value       = try(data.terraform_remote_state.common.outputs.instance_manager_url, null)
}

output "dify_jira_api_url" {
  description = "URL of the dify jira API Lambda function"
  value       = module.lambda.dify_jira_api_url
}

# CloudFront Outputs - Instance Manager
output "instance_manager_custom_url" {
  description = "Custom domain URL for EC2 instance manager (https://ec2-management.testingfantasy.com)"
  value       = try(data.terraform_remote_state.common.outputs.instance_manager_custom_url, null)
}

output "instance_manager_cloudfront_domain" {
  description = "CloudFront distribution domain name for instance manager (use this for DNS CNAME record in Route 53)"
  value       = try(data.terraform_remote_state.common.outputs.instance_manager_cloudfront_domain, null)
}

output "instance_manager_acm_certificate_validation_records" {
  description = "DNS validation records for instance manager ACM certificate (add these to Route 53)"
  value       = try(data.terraform_remote_state.common.outputs.instance_manager_acm_certificate_validation_records, null)
}

# CloudFront Outputs - User Management
output "user_management_custom_url" {
  description = "Custom domain URL for user management (https://testus-patronus.testingfantasy.com)"
  value       = module.cloudfront_user_management.custom_url
}

output "user_management_cloudfront_domain" {
  description = "CloudFront distribution domain name for user management (use this for DNS CNAME record in Route 53)"
  value       = module.cloudfront_user_management.cloudfront_domain
}

output "user_management_acm_certificate_validation_records" {
  description = "DNS validation records for user management ACM certificate (add these to Route 53)"
  value       = module.cloudfront_user_management.certificate_validation_records
}

# CloudFront Outputs - Dify Jira API
output "dify_jira_custom_url" {
  description = "Custom domain URL for Dify Jira API (https://dify-jira.testingfantasy.com)"
  value       = module.cloudfront_dify_jira.custom_url
}

output "dify_jira_cloudfront_domain" {
  description = "CloudFront distribution domain name for Dify Jira API (use this for DNS CNAME record in Route 53)"
  value       = module.cloudfront_dify_jira.cloudfront_domain
}

output "dify_jira_acm_certificate_validation_records" {
  description = "DNS validation records for Dify Jira API ACM certificate (add these to Route 53)"
  value       = module.cloudfront_dify_jira.certificate_validation_records
}

output "instance_manager_password_secret_name" {
  description = "Name of the Secrets Manager secret containing the instance manager password"
  value       = try(data.terraform_remote_state.common.outputs.instance_manager_password_secret_name, null)
  sensitive   = true
}


# Static Website Outputs - Root Domain
# DISABLED: The testing_fantasy application is now deployed with AWS Amplify
# 
# Important: You do NOT need the Terraform-managed certificate validation records
# because Amplify automatically creates and manages its own ACM certificate.
# 
# When you add a custom domain in Amplify Console:
# 1. Amplify creates its own ACM certificate automatically
# 2. Amplify provides its own certificate validation records (if needed)
# 3. Amplify manages the SSL/TLS configuration
# 
# The certificate validation records shown in terraform plan/apply output
# (for testingfantasy.com and www.testingfantasy.com) are NOT needed and can be ignored.
#
# output "static_website_s3_bucket" {
#   description = "S3 bucket name for the static website"
#   value       = module.static_website.s3_bucket_name
# }
#
# output "static_website_cloudfront_domain" {
#   description = "CloudFront distribution domain name for root domain (use this for Route 53 A record)"
#   value       = module.static_website.cloudfront_domain
# }
#
# output "static_website_cloudfront_distribution_id" {
#   description = "CloudFront distribution ID for cache invalidation"
#   value       = module.static_website.cloudfront_distribution_id
# }
#
# output "static_website_custom_url" {
#   description = "Custom domain URL for root domain (https://testingfantasy.com)"
#   value       = module.static_website.custom_url
# }
#
# output "static_website_acm_certificate_validation_records" {
#   description = "DNS validation records for root domain ACM certificate (add these to Route 53)"
#   value       = module.static_website.certificate_validation_records
# }
