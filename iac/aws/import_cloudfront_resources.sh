#!/bin/bash
# Script to import existing CloudFront logging resources into Terraform state
# Run this from the iac/aws directory
# This script will skip resources that are already in state

# Don't exit on error - we want to continue even if some imports fail
set +e

echo "Importing existing CloudFront logging resources..."
echo "Note: Resources already in state will be skipped."
echo ""

# Function to try import and skip if already managed
import_if_needed() {
    local resource_address=$1
    local resource_id=$2
    
    echo "Attempting to import: $resource_address"
    output=$(terraform import "$resource_address" "$resource_id" 2>&1)
    exit_code=$?
    
    if echo "$output" | grep -q "already managed by Terraform"; then
        echo "  ✓ Already in state, skipping"
        return 0
    elif [ $exit_code -eq 0 ]; then
        echo "  ✓ Successfully imported"
        return 0
    else
        echo "  ✗ Import failed:"
        echo "$output" | head -5
        return 1
    fi
}

# Workshop: fellowship
echo "=== Importing fellowship workshop resources ==="

echo "--- cloudfront_user_management module ---"
# CloudWatch Log Group
import_if_needed 'module.workshop_fellowship.module.cloudfront_user_management.aws_cloudwatch_log_group.cloudfront_logs[0]' '/aws/cloudfront/dev-fellowship' || true

# IAM Roles
import_if_needed 'module.workshop_fellowship.module.cloudfront_user_management.aws_iam_role.cloudfront_logging[0]' 'cloudfront-logging-dev-fellowship' || true
import_if_needed 'module.workshop_fellowship.module.cloudfront_user_management.aws_iam_role.lambda_log_processor[0]' 'lambda-log-processor-dev-fellowship' || true

# Kinesis Stream
import_if_needed 'module.workshop_fellowship.module.cloudfront_user_management.aws_kinesis_stream.cloudfront_logs[0]' 'cloudfront-logs-dev-fellowship' || true

# CloudFront Real-time Log Config
import_if_needed 'module.workshop_fellowship.module.cloudfront_user_management.aws_cloudfront_realtime_log_config.cloudfront_realtime_logs[0]' 'dev-fellowship-realtime-logs' || true

# Lambda Function
import_if_needed 'module.workshop_fellowship.module.cloudfront_user_management.aws_lambda_function.cloudfront_log_processor[0]' 'cloudfront-log-processor-dev-fellowship' || true

# CloudFront Function
import_if_needed 'module.workshop_fellowship.module.cloudfront_user_management.aws_cloudfront_function.api_path_rewrite' 'api-path-rewrite-dev-fellowship' || true

echo ""
echo "--- cloudfront_dify_jira module ---"
# CloudWatch Log Group
import_if_needed 'module.workshop_fellowship.module.cloudfront_dify_jira.aws_cloudwatch_log_group.cloudfront_logs[0]' '/aws/cloudfront/dev-fellowship' || true

# IAM Roles
import_if_needed 'module.workshop_fellowship.module.cloudfront_dify_jira.aws_iam_role.cloudfront_logging[0]' 'cloudfront-logging-dev-fellowship' || true
import_if_needed 'module.workshop_fellowship.module.cloudfront_dify_jira.aws_iam_role.lambda_log_processor[0]' 'lambda-log-processor-dev-fellowship' || true

# Kinesis Stream
import_if_needed 'module.workshop_fellowship.module.cloudfront_dify_jira.aws_kinesis_stream.cloudfront_logs[0]' 'cloudfront-logs-dev-fellowship' || true

# Lambda Function
import_if_needed 'module.workshop_fellowship.module.cloudfront_dify_jira.aws_lambda_function.cloudfront_log_processor[0]' 'cloudfront-log-processor-dev-fellowship' || true

# CloudFront Function
import_if_needed 'module.workshop_fellowship.module.cloudfront_dify_jira.aws_cloudfront_function.api_path_rewrite' 'api-path-rewrite-dev-fellowship' || true

echo ""
echo "=== Importing testus_patronus workshop resources ==="

echo "--- cloudfront_user_management module ---"
# CloudWatch Log Group
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_user_management.aws_cloudwatch_log_group.cloudfront_logs[0]' '/aws/cloudfront/dev-testus_patronus' || true

# IAM Roles
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_user_management.aws_iam_role.cloudfront_logging[0]' 'cloudfront-logging-dev-testus_patronus' || true
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_user_management.aws_iam_role.lambda_log_processor[0]' 'lambda-log-processor-dev-testus_patronus' || true

# Kinesis Stream
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_user_management.aws_kinesis_stream.cloudfront_logs[0]' 'cloudfront-logs-dev-testus_patronus' || true

# CloudFront Real-time Log Config
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_user_management.aws_cloudfront_realtime_log_config.cloudfront_realtime_logs[0]' 'dev-testus_patronus-realtime-logs' || true

# Lambda Function
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_user_management.aws_lambda_function.cloudfront_log_processor[0]' 'cloudfront-log-processor-dev-testus_patronus' || true

# CloudFront Function
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_user_management.aws_cloudfront_function.api_path_rewrite' 'api-path-rewrite-dev-testus_patronus' || true

echo ""
echo "--- cloudfront_dify_jira module ---"
# CloudWatch Log Group
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_dify_jira.aws_cloudwatch_log_group.cloudfront_logs[0]' '/aws/cloudfront/dev-testus_patronus' || true

# IAM Roles
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_dify_jira.aws_iam_role.cloudfront_logging[0]' 'cloudfront-logging-dev-testus_patronus' || true
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_dify_jira.aws_iam_role.lambda_log_processor[0]' 'lambda-log-processor-dev-testus_patronus' || true

# Kinesis Stream
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_dify_jira.aws_kinesis_stream.cloudfront_logs[0]' 'cloudfront-logs-dev-testus_patronus' || true

# CloudFront Real-time Log Config
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_dify_jira.aws_cloudfront_realtime_log_config.cloudfront_realtime_logs[0]' 'dev-testus_patronus-realtime-logs' || true

# Lambda Function
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_dify_jira.aws_lambda_function.cloudfront_log_processor[0]' 'cloudfront-log-processor-dev-testus_patronus' || true

# CloudFront Function
import_if_needed 'module.workshop_testus_patronus.module.cloudfront_dify_jira.aws_cloudfront_function.api_path_rewrite' 'api-path-rewrite-dev-testus_patronus' || true

echo ""
echo "Import process complete! Run 'terraform plan' to verify."
