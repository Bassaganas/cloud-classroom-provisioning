output "s3_bucket_name" {
  description = "Name of the S3 bucket for the static website"
  value       = aws_s3_bucket.website.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.website.arn
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.website.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.website.id
}

output "custom_url" {
  description = "Custom domain URL"
  value       = "https://${var.domain_name}"
}

output "certificate_validation_records" {
  description = "DNS validation records for ACM certificate"
  value = [
    for record in aws_acm_certificate.cert.domain_validation_options : {
      domain_name           = record.domain_name
      resource_record_name  = record.resource_record_name
      resource_record_type  = record.resource_record_type
      resource_record_value = record.resource_record_value
    }
  ]
}

output "certificate_arn" {
  description = "ARN of the ACM certificate"
  value       = aws_acm_certificate.cert.arn
}

