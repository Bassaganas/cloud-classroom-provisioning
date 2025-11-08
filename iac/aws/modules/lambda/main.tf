# Lambda Function for Status Checking (created first)
resource "aws_lambda_function" "status" {
  filename         = "${var.functions_path}/testus_patronus_status.zip"
  function_name    = "status-lambda-${var.classroom_name}-${var.environment}"
  role             = var.lambda_role_arn
  handler          = "testus_patronus_status.lambda_handler"
  runtime          = "python3.9"
  timeout          = 30
  memory_size      = 128
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${var.functions_path}/testus_patronus_status.zip")

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Lambda Function URL for Status
resource "aws_lambda_function_url" "status_url" {
  function_name      = aws_lambda_function.status.function_name
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
  filename                      = "${var.functions_path}/testus_patronus_user_management.zip"
  function_name                 = "lambda-${var.classroom_name}-${var.environment}"
  role                          = var.lambda_role_arn
  handler                       = "testus_patronus_user_management.lambda_handler"
  runtime                       = "python3.9"
  timeout                       = var.user_management_timeout
  memory_size                   = var.user_management_memory_size
  package_type                  = "Zip"
  source_code_hash              = filebase64sha256("${var.functions_path}/testus_patronus_user_management.zip")
  publish                       = var.user_management_provisioned_concurrency > 0 ? true : false  # Publish version if using provisioned concurrency
  reserved_concurrent_executions = var.user_management_reserved_concurrency > 0 ? var.user_management_reserved_concurrency : null  # Reserved concurrency (null = unlimited)

  environment {
    variables = {
      ENVIRONMENT       = var.environment
      STATUS_LAMBDA_URL = var.status_lambda_url != "" ? var.status_lambda_url : aws_lambda_function_url.status_url.function_url
      SKIP_IAM_USER_CREATION = var.skip_iam_user_creation ? "true" : "false"
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }

  depends_on = [aws_lambda_function_url.status_url]
}

# Alias for User Management (required for provisioned concurrency)
# Provisioned concurrency requires a version or alias, not $LATEST
# The alias points to the published version
resource "aws_lambda_alias" "user_management" {
  count            = var.user_management_provisioned_concurrency > 0 ? 1 : 0
  name             = "live"
  description      = "Live alias for provisioned concurrency"
  function_name    = aws_lambda_function.user_management.function_name
  function_version = aws_lambda_function.user_management.version  # Points to published version
  
  # Note: When function code is updated, Terraform will publish a new version
  # and the alias will need to be updated (or use lifecycle ignore_changes)
}

# Provisioned Concurrency for User Management (if configured)
# Pre-warms execution environments to eliminate cold starts
# This keeps execution environments "warm" and ready to respond immediately
resource "aws_lambda_provisioned_concurrency_config" "user_management" {
  count                             = var.user_management_provisioned_concurrency > 0 ? 1 : 0
  function_name                     = aws_lambda_function.user_management.function_name
  provisioned_concurrent_executions = var.user_management_provisioned_concurrency
  qualifier                         = aws_lambda_alias.user_management[0].name
  
  depends_on = [aws_lambda_alias.user_management]
}

# Lambda Function URL for User Management
resource "aws_lambda_function_url" "user_management_url" {
  function_name      = aws_lambda_function.user_management.function_name
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
  filename         = "${var.functions_path}/testus_patronus_stop_old_instances.zip"
  function_name    = "stop-old-instances-${var.classroom_name}-${var.environment}"
  role             = var.lambda_role_arn
  handler          = "testus_patronus_stop_old_instances.lambda_handler"
  runtime          = "python3.9"
  timeout          = 300
  memory_size      = 256
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${var.functions_path}/testus_patronus_stop_old_instances.zip")

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Lambda Function for Instance Manager
resource "aws_lambda_function" "instance_manager" {
  filename         = "${var.functions_path}/testus_patronus_instance_manager.zip"
  function_name    = "instance-manager-${var.classroom_name}-${var.environment}"
  role             = var.lambda_role_arn
  handler          = "testus_patronus_instance_manager.lambda_handler"
  runtime          = "python3.9"
  timeout          = var.instance_manager_timeout
  memory_size      = var.instance_manager_memory_size
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${var.functions_path}/testus_patronus_instance_manager.zip")

  environment {
    variables = {
      ENVIRONMENT            = var.environment
      CLASSROOM_REGION        = var.region
      EC2_INSTANCE_TYPE       = var.instance_type
      EC2_SUBNET_ID           = var.subnet_id
      EC2_SECURITY_GROUP_IDS   = join(",", var.security_group_ids)
      EC2_IAM_INSTANCE_PROFILE = var.iam_instance_profile_name
      INSTANCE_MANAGER_PASSWORD_SECRET = var.instance_manager_password_secret_name
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Lambda Function URL for Instance Manager
resource "aws_lambda_function_url" "instance_manager_url" {
  function_name      = aws_lambda_function.instance_manager.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST", "DELETE"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}

# Lambda Function for Admin Instance Cleanup
resource "aws_lambda_function" "admin_cleanup" {
  filename         = "${var.functions_path}/testus_patronus_admin_cleanup.zip"
  function_name    = "admin-cleanup-${var.classroom_name}-${var.environment}"
  role             = var.lambda_role_arn
  handler          = "testus_patronus_admin_cleanup.lambda_handler"
  runtime          = "python3.9"
  timeout          = 300
  memory_size      = 256
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${var.functions_path}/testus_patronus_admin_cleanup.zip")

  environment {
    variables = {
      ENVIRONMENT            = var.environment
      CLASSROOM_REGION       = var.region
      ADMIN_CLEANUP_INTERVAL_DAYS = var.admin_cleanup_interval_days
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
  }
}

# Lambda Function for Dify Jira API
resource "aws_lambda_function" "dify_jira_api" {
  filename         = "${var.functions_path}/dify_jira_api.zip"
  function_name    = "dify-jira-api-${var.classroom_name}-${var.environment}"
  role             = var.lambda_role_arn
  handler          = "dify_jira_api.lambda_handler"
  runtime          = "python3.9"
  timeout          = 300
  memory_size      = 1024
  package_type     = "Zip"
  source_code_hash = filebase64sha256("${var.functions_path}/dify_jira_api.zip")

  environment {
    variables = {
      ENVIRONMENT   = var.environment
      CLASSROOM_NAME = var.classroom_name
    }
  }

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    Service     = "dify-jira-api"
  }
}

# Lambda Function URL for Dify Jira API
resource "aws_lambda_function_url" "dify_jira_api_url" {
  function_name      = aws_lambda_function.dify_jira_api.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"

  cors {
    allow_credentials = true
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST", "PUT", "DELETE"]
    allow_origins     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}
