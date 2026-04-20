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
  # Automatically construct instance manager password secret name
  instance_manager_password_secret_name = "classroom/${var.workshop_name}/${var.environment}/instance-manager/password"
}

# Lambda Function for Status Checking (created first)
resource "aws_lambda_function" "status" {
  count            = var.enable_status ? 1 : 0
  filename         = "${path.root}/../../functions/packages/testus_patronus_status.zip"
  function_name    = "lambda-status-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role             = var.lambda_role_arn
  handler          = "testus_patronus_status.lambda_handler"
  runtime          = "python3.9"
  timeout          = 30
  memory_size      = 128
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${path.root}/../../functions/packages/testus_patronus_status.zip")

  environment {
    variables = {
      ENVIRONMENT   = var.environment
      WORKSHOP_NAME = var.workshop_name
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Lambda Function URL for Status
resource "aws_lambda_function_url" "status_url" {
  count              = var.enable_status ? 1 : 0
  function_name      = aws_lambda_function.status[0].function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}

# Lambda Function for User Management (depends on status URL)
resource "aws_lambda_function" "user_management" {
  count                          = var.enable_user_management ? 1 : 0
  filename                       = "${path.root}/../../functions/packages/classroom_user_management.zip"
  function_name                  = "lambda-user-management-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role                           = var.lambda_role_arn
  handler                        = "classroom_user_management.lambda_handler"
  runtime                        = "python3.9"
  timeout                        = var.user_management_timeout
  memory_size                    = var.user_management_memory_size
  package_type                   = "Zip"
  source_code_hash               = filebase64sha256("${path.root}/../../functions/packages/classroom_user_management.zip")
  publish                        = var.user_management_provisioned_concurrency > 0 ? true : false                                 # Publish version if using provisioned concurrency
  reserved_concurrent_executions = var.user_management_reserved_concurrency > 0 ? var.user_management_reserved_concurrency : null # Reserved concurrency (null = unlimited)

  environment {
    variables = {
      ENVIRONMENT            = var.environment
      WORKSHOP_NAME          = var.workshop_name
      STATUS_LAMBDA_URL      = var.status_lambda_url != "" ? var.status_lambda_url : (var.enable_status ? aws_lambda_function_url.status_url[0].function_url : "")
      SKIP_IAM_USER_CREATION = var.skip_iam_user_creation ? "true" : "false"
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }

}

# Alias for User Management (required for provisioned concurrency)
# Provisioned concurrency requires a version or alias, not $LATEST
# The alias points to the published version
resource "aws_lambda_alias" "user_management" {
  count            = var.enable_user_management && var.user_management_provisioned_concurrency > 0 ? 1 : 0
  name             = "live"
  description      = "Live alias for provisioned concurrency"
  function_name    = aws_lambda_function.user_management[0].function_name
  function_version = aws_lambda_function.user_management[0].version # Points to published version

  # Note: When function code is updated, Terraform will publish a new version
  # and the alias will need to be updated (or use lifecycle ignore_changes)
}

# Provisioned Concurrency for User Management (if configured)
# Pre-warms execution environments to eliminate cold starts
# This keeps execution environments "warm" and ready to respond immediately
resource "aws_lambda_provisioned_concurrency_config" "user_management" {
  count                             = var.enable_user_management && var.user_management_provisioned_concurrency > 0 ? 1 : 0
  function_name                     = aws_lambda_function.user_management[0].function_name
  provisioned_concurrent_executions = var.user_management_provisioned_concurrency
  qualifier                         = aws_lambda_alias.user_management[0].name

  depends_on = [aws_lambda_alias.user_management]
}

# Lambda Function URL for User Management
resource "aws_lambda_function_url" "user_management_url" {
  count              = var.enable_user_management ? 1 : 0
  function_name      = aws_lambda_function.user_management[0].function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}


# Lambda Function for Stopping Old Instances
resource "aws_lambda_function" "stop_old_instances" {
  count            = var.enable_stop_old_instances ? 1 : 0
  filename         = "${path.root}/../../functions/packages/classroom_stop_old_instances.zip"
  function_name    = "lambda-stop-old-instances-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role             = var.lambda_role_arn
  handler          = "classroom_stop_old_instances.lambda_handler"
  runtime          = "python3.9"
  timeout          = 300
  memory_size      = 256
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${path.root}/../../functions/packages/classroom_stop_old_instances.zip")

  environment {
    variables = {
      ENVIRONMENT                     = var.environment
      WORKSHOP_NAME                   = var.workshop_name
      CLASSROOM_REGION                = var.region
      INSTANCE_MANAGER_BASE_DOMAIN    = var.instance_manager_base_domain
      INSTANCE_MANAGER_HOSTED_ZONE_ID = var.instance_manager_hosted_zone_id
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Lambda Function for Instance Manager
resource "aws_lambda_function" "instance_manager" {
  count            = var.enable_instance_manager ? 1 : 0
  filename         = "${path.root}/../../functions/packages/classroom_instance_manager.zip"
  function_name    = "lambda-instance-manager-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role             = var.lambda_role_arn
  handler          = "classroom_instance_manager.lambda_handler"
  runtime          = "python3.9"
  timeout          = var.instance_manager_timeout
  memory_size      = var.instance_manager_memory_size
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${path.root}/../../functions/packages/classroom_instance_manager.zip")

  environment {
    variables = {
      ENVIRONMENT                             = var.environment
      WORKSHOP_NAME                           = var.workshop_name
      CLASSROOM_REGION                        = var.region
      EC2_INSTANCE_TYPE                       = var.instance_type
      EC2_SUBNET_ID                           = var.subnet_id
      EC2_SECURITY_GROUP_IDS                  = join(",", var.security_group_ids)
      EC2_IAM_INSTANCE_PROFILE                = var.iam_instance_profile_name
      INSTANCE_MANAGER_PASSWORD_SECRET        = var.instance_manager_password_secret_name
      INSTANCE_MANAGER_TEMPLATE_MAP_PARAMETER = var.instance_manager_template_map_parameter
      INSTANCE_MANAGER_BASE_DOMAIN            = var.instance_manager_base_domain
      INSTANCE_MANAGER_HOSTED_ZONE_ID         = var.instance_manager_hosted_zone_id
      INSTANCE_MANAGER_HTTPS_CERT_ARN         = var.instance_manager_https_cert_arn
      SHARED_CORE_MODE                        = var.shared_core_mode ? "true" : "false"
      SHARED_JENKINS_URL                      = var.shared_core_jenkins_url
      SHARED_GITEA_URL                        = var.shared_core_gitea_url
      SHARED_CORE_PROVISIONING_QUEUE_URL      = var.shared_core_provisioning_queue_url
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Lambda Function URL for Instance Manager
resource "aws_lambda_function_url" "instance_manager_url" {
  count              = var.enable_instance_manager ? 1 : 0
  function_name      = aws_lambda_function.instance_manager[0].function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["*"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}

# Explicit permission for public access to Function URL
# This ensures the Function URL is accessible even if there are propagation delays
resource "aws_lambda_permission" "instance_manager_url_public" {
  count = var.enable_instance_manager ? 1 : 0

  statement_id           = "AllowPublicInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.instance_manager[0].function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# Lambda Function for Admin Instance Cleanup
resource "aws_lambda_function" "admin_cleanup" {
  count            = var.enable_admin_cleanup ? 1 : 0
  filename         = "${path.root}/../../functions/packages/classroom_admin_cleanup.zip"
  function_name    = "lambda-admin-cleanup-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role             = var.lambda_role_arn
  handler          = "classroom_admin_cleanup.lambda_handler"
  runtime          = "python3.9"
  timeout          = 300
  memory_size      = 256
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${path.root}/../../functions/packages/classroom_admin_cleanup.zip")

  environment {
    variables = {
      ENVIRONMENT                     = var.environment
      WORKSHOP_NAME                   = var.workshop_name
      CLASSROOM_REGION                = var.region
      ADMIN_CLEANUP_INTERVAL_DAYS     = var.admin_cleanup_interval_days
      INSTANCE_MANAGER_BASE_DOMAIN    = var.instance_manager_base_domain
      INSTANCE_MANAGER_HOSTED_ZONE_ID = var.instance_manager_hosted_zone_id
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Lambda Function for Dify Jira API
resource "aws_lambda_function" "dify_jira_api" {
  count            = var.enable_dify_jira_api ? 1 : 0
  filename         = "${path.root}/../../functions/packages/dify_jira_api.zip"
  function_name    = "lambda-dify-jira-api-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role             = var.lambda_role_arn
  handler          = "dify_jira_api.lambda_handler"
  runtime          = "python3.9"
  timeout          = 300
  memory_size      = 1024
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${path.root}/../../functions/packages/dify_jira_api.zip")

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      WORKSHOP_NAME  = var.workshop_name
      CLASSROOM_NAME = var.classroom_name
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Service     = "dify-jira-api"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

# Lambda Function URL for Dify Jira API
resource "aws_lambda_function_url" "dify_jira_api_url" {
  count              = var.enable_dify_jira_api ? 1 : 0
  function_name      = aws_lambda_function.dify_jira_api[0].function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["*"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}


# ============================================================================
# Fellowship Student Assignment Lambda Function
# ============================================================================
# Provisions student credentials, EC2 instances, and service URLs for the
# Fellowship workshop. Provides an HTML interface for students to initiate
# their provisioning workflow.

# Lambda Function for Fellowship Student Assignment
resource "aws_lambda_function" "fellowship_student_assignment" {
  count            = var.enable_fellowship_student_assignment ? 1 : 0
  filename         = "${path.root}/../../functions/packages/fellowship_student_assignment.zip"
  function_name    = "lambda-fellowship-student-assignment-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  role             = var.lambda_role_arn
  handler          = "fellowship_student_assignment.lambda_handler"
  runtime          = "python3.11"
  timeout          = var.fellowship_student_assignment_timeout
  memory_size      = var.fellowship_student_assignment_memory_size
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${path.root}/../../functions/packages/fellowship_student_assignment.zip")

  environment {
    variables = {
      ENVIRONMENT                      = var.environment
      WORKSHOP_NAME                    = var.workshop_name
      CLASSROOM_NAME                   = var.classroom_name
      CLASSROOM_REGION                 = var.region
      STATUS_LAMBDA_URL                = var.status_lambda_url != "" ? var.status_lambda_url : (var.enable_status ? aws_lambda_function_url.status_url[0].function_url : "")
      INSTANCE_MANAGER_URL             = var.instance_manager_url != "" ? var.instance_manager_url : (var.enable_instance_manager ? aws_lambda_function_url.instance_manager_url[0].function_url : "")
      INSTANCE_MANAGER_PASSWORD_SECRET = local.instance_manager_password_secret_name
      DESTROY_KEY                      = var.destroy_key
      SKIP_IAM_USER_CREATION           = var.skip_iam_user_creation ? "true" : "false"
      FELLOWSHIP_SUT_DOMAIN            = var.fellowship_sut_domain
      FELLOWSHIP_JENKINS_DOMAIN        = var.fellowship_jenkins_domain
      FELLOWSHIP_GITEA_DOMAIN          = var.fellowship_gitea_domain
      FELLOWSHIP_GITEA_API_DOMAIN      = var.fellowship_gitea_api_domain
      FELLOWSHIP_GITEA_ORG             = var.fellowship_gitea_org
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Service     = "fellowship-student-assignment"
    Company     = "TestingFantasy"
  }
}

# Lambda Function URL for Fellowship Student Assignment
resource "aws_lambda_function_url" "fellowship_student_assignment_url" {
  count              = var.enable_fellowship_student_assignment ? 1 : 0
  function_name      = aws_lambda_function.fellowship_student_assignment[0].function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["*"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}

# Explicit permission for public access to Function URL
resource "aws_lambda_permission" "fellowship_student_assignment_url_public" {
  count = var.enable_fellowship_student_assignment ? 1 : 0

  statement_id           = "AllowPublicInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.fellowship_student_assignment[0].function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
