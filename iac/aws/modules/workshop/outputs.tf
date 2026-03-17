# Lambda Outputs
output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.lambda.user_management_function_arn
}

# Workshop Template Output (used by EC2 instance manager)
# Note: user_data_base64 should be passed from root module since file() can't be used in modules
output "template_config" {
  description = "Template configuration for EC2 instance manager (AMI, instance type)"
  value = {
    workshop_name = var.workshop_name
    ami_id        = var.ec2_ami_id != "" ? var.ec2_ami_id : data.aws_ami.amazon_linux_2.id
    instance_type = var.ec2_instance_type
    app_port      = 8080
  }
}

output "lambda_function_url" {
  description = "URL of the Lambda function"
  value       = module.lambda.user_management_url
}

output "status_lambda_url" {
  description = "URL of the status Lambda function"
  value       = module.lambda.status_url
}

output "dify_jira_api_url" {
  description = "URL of the dify jira API Lambda function"
  value       = module.lambda.dify_jira_api_url
}

# CloudFront Outputs - User Management
output "user_management_custom_url" {
  description = "Custom domain URL for user management"
  value       = module.cloudfront_user_management.custom_url
}

output "user_management_cloudfront_domain" {
  description = "CloudFront distribution domain name for user management"
  value       = module.cloudfront_user_management.cloudfront_domain
}

output "user_management_acm_certificate_validation_records" {
  description = "DNS validation records for user management ACM certificate"
  value       = module.cloudfront_user_management.certificate_validation_records
}

# CloudFront Outputs - Dify Jira API
output "dify_jira_custom_url" {
  description = "Custom domain URL for Dify Jira API"
  value       = module.cloudfront_dify_jira.custom_url
}

output "dify_jira_cloudfront_domain" {
  description = "CloudFront distribution domain name for Dify Jira API"
  value       = module.cloudfront_dify_jira.cloudfront_domain
}

output "dify_jira_acm_certificate_validation_records" {
  description = "DNS validation records for Dify Jira API ACM certificate"
  value       = module.cloudfront_dify_jira.certificate_validation_records
}

output "sut_bucket_name" {
  description = "Name of the S3 bucket for workshop setup scripts (fellowship SUT or testus_patronus setup script)"
  value       = (var.workshop_name == "fellowship" || var.workshop_name == "fellowship-of-the-build" || var.workshop_name == "testus_patronus") ? module.s3_sut[0].bucket_name : ""
}
