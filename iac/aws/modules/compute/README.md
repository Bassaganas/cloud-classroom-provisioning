# Compute Module

This module manages EC2 instances, security groups, and EC2 IAM roles.

## Resources

- **EC2 Instances**: Emergency option for creating EC2 pool via Terraform (default: 0)
- **Security Group**: Allows SSH, HTTP, and HTTPS access
- **EC2 IAM Role**: SSM access for EC2 instances
- **IAM Instance Profile**: For EC2 instances to assume the SSM role

## Data Sources

- Default VPC
- Default Subnet
- Latest Amazon Linux 2 AMI

## Outputs

- Security group ID
- Subnet ID
- VPC ID
- EC2 IAM instance profile name
- Pool instance IDs and private IPs (if emergency pool created)




