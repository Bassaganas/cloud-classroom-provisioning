output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = try(aws_cloudfront_distribution.distribution["create"].domain_name, null)
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = try(aws_cloudfront_distribution.distribution["create"].id, null)
}

output "custom_url" {
  description = "Custom domain URL"
  value       = "https://${var.domain_name}"
}

output "certificate_validation_records" {
  description = "DNS validation records for ACM certificate"
  value       = aws_acm_certificate.cert.domain_validation_options
}

output "route53_zone_id" {
  description = "Route53 hosted zone ID"
  value       = try(data.aws_route53_zone.domain[0].zone_id, null)
}

output "cloudwatch_log_group_name" {
  description = "CloudWatch Log Group name for CloudFront logs"
  value       = var.enable_cloudwatch_logging ? aws_cloudwatch_log_group.cloudfront_logs[0].name : null
}

output "cloudfront_distribution_arn" {
  description = "CloudFront distribution ARN (used for OAC S3 bucket policies)"
  value       = try(aws_cloudfront_distribution.distribution["create"].arn, null)
}

output "cloudwatch_log_group_arn" {
  description = "CloudWatch Log Group ARN for CloudFront logs"
  value       = var.enable_cloudwatch_logging ? aws_cloudwatch_log_group.cloudfront_logs[0].arn : null
}

output "kinesis_stream_name" {
  description = "Kinesis stream name for CloudFront real-time logs"
  value       = var.enable_cloudwatch_logging ? aws_kinesis_stream.cloudfront_logs[0].name : null
}

output "kinesis_stream_arn" {
  description = "Kinesis stream ARN for CloudFront real-time logs"
  value       = var.enable_cloudwatch_logging ? aws_kinesis_stream.cloudfront_logs[0].arn : null
}
