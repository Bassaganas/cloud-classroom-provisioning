# IAM Lambda Module

This module manages the IAM role and policies for Lambda function execution.

## Resources

- **Lambda Execution Role**: IAM role assumed by all Lambda functions
- **Lambda IAM Policy**: Comprehensive policy for Lambda functions to manage:
  - IAM users
  - EC2 instances
  - DynamoDB tables
  - SSM parameters
  - S3 buckets
  - Logs
- **Secrets Manager Policy**: Optional policy for accessing Secrets Manager (if ARN provided)

## Outputs

- Lambda role ARN
- Lambda role name




