output "instance_id" {
  description = "EC2 instance ID of the Terraform-managed shared-core host"
  value       = aws_instance.shared_core_host.id
}

output "public_ip" {
  description = "Current public IP of the shared-core host"
  value       = aws_instance.shared_core_host.public_ip
}

output "public_dns" {
  description = "Current public DNS of the shared-core host"
  value       = aws_instance.shared_core_host.public_dns
}

output "ssh_host" {
  description = "SSH host used by the shared-core deployment workflow"
  value       = local.shared_core_ssh_host
}

output "security_group_id" {
  description = "Security group ID used by the shared-core host"
  value       = local.shared_core_security_group_id
}

output "hosted_zone_id" {
  description = "Route53 hosted zone ID for shared-core domains"
  value       = try(data.aws_route53_zone.shared_core[0].zone_id, null)
}
