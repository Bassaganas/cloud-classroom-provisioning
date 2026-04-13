# Jenkins ECS Fargate Agent Pool
#
# Creates the AWS infrastructure required for the Jenkins ECS cloud plugin to
# spawn ephemeral Fargate containers as build agents.
#
# Architecture:
#   Jenkins controller (on shared-core EC2) ──JNLP:50000──► ECS Fargate tasks
#   Each task runs jenkins/inbound-agent (customised via ECR image).
#   Tasks start on build trigger, stop when the build completes.
#   The shared-core EC2 instance role is granted the minimum ECS permissions
#   required to register task definitions, run tasks, and stop tasks.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  prefix = "fellowship-jenkins-agent-${var.environment}"
}

# ── ECR repository ──────────────────────────────────────────────────────────

resource "aws_ecr_repository" "jenkins_agent" {
  name                 = "fellowship-jenkins-agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "jenkins-agent"
    Company     = "TestingFantasy"
  }
}

resource "aws_ecr_lifecycle_policy" "jenkins_agent" {
  repository = aws_ecr_repository.jenkins_agent.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ── ECS Cluster ─────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "jenkins_agents" {
  name = "${local.prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "disabled" # keep cost low for a classroom environment
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "jenkins-agent"
    Company     = "TestingFantasy"
  }
}

resource "aws_ecs_cluster_capacity_providers" "jenkins_agents" {
  cluster_name = aws_ecs_cluster.jenkins_agents.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# ── CloudWatch log group ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "jenkins_agents" {
  name              = "/jenkins/agents/fellowship"
  retention_in_days = 7

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "jenkins-agent"
    Company     = "TestingFantasy"
  }
}

# ── Security group (agents) ──────────────────────────────────────────────────
#
# Agents need NO inbound access — they call OUT to the Jenkins controller on
# port 50000 (JNLP).  All other outbound traffic (ECR pull, pip, npm, AWS
# APIs, Gitea clone) goes to 443.

resource "aws_security_group" "jenkins_agent" {
  name_prefix = "${local.prefix}-sg-"
  vpc_id      = var.vpc_id
  description = "Jenkins ECS Fargate build-agent security group"

  # JNLP outbound to Jenkins controller shared-core SG on port 50000
  egress {
    description     = "JNLP to Jenkins controller"
    from_port       = 50000
    to_port         = 50000
    protocol        = "tcp"
    security_groups = [var.shared_core_security_group_id]
  }

  # HTTPS outbound for ECR pull, AWS APIs, npm, pip, git over HTTPS
  egress {
    description = "HTTPS outbound (ECR pull / AWS APIs / package managers)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP outbound – git clone over plain HTTP if needed (Gitea on port 3000)
  egress {
    description = "HTTP outbound"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Gitea internal port – allows git clone via docker-internal URL
  egress {
    description = "Gitea API / HTTP (internal port 3000)"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${local.prefix}-sg"
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Component   = "jenkins-agent"
    Company     = "TestingFantasy"
  }
}

# ── IAM — task execution role (ECS pulls image, writes logs) ────────────────

resource "aws_iam_role" "task_execution" {
  name = "${local.prefix}-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow task execution role to pull from the ECR repo
resource "aws_iam_role_policy" "task_execution_ecr" {
  name = "${local.prefix}-ecr-pull"
  role = aws_iam_role.task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ECRPull"
      Effect = "Allow"
      Action = [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetAuthorizationToken"
      ]
      Resource = "*"
    }]
  })
}

# ── IAM — task role (what the agent container can do at runtime) ─────────────

resource "aws_iam_role" "task_role" {
  name = "${local.prefix}-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_iam_role_policy" "task_role_cloudwatch" {
  name = "${local.prefix}-cloudwatch"
  role = aws_iam_role.task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "CloudWatchLogs"
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ]
      Resource = "${aws_cloudwatch_log_group.jenkins_agents.arn}:*"
    }]
  })
}

# ── IAM — grant shared-core EC2 role ECS permissions ────────────────────────
#
# The Jenkins ECS plugin running on the shared-core EC2 host uses the instance
# profile to call ECS APIs.  Minimum permissions needed:
#   - Register / describe task definitions (plugin creates one per agent template)
#   - Run / stop / describe tasks
#   - iam:PassRole to hand off the execution role to ECS

resource "aws_iam_role_policy" "shared_core_ecs_permissions" {
  name = "jenkins-ecs-cloud-${var.environment}"
  role = var.shared_core_ec2_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECSTaskManagement"
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:DeregisterTaskDefinition",
          "ecs:ListTaskDefinitions",
          "ecs:DescribeTaskDefinition",
          "ecs:ListClusters",
          "ecs:DescribeClusters",
          "ecs:RunTask",
          "ecs:StopTask",
          "ecs:DescribeTasks",
          "ecs:ListContainerInstances",
          "ecs:DescribeContainerInstances",
          "ecs:ListTasks",
          "ecs:TagResource",
          "ecs:UntagResource",
          "ecs:ListTagsForResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "PassExecutionRole"
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.task_execution.arn,
          aws_iam_role.task_role.arn
        ]
      }
    ]
  })
}
