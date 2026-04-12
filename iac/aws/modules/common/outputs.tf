# Outputs for shared/common infrastructure.

output "instance_manager_url" {
  description = "URL for the EC2 instance manager Lambda (frontend at /ui)"
  value       = module.lambda.instance_manager_url
}

output "instance_manager_custom_url" {
  description = "Custom domain URL for EC2 instance manager"
  value       = module.cloudfront_instance_manager.custom_url
}

output "instance_manager_cloudfront_domain" {
  description = "CloudFront distribution domain name for instance manager"
  value       = module.cloudfront_instance_manager.cloudfront_domain
}

output "instance_manager_cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidation"
  value       = try(module.cloudfront_instance_manager.cloudfront_distribution_id, null)
}

output "instance_manager_acm_certificate_validation_records" {
  description = "DNS validation records for instance manager ACM certificate"
  value       = module.cloudfront_instance_manager.certificate_validation_records
}

output "instance_manager_https_certificate_arn" {
  description = "ARN of the wildcard ACM certificate for per-instance HTTPS (ALB)"
  value       = aws_acm_certificate.instance_https.arn
}

output "instance_manager_https_certificate_validation_records" {
  description = "DNS validation records for the wildcard HTTPS certificate"
  value       = aws_acm_certificate.instance_https.domain_validation_options
}

output "instance_manager_password_secret_name" {
  description = "Name of the Secrets Manager secret containing the instance manager password"
  value       = module.storage.instance_manager_password_secret_name
  sensitive   = true
}

output "instance_manager_password_secret_arn" {
  description = "ARN of the Secrets Manager secret containing the instance manager password"
  value       = module.storage.instance_manager_password_secret_arn
  sensitive   = true
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for instance assignments"
  value       = module.storage.dynamodb_table_name
}

output "subnet_id" {
  description = "ID of the default subnet being used"
  value       = module.compute.subnet_id
}

output "vpc_id" {
  description = "ID of the default VPC"
  value       = module.compute.vpc_id
}

output "security_group_id" {
  description = "ID of the classroom security group"
  value       = module.compute.security_group_id
}

output "shared_core_security_group_id" {
  description = "ID of the shared-core Jenkins and Gitea security group"
  value       = module.compute.shared_core_security_group_id
}

output "ec2_iam_instance_profile_name" {
  description = "Name of the EC2 IAM instance profile"
  value       = module.compute.ec2_iam_instance_profile_name
}

output "ec2_iam_role_arn" {
  description = "ARN of the EC2 IAM role"
  value       = module.compute.ec2_iam_role_arn
}

output "ec2_iam_role_name" {
  description = "Name of the EC2 IAM role (used to attach additional policies)"
  value       = module.compute.ec2_iam_role_name
}

output "s3_frontend_bucket_name" {
  description = "Name of the S3 bucket for frontend"
  value       = module.s3_frontend.bucket_name
}

output "instance_manager_api_gateway_url" {
  description = "API Gateway invoke URL for EC2 instance manager"
  value       = module.api_gateway.api_gateway_invoke_url
}

output "instance_manager_openapi_spec_url" {
  description = "URL to export OpenAPI spec from API Gateway"
  value       = module.api_gateway.openapi_spec_url
}

