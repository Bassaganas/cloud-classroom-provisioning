output "ec2_iam_role_arn" {
  description = "ARN of the EC2 SSM IAM role"
  value       = aws_iam_role.ec2_ssm_role.arn
}

output "ec2_iam_role_name" {
  description = "Name of the EC2 SSM IAM role (used to attach additional policies)"
  value       = aws_iam_role.ec2_ssm_role.name
}

output "ec2_iam_instance_profile_name" {
  description = "Name of the EC2 IAM instance profile"
  value       = aws_iam_instance_profile.ec2_ssm_profile.name
}

output "security_group_id" {
  description = "ID of the classroom security group"
  value       = aws_security_group.classroom_sg.id
}

output "shared_core_security_group_id" {
  description = "ID of the shared-core (Jenkins + Gitea) security group"
  value       = aws_security_group.shared_core_sg.id
}

output "vpc_id" {
  description = "ID of the default VPC being used"
  value       = data.aws_vpc.default.id
}

output "subnet_id" {
  description = "ID of the default subnet being used"
  value       = var.ec2_subnet_id != "" ? var.ec2_subnet_id : data.aws_subnet.default.id
}

output "pool_instance_ids" {
  description = "IDs of the EC2 instances in the pool (emergency option only)"
  value       = var.ec2_pool_size > 0 ? aws_instance.classroom_pool[*].id : []
}

output "pool_instance_private_ips" {
  description = "Private IPs of the EC2 instances in the pool (emergency option only)"
  value       = var.ec2_pool_size > 0 ? aws_instance.classroom_pool[*].private_ip : []
}




