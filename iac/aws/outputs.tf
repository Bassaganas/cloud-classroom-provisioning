# Route 53 alias record output — managed by the docs_cloudfront module
output "docs_route53_record_fqdn" {
  value       = try(module.docs_cloudfront.cloudfront_domain, null)
  description = "CloudFront domain serving docs.fellowship.testingfantasy.com"
}
# Docusaurus Docs CloudFront Outputs
output "docs_cloudfront_distribution_id" {
  value       = module.docs_cloudfront.cloudfront_distribution_id
  description = "CloudFront distribution ID for Docusaurus docs"
}

output "docs_cloudfront_domain_name" {
  value       = module.docs_cloudfront.cloudfront_domain
  description = "CloudFront domain name for Docusaurus docs"
}
output "tutorial_always_on_links_parameter_arn" {
  description = "ARN of the always-on tutorial links SSM parameter"
  value       = aws_ssm_parameter.tutorial_always_on_links.arn
}

output "tutorial_always_on_links_parameter_name" {
  description = "Name of the always-on tutorial links SSM parameter"
  value       = aws_ssm_parameter.tutorial_always_on_links.name
}

output "shared_core_github_actions_role_arn" {
  description = "IAM role ARN for the shared-core GitHub Actions deploy workflow"
  value       = module.shared_core_iam.github_actions_role_arn
}

output "shared_core_deploy_secret_name" {
  description = "Secrets Manager secret name for shared-core deploy credentials"
  value       = module.shared_core_secrets.deploy_secret_name
}

output "shared_core_config_parameter_names" {
  description = "SSM parameter names used by the shared-core deploy workflow"
  value       = module.shared_core_config.config_parameter_names
}

# Aggregate outputs from all modules

# Common infrastructure outputs
output "instance_manager_url" {
  description = "URL for the EC2 instance manager Lambda (frontend at /ui)"
  value       = module.common.instance_manager_url
}

output "instance_manager_custom_url" {
  description = "Custom domain URL for EC2 instance manager"
  value       = module.common.instance_manager_custom_url
}

output "instance_manager_cloudfront_domain" {
  description = "CloudFront distribution domain name for instance manager"
  value       = module.common.instance_manager_cloudfront_domain
}

output "instance_manager_cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidation"
  value       = module.common.instance_manager_cloudfront_distribution_id
}

output "security_group_id" {
  description = "ID of the classroom security group"
  value       = module.common.security_group_id
}

output "shared_core_security_group_id" {
  description = "ID of the shared-core Jenkins and Gitea security group"
  value       = module.shared_core_compute.security_group_id
}

output "shared_core_instance_id" {
  description = "EC2 instance ID of the Terraform-managed shared-core host"
  value       = module.shared_core_compute.instance_id
}

output "shared_core_ssh_host" {
  description = "SSH host used by the shared-core deployment workflow"
  value       = module.shared_core_compute.ssh_host
}

output "subnet_id" {
  description = "ID of the default subnet being used"
  value       = module.common.subnet_id
}

# Fellowship workshop outputs
output "fellowship_lambda_function_url" {
  description = "URL of the fellowship Lambda function"
  value       = module.workshop_fellowship.lambda_function_url
}

output "fellowship_user_management_custom_url" {
  description = "Custom domain URL for fellowship user management"
  value       = module.workshop_fellowship.user_management_custom_url
}

output "fellowship_dify_jira_custom_url" {
  description = "Custom domain URL for fellowship Dify Jira API"
  value       = module.workshop_fellowship.dify_jira_custom_url
}

output "fellowship_leaderboard_api_custom_url" {
  description = "Custom domain URL for fellowship leaderboard API"
  value       = module.workshop_fellowship.leaderboard_api_custom_domain
}

# Fellowship messaging outputs
output "fellowship_sqs_queue_url" {
  description = "SQS queue URL for fellowship student progress events"
  value       = module.workshop_fellowship.sqs_queue_url
}

output "fellowship_sqs_ssm_param" {
  description = "SSM Parameter name storing the fellowship SQS queue URL"
  value       = module.workshop_fellowship.sqs_ssm_queue_url_param_name
}

# Testus Patronus messaging outputs
output "testus_patronus_sqs_queue_url" {
  description = "SQS queue URL for testus_patronus student progress events"
  value       = module.workshop_testus_patronus.sqs_queue_url
}

output "testus_patronus_sqs_ssm_param" {
  description = "SSM Parameter name storing the testus_patronus SQS queue URL"
  value       = module.workshop_testus_patronus.sqs_ssm_queue_url_param_name
}

# Testus Patronus workshop outputs
output "testus_patronus_lambda_function_url" {
  description = "URL of the testus_patronus Lambda function"
  value       = module.workshop_testus_patronus.lambda_function_url
}

output "testus_patronus_user_management_custom_url" {
  description = "Custom domain URL for testus_patronus user management"
  value       = module.workshop_testus_patronus.user_management_custom_url
}

output "testus_patronus_dify_jira_custom_url" {
  description = "Custom domain URL for testus_patronus Dify Jira API"
  value       = module.workshop_testus_patronus.dify_jira_custom_url
}

output "testus_patronus_leaderboard_api_custom_url" {
  description = "Custom domain URL for testus_patronus leaderboard API"
  value       = module.workshop_testus_patronus.leaderboard_api_custom_domain
}

output "instance_manager_s3_bucket_name" {
  description = "Name of the S3 bucket for frontend (alias for compatibility)"
  value       = module.common.s3_frontend_bucket_name
}

# Template configs for SSM publishing (includes user_data_base64)
output "workshop_fellowship_template_config" {
  description = "Template configuration for fellowship workshop (for SSM)"
  value = {
    workshop_name    = module.workshop_fellowship.template_config.workshop_name
    ami_id           = module.workshop_fellowship.template_config.ami_id
    instance_type    = module.workshop_fellowship.template_config.instance_type
    app_port         = module.workshop_fellowship.template_config.app_port
    user_data_base64 = base64encode(file("${path.module}/workshops/fellowship/user_data.sh"))
  }
}

output "sut_bucket_name" {
  description = "Name of the S3 bucket for Fellowship SUT (only for fellowship workshop)"
  value       = module.workshop_fellowship.sut_bucket_name
}

output "testus_patronus_sut_bucket_name" {
  description = "Name of the S3 bucket for Testus Patronus setup script"
  value       = module.workshop_testus_patronus.sut_bucket_name
}

output "workshop_testus_patronus_template_config" {
  description = "Template configuration for testus_patronus workshop (for SSM)"
  value = {
    workshop_name    = module.workshop_testus_patronus.template_config.workshop_name
    ami_id           = module.workshop_testus_patronus.template_config.ami_id
    instance_type    = module.workshop_testus_patronus.template_config.instance_type
    app_port         = module.workshop_testus_patronus.template_config.app_port
    user_data_base64 = base64encode(file("${path.module}/workshops/testus_patronus/user_data.sh"))
  }
}

output "instance_manager_api_gateway_url" {
  description = "API Gateway invoke URL for EC2 instance manager"
  value       = module.common.instance_manager_api_gateway_url
}

output "instance_manager_openapi_spec_url" {
  description = "URL to export OpenAPI spec from API Gateway"
  value       = module.common.instance_manager_openapi_spec_url
}

output "fellowship_leaderboard_api_gateway_url" {
  description = "API Gateway invoke URL for the fellowship leaderboard API"
  value       = module.workshop_fellowship.leaderboard_api_gateway_url
}

output "fellowship_leaderboard_openapi_spec_url" {
  description = "OpenAPI spec URL for the fellowship leaderboard API"
  value       = module.workshop_fellowship.leaderboard_openapi_spec_url
}

output "testus_patronus_leaderboard_api_gateway_url" {
  description = "API Gateway invoke URL for the testus_patronus leaderboard API"
  value       = module.workshop_testus_patronus.leaderboard_api_gateway_url
}

output "testus_patronus_leaderboard_openapi_spec_url" {
  description = "OpenAPI spec URL for the testus_patronus leaderboard API"
  value       = module.workshop_testus_patronus.leaderboard_openapi_spec_url
}
