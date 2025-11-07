output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = try(aws_cloudfront_distribution.distribution["create"].domain_name, null)
}

output "custom_url" {
  description = "Custom domain URL"
  value       = "https://${var.domain_name}"
}

output "certificate_validation_records" {
  description = "DNS validation records for ACM certificate"
  value       = aws_acm_certificate.cert.domain_validation_options
}

