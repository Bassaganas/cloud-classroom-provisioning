output "bucket_name" {
  description = "Name of the S3 bucket for Fellowship SUT"
  value       = aws_s3_bucket.sut.id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket for Fellowship SUT"
  value       = aws_s3_bucket.sut.arn
}

output "bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = aws_s3_bucket.sut.bucket_regional_domain_name
}
