# IAM Role for Lambda execution
resource "aws_iam_role" "lambda_role" {
  name = "classroom-lambda-execution-role-${var.workshop_name}-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
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

# IAM Policy for Lambda to manage EC2, DynamoDB, IAM, etc.
resource "aws_iam_role_policy" "lambda_iam_policy" {
  name = "LambdaIAMManagementPolicy-${var.workshop_name}-${var.environment}"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DescribeTable",
          "dynamodb:ListTables"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateUser",
          "iam:CreateAccessKey",
          "iam:DeleteUser",
          "iam:DeleteAccessKey",
          "iam:ListAccessKeys",
          "iam:GetUser",
          "iam:ListAttachedUserPolicies",
          "iam:AttachUserPolicy",
          "iam:DetachUserPolicy",
          "iam:ListUserPolicies",
          "iam:PutUserPolicy",
          "iam:DeleteUserPolicy",
          "iam:TagUser",
          "iam:UntagUser",
          "iam:ListUserTags",
          "iam:CreateLoginProfile",
          "iam:DeleteLoginProfile",
          "iam:GetLoginProfile",
          "iam:UpdateLoginProfile",
          "iam:CreateServiceLinkedRole"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:RunInstances",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeImages",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:CreateTags",
          "ec2:StopInstances",
          "ec2:StartInstances",
          "ec2:DescribeAccountAttributes"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = "arn:aws:iam::${var.account_id}:role/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:${var.region}:${var.account_id}:parameter/classroom/${var.workshop_name}/${var.environment}/*",
          "arn:aws:ssm:${var.region}:${var.account_id}:parameter/classroom/templates/${var.environment}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:CreateTargetGroup",
          "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:RegisterTargets",
          "elasticloadbalancing:DeregisterTargets",
          "elasticloadbalancing:CreateListener",
          "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:DescribeListeners",
          "elasticloadbalancing:CreateRule",
          "elasticloadbalancing:DeleteRule",
          "elasticloadbalancing:DescribeRules",
          "elasticloadbalancing:AddTags"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "route53:ChangeResourceRecordSets",
          "route53:ListHostedZonesByName",
          "route53:ListResourceRecordSets"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "acm:DescribeCertificate",
          "acm:ListCertificates"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:DeleteSecurityGroup"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:DescribeInstanceInformation",
          "ssm:SendCommand",
          "ssm:GetCommandInvocation"
        ]
        Resource = "*"
      }
    ]
  })
}

# Add AWS Managed Policy for Lambda Basic Execution
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# IAM Policy for Secrets Manager (if secret ARN provided)
# Always create the policy - it will be empty if no secrets are provided
# This avoids count dependency issues with resource outputs
resource "aws_iam_policy" "lambda_secretsmanager_policy" {
  count = 1

  name        = "lambda-secretsmanager-policy-${var.workshop_name}-${var.environment}"
  description = "Allow Lambda to get secrets from Secrets Manager"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      var.secrets_manager_secret_arn != "" ? [
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:GetSecretValue"
          ]
          Resource = var.secrets_manager_secret_arn
        }
      ] : [],
      var.instance_manager_password_secret_arn != "" ? [
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:GetSecretValue"
          ]
          Resource = var.instance_manager_password_secret_arn
        }
      ] : []
    )
  })
}

resource "aws_iam_role_policy_attachment" "lambda_secretsmanager_attach" {
  # Always attach the policy since we always create it (policy will be empty if no secrets)
  count = 1

  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_secretsmanager_policy[0].arn
}
