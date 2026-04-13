output "s3_bucket_name" {
  description = "Name of the leadership S3 bucket"
  value       = aws_s3_bucket.leadership.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the leadership S3 bucket"
  value       = aws_s3_bucket.leadership.arn
}

output "oac_id" {
  description = "CloudFront Origin Access Control ID for leadership S3"
  value       = aws_cloudfront_origin_access_control.leadership.id
}

output "oac_arn" {
  description = "CloudFront Origin Access Control ARN for leadership S3"
  value       = aws_cloudfront_origin_access_control.leadership.arn
}
