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

resource "aws_iam_policy" "user_restricted_policy_lambda" {
  name        = "iam-user-restricted-policy-lambda-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to restrict users to their own resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:ListFunctions",
          "lambda:GetFunction",
          "lambda:InvokeFunction"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:CreateFunction",
          "lambda:UpdateFunctionCode",
          "lambda:DeleteFunction",
          "lambda:TagResource",
          "lambda:UntagResource",
          "lambda:ListTagsForResource"
        ]
        Resource = "arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function/*"
        Condition = {
          StringEquals = {
            "lambda:ResourceTag/Owner" : "$${aws:username}"
          }
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

resource "aws_iam_policy" "user_restricted_policy_athena" {
  name        = "iam-user-restricted-policy-athena-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to restrict users to their own resources on Athena"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryResults"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "athena:CreateNamedQuery",
          "athena:DeleteNamedQuery",
          "athena:TagResource",
          "athena:UntagResource",
          "athena:ListTagsForResource"
        ]
        Resource = "arn:aws:athena:${var.region}:${data.aws_caller_identity.current.account_id}:workgroup/*"
        Condition = {
          StringEquals = {
            "athena:ResourceTag/Owner" : "$${aws:username}"
          }
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

resource "aws_iam_policy" "user_restricted_policy_s3" {
  name        = "iam-user-restricted-policy-s3-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to restrict users to their own resources on S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::$${aws:username}*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:GetObjectTagging",
          "s3:PutObjectTagging",
          "s3:DeleteObjectTagging"
        ]
        Resource = "arn:aws:s3:::*"
        Condition = {
          StringEquals = {
            "s3:ResourceTag/Owner" : "$${aws:username}"
          }
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

resource "aws_iam_policy" "user_restricted_policy_eventbridge" {
  name        = "iam-user-restricted-policy-eventbridge-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to restrict users to their own resources on Eventbridge"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:ListRules",
          "events:DescribeRule",
          "events:PutRule",
          "events:DeleteRule",
          "events:TagResource",
          "events:UntagResource",
          "events:ListTagsForResource"
        ]
        Resource = "arn:aws:events:${var.region}:${data.aws_caller_identity.current.account_id}:rule/*"
        Condition = {
          StringEquals = {
            "events:ResourceTag/Owner" : "$${aws:username}"
          }
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

resource "aws_iam_policy" "user_restricted_policy_dynamodb" {
  name        = "iam-user-restricted-policy-dynamodb-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to restrict users to their own resources on DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:ListTables",
          "dynamodb:DescribeTable"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem",
          "dynamodb:TagResource",
          "dynamodb:UntagResource",
          "dynamodb:ListTagsForResource"
        ]
        Resource = "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/*"
        Condition = {
          StringEquals = {
            "dynamodb:ResourceTag/Owner" : "$${aws:username}"
          }
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

resource "aws_iam_policy" "user_restricted_policy_cicd" {
  name        = "iam-user-restricted-policy-cicd-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to restrict users to their own CICD resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "codebuild:ListProjects",
          "codepipeline:ListPipelines"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "codebuild:StartBuild",
          "codebuild:BatchGetBuilds",
          "codepipeline:StartPipelineExecution",
          "codepipeline:GetPipelineExecution",
          "codebuild:TagResource",
          "codebuild:UntagResource",
          "codebuild:ListTagsForResource",
          "codepipeline:TagResource",
          "codepipeline:UntagResource",
          "codepipeline:ListTagsForResource"
        ]
        Resource = [
          "arn:aws:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:project/*",
          "arn:aws:codepipeline:${var.region}:${data.aws_caller_identity.current.account_id}:pipeline/*"
        ]
        Condition = {
          StringEquals = {
            "codebuild:ResourceTag/Owner" : "$${aws:username}",
            "codepipeline:ResourceTag/Owner" : "$${aws:username}"
          }
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

resource "aws_iam_policy" "user_restricted_policy_resource_groups" {
  name        = "iam-user-restricted-policy-resourcegroups-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to allow resource groups and related actions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "resource-groups:*",
          "tag:GetResources",
          "cloudformation:ListStackResources",
          "cloudformation:DescribeStacks"
        ]
        Resource = "*"
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

resource "aws_iam_policy" "user_restricted_policy_tagging" {
  name        = "iam-user-restricted-policy-tagging-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  description = "Policy to allow users to manage tags on their resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "tag:GetResources",
          "tag:TagResources",
          "tag:UntagResources",
          "tag:GetTagKeys",
          "tag:GetTagValues"
        ]
        Resource = "*"
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

resource "aws_iam_role" "restricted_user_role" {
  name = "iam-restricted-user-role-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringLike = {
            "aws:userid" : "${data.aws_caller_identity.current.account_id}:*"
          }
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

resource "aws_iam_role_policy_attachment" "attach_lambda_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_lambda.arn
}

resource "aws_iam_role_policy_attachment" "attach_athena_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_athena.arn
}

resource "aws_iam_role_policy_attachment" "attach_s3_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_s3.arn
}

resource "aws_iam_role_policy_attachment" "attach_eventbridge_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_eventbridge.arn
}

resource "aws_iam_role_policy_attachment" "attach_dynamodb_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_dynamodb.arn
}

resource "aws_iam_role_policy_attachment" "attach_cicd_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_cicd.arn
}

resource "aws_iam_role_policy_attachment" "attach_resource_groups_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_resource_groups.arn
}

resource "aws_iam_role_policy_attachment" "attach_tagging_policy" {
  role       = aws_iam_role.restricted_user_role.name
  policy_arn = aws_iam_policy.user_restricted_policy_tagging.arn
}

data "aws_caller_identity" "current" {}
