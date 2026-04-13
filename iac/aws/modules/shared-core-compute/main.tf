data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_route53_zone" "shared_core" {
  count        = var.shared_core_manage_route53_records && (trimspace(var.shared_core_jenkins_domain) != "" || trimspace(var.shared_core_gitea_domain) != "") ? 1 : 0
  name         = "${var.base_domain}."
  private_zone = false
}

locals {
  shared_core_security_group_id = trimspace(var.shared_core_security_group_id) != "" ? var.shared_core_security_group_id : var.common_shared_core_security_group_id
  shared_core_ssh_host          = trimspace(var.shared_core_ssh_host) != "" ? var.shared_core_ssh_host : trimspace(var.shared_core_jenkins_domain) != "" ? var.shared_core_jenkins_domain : coalesce(aws_instance.shared_core_host.public_dns, aws_instance.shared_core_host.public_ip)
}

resource "aws_instance" "shared_core_host" {
  ami                         = var.shared_core_ami_id != "" ? var.shared_core_ami_id : data.aws_ami.amazon_linux_2.id
  instance_type               = var.shared_core_instance_type
  key_name                    = var.shared_core_key_name != "" ? var.shared_core_key_name : null
  subnet_id                   = var.shared_core_subnet_id != "" ? var.shared_core_subnet_id : var.common_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = [local.shared_core_security_group_id]
  iam_instance_profile        = var.common_ec2_iam_instance_profile_name
  user_data_base64 = base64encode(templatefile("${path.module}/templates/install-scripts.sh.tpl", {})) # Prevent instance replacement when scripts are updated — deploy script changes via SSH/SSM instead
  user_data_replace_on_change = false
  root_block_device {
    volume_size           = 80
    volume_type           = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
  }

  tags = {
    Name        = "shared-core-${var.shared_core_environment}"
    Environment = var.shared_core_environment
    Owner       = var.owner
    Project     = "classroom"
    Type        = "shared-core"
    Company     = "TestingFantasy"
  }
}

resource "aws_route53_record" "shared_core_jenkins" {
  count = var.shared_core_manage_route53_records && trimspace(var.shared_core_jenkins_domain) != "" ? 1 : 0

  zone_id         = data.aws_route53_zone.shared_core[0].zone_id
  name            = var.shared_core_jenkins_domain
  type            = "A"
  ttl             = 60
  records         = [aws_instance.shared_core_host.public_ip]
  allow_overwrite = true
}

resource "aws_route53_record" "shared_core_gitea" {
  count = var.shared_core_manage_route53_records && trimspace(var.shared_core_gitea_domain) != "" ? 1 : 0

  zone_id         = data.aws_route53_zone.shared_core[0].zone_id
  name            = var.shared_core_gitea_domain
  type            = "A"
  ttl             = 60
  records         = [aws_instance.shared_core_host.public_ip]
  allow_overwrite = true
}
