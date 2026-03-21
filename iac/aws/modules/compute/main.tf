# Data source for latest Amazon Linux 2 AMI
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

# Locals for normalized naming
locals {
  # Normalize tutorial names: testus_patronus -> testus-patronus, fellowship-of-the-build -> fellowship, shared -> common
  normalized_tutorial_name = replace(
    replace(
      replace(var.workshop_name, "testus_patronus", "testus-patronus"),
      "fellowship-of-the-build",
      "fellowship"
    ),
    "shared",
    "common"
  )
  # Convert region to region code (eu-west-1 -> euwest1)
  region_code = replace(var.region, "-", "")
}

# IAM Role for EC2 instances
resource "aws_iam_role" "ec2_ssm_role" {
  name = "iam-ec2-ssm-role-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Attach SSM policy to EC2 role
resource "aws_iam_role_policy_attachment" "ssm_policy" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# IAM policy for S3 access to Fellowship SUT bucket
resource "aws_iam_role_policy" "ec2_sut_access" {
  count = var.sut_bucket_arn != "" ? 1 : 0
  name  = "ec2-sut-s3-access-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role  = aws_iam_role.ec2_ssm_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "${var.sut_bucket_arn}/*"
    }]
  })
}

# IAM policy for Secrets Manager access to Azure OpenAI credentials
resource "aws_iam_role_policy" "ec2_secrets_access" {
  name = "ec2-secrets-access-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role = aws_iam_role.ec2_ssm_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        "arn:aws:secretsmanager:*:*:secret:classroom/shared/${var.environment}/*",
        "arn:aws:secretsmanager:*:*:secret:classroom/${var.workshop_name}/${var.environment}/*"
      ]
    }]
  })
}

# Create instance profile
resource "aws_iam_instance_profile" "ec2_ssm_profile" {
  name = "iam-ec2-ssm-profile-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role = aws_iam_role.ec2_ssm_role.name
}

# Data source for default VPC
data "aws_vpc" "default" {
  default = true
}

# Data source for available AZs
data "aws_availability_zones" "available" {
  state = "available"
}

# Data source for default subnet
data "aws_subnet" "default" {
  vpc_id            = data.aws_vpc.default.id
  availability_zone = data.aws_availability_zones.available.names[0]
}

# Security Group for Classroom EC2 Instances
resource "aws_security_group" "classroom_sg" {
  name_prefix = "classroom-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}-"
  vpc_id      = data.aws_vpc.default.id
  description = "Minimal security group for classroom EC2 instances"

  # SSH access
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP access
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  # Jenkins (port 8080) access
  ingress {
    description = "Jenkins"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  # HTTPS access
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound traffic
  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "sg-classroom-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# EC2 Pool Instances - Emergency Option
resource "aws_instance" "classroom_pool" {
  count                  = var.ec2_pool_size > 0 ? var.ec2_pool_size : 0
  ami                    = var.ec2_ami_id != "" ? var.ec2_ami_id : data.aws_ami.amazon_linux_2.id
  instance_type          = var.ec2_instance_type
  vpc_security_group_ids = [aws_security_group.classroom_sg.id]
  subnet_id              = var.ec2_subnet_id != "" ? var.ec2_subnet_id : data.aws_subnet.default.id
  iam_instance_profile   = aws_iam_instance_profile.ec2_ssm_profile.name

  user_data_replace_on_change = true
  user_data = var.user_data_script_path != "" ? file(var.user_data_script_path) : (
    var.user_data_script_content != "" ? var.user_data_script_content : ""
  )

  root_block_device {
    volume_size           = 40
    volume_type           = "gp3"
    delete_on_termination = true
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  tags = {
    Name        = "classroom-pool-${var.workshop_name}-${count.index}"
    Status      = "available"
    Project     = "classroom"
    Environment = var.environment
    Owner       = var.owner
    Type        = "pool"
    CreatedBy   = "terraform-emergency"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }

  lifecycle {
    create_before_destroy = true
  }
}




