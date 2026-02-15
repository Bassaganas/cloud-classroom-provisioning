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

# CloudWatch Event Rule for Stopping Old Instances
resource "aws_cloudwatch_event_rule" "stop_old_instances_schedule" {
  name                = "eventbridge-stop-old-instances-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  schedule_expression = "rate(10 minutes)"
  description         = "Stop EC2 instances running for more than configured timeout"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

resource "aws_cloudwatch_event_target" "stop_old_instances_target" {
  rule      = aws_cloudwatch_event_rule.stop_old_instances_schedule.name
  target_id = "stop-old-instances-lambda"
  arn       = var.stop_old_instances_lambda_arn
}

resource "aws_lambda_permission" "allow_eventbridge_stop_old_instances" {
  statement_id  = "AllowExecutionFromEventBridgeStopOldInstances"
  action        = "lambda:InvokeFunction"
  function_name = split(":", var.stop_old_instances_lambda_arn)[6]
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stop_old_instances_schedule.arn
}

# CloudWatch Event Rule for Admin Instance Cleanup
resource "aws_cloudwatch_event_rule" "admin_cleanup_schedule" {
  name                = "eventbridge-admin-cleanup-${local.normalized_tutorial_name}-${var.environment}-${local.region_code}"
  schedule_expression = var.admin_cleanup_schedule
  description         = "Clean up admin instances based on age"

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "classroom"
    WorkshopID  = var.workshop_name
    Company     = "TestingFantasy"
  }
}

resource "aws_cloudwatch_event_target" "admin_cleanup_target" {
  rule      = aws_cloudwatch_event_rule.admin_cleanup_schedule.name
  target_id = "admin-cleanup-lambda"
  arn       = var.admin_cleanup_lambda_arn
}

resource "aws_lambda_permission" "allow_eventbridge_admin_cleanup" {
  statement_id  = "AllowExecutionFromEventBridgeAdminCleanup"
  action        = "lambda:InvokeFunction"
  function_name = split(":", var.admin_cleanup_lambda_arn)[6]
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.admin_cleanup_schedule.arn
}

