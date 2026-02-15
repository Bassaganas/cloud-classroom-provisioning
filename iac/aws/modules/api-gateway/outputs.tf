# Data source for current region (needed for outputs)

output "api_gateway_id" {
  description = "ID of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.api.id
}

output "api_gateway_url" {
  description = "URL of the API Gateway REST API"
  value       = "${aws_api_gateway_rest_api.api.execution_arn}/restapis/${aws_api_gateway_rest_api.api.id}/${local.stage_name}"
}

output "api_gateway_invoke_url" {
  description = "Invoke URL of the API Gateway REST API"
  value       = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/${local.stage_name}"
}

output "api_gateway_arn" {
  description = "ARN of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.api.arn
}

output "api_gateway_execution_arn" {
  description = "Execution ARN of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.api.execution_arn
}

output "api_gateway_domain_name" {
  description = "Domain name of the API Gateway (for CloudFront origin)"
  value       = "${aws_api_gateway_rest_api.api.id}.execute-api.${data.aws_region.current.name}.amazonaws.com"
}

output "openapi_spec_url" {
  description = "URL to export OpenAPI spec from API Gateway"
  value       = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/${local.stage_name}/swagger.json"
}


output "api_gateway_custom_domain_name" {
  description = "Custom domain name for API Gateway (if configured)"
  value       = var.api_custom_domain_name != "" && var.wait_for_certificate_validation ? try(aws_api_gateway_domain_name.api_domain["create"].domain_name, null) : null
}

output "api_gateway_custom_domain_regional_domain_name" {
  description = "CloudFront domain name for API Gateway custom domain (Edge endpoint) - for CloudFront origin or Route53"
  value       = var.api_custom_domain_name != "" && var.wait_for_certificate_validation ? try(aws_api_gateway_domain_name.api_domain["create"].cloudfront_domain_name, null) : null
}

output "api_gateway_certificate_validation_records" {
  description = "DNS validation records for API Gateway custom domain certificate"
  value = var.api_custom_domain_name != "" ? {
    for dvo in aws_acm_certificate.api_domain_cert[0].domain_validation_options : dvo.domain_name => {
      domain_name           = dvo.domain_name
      resource_record_name  = dvo.resource_record_name
      resource_record_type  = dvo.resource_record_type
      resource_record_value = dvo.resource_record_value
    }
  } : {}
}
output "api_gateway_custom_domain_cloudfront_zone_id" {
  description = "CloudFront hosted zone ID for API Gateway custom domain (Edge endpoint) - for Route53 alias"
  value       = var.api_custom_domain_name != "" && var.wait_for_certificate_validation ? try(aws_api_gateway_domain_name.api_domain["create"].cloudfront_zone_id, null) : null
}

output "api_custom_domain_name" {
  description = "The API custom domain name variable (for use in other modules to avoid circular dependencies)"
  value       = var.api_custom_domain_name
}

output "wait_for_certificate_validation" {
  description = "Whether certificate validation is enabled (for use in other modules to avoid circular dependencies)"
  value       = var.wait_for_certificate_validation
}