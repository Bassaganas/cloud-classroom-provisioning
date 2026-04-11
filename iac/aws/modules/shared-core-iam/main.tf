data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  shared_core_prefix     = "/classroom/shared-core/${var.shared_core_environment}"
  shared_core_github_sub = "repo:${var.shared_core_github_owner}/${var.shared_core_github_repo}:environment:${var.shared_core_github_environment}"
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [var.github_actions_oidc_thumbprint]

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_iam_policy" "shared_core_github_actions_read" {
  name        = "shared-core-github-actions-read-${var.shared_core_environment}-${replace(var.region, "-", "")}"
  description = "Allow GitHub Actions shared-core deploy workflow to read required SSM parameters and Secrets Manager secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadSharedCoreParameters"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${local.shared_core_prefix}/*"
        ]
      },
      {
        Sid    = "UpdateSharedCoreSshHostParameter"
        Effect = "Allow"
        Action = [
          "ssm:PutParameter"
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${local.shared_core_prefix}/ssh-host"
        ]
      },
      {
        Sid    = "DescribeSharedCoreInstance"
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances"
        ]
        Resource = "*"
      },
      {
        Sid    = "UpdateSharedCoreDnsRecords"
        Effect = "Allow"
        Action = [
          "route53:ChangeResourceRecordSets",
          "route53:ListResourceRecordSets",
          "route53:ListHostedZonesByName"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadSharedCoreSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          var.shared_core_deploy_secret_arn,
          "arn:${data.aws_partition.current.partition}:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:/classroom/wildcard-cert/fellowship*"
        ]
      },
      {
        Sid    = "DecryptSecretsManagerValues"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.region}.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_iam_role" "shared_core_github_actions" {
  name = "shared-core-github-actions-${var.shared_core_environment}-${replace(var.region, "-", "")}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = local.shared_core_github_sub
          }
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Company     = "TestingFantasy"
  }
}

resource "aws_iam_role_policy_attachment" "shared_core_github_actions_read" {
  role       = aws_iam_role.shared_core_github_actions.name
  policy_arn = aws_iam_policy.shared_core_github_actions_read.arn
}
