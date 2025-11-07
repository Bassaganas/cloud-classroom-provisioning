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

output "instance_manager_url" {
  description = "URL for the EC2 instance pool management Lambda (frontend at /ui)"
  value       = module.lambda.instance_manager_url
}

output "dify_jira_api_url" {
  description = "URL of the dify jira API Lambda function"
  value       = module.lambda.dify_jira_api_url
}

# CloudFront Outputs - Instance Manager
output "instance_manager_custom_url" {
  description = "Custom domain URL for EC2 instance manager (https://ec2-management.testingfantasy.com)"
  value       = module.cloudfront_instance_manager.custom_url
}

output "instance_manager_cloudfront_domain" {
  description = "CloudFront distribution domain name for instance manager (use this for DNS CNAME record in GoDaddy)"
  value       = module.cloudfront_instance_manager.cloudfront_domain
}

output "instance_manager_acm_certificate_validation_records" {
  description = "DNS validation records for instance manager ACM certificate (add these to GoDaddy DNS)"
  value       = module.cloudfront_instance_manager.certificate_validation_records
}

# CloudFront Outputs - User Management
output "user_management_custom_url" {
  description = "Custom domain URL for user management (https://testus-patronus.testingfantasy.com)"
  value       = module.cloudfront_user_management.custom_url
}

output "user_management_cloudfront_domain" {
  description = "CloudFront distribution domain name for user management (use this for DNS CNAME record in GoDaddy)"
  value       = module.cloudfront_user_management.cloudfront_domain
}

output "user_management_acm_certificate_validation_records" {
  description = "DNS validation records for user management ACM certificate (add these to GoDaddy DNS)"
  value       = module.cloudfront_user_management.certificate_validation_records
}

# CloudFront Outputs - Dify Jira API
output "dify_jira_custom_url" {
  description = "Custom domain URL for Dify Jira API (https://dify-jira.testingfantasy.com)"
  value       = module.cloudfront_dify_jira.custom_url
}

output "dify_jira_cloudfront_domain" {
  description = "CloudFront distribution domain name for Dify Jira API (use this for DNS CNAME record in GoDaddy)"
  value       = module.cloudfront_dify_jira.cloudfront_domain
}

output "dify_jira_acm_certificate_validation_records" {
  description = "DNS validation records for Dify Jira API ACM certificate (add these to GoDaddy DNS)"
  value       = module.cloudfront_dify_jira.certificate_validation_records
}

output "instance_manager_password_secret_name" {
  description = "Name of the Secrets Manager secret containing the instance manager password"
  value       = module.storage.instance_manager_password_secret_name
  sensitive   = true
}

# Compute Outputs
output "vpc_id" {
  description = "ID of the default VPC being used"
  value       = module.compute.vpc_id
}

output "subnet_id" {
  description = "ID of the default subnet being used"
  value       = module.compute.subnet_id
}

output "security_group_id" {
  description = "ID of the classroom security group"
  value       = module.compute.security_group_id
}

output "pool_instance_ids" {
  description = "IDs of the EC2 instances in the pool (emergency option only)"
  value       = module.compute.pool_instance_ids
}

output "pool_instance_private_ips" {
  description = "Private IPs of the EC2 instances in the pool (emergency option only)"
  value       = module.compute.pool_instance_private_ips
}
