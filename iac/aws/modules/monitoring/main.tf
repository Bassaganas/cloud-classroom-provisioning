# CloudWatch Event Rule for Stopping Old Instances
resource "aws_cloudwatch_event_rule" "stop_old_instances_schedule" {
  name                = "stop-old-instances-schedule-${var.environment}"
  schedule_expression = "rate(10 minutes)"
  description         = "Stop EC2 instances running for more than configured timeout"
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
  name                = "admin-cleanup-schedule-${var.environment}"
  schedule_expression = var.admin_cleanup_schedule
  description         = "Clean up admin instances based on age"
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

