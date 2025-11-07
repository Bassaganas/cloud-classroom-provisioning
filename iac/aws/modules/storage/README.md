# Storage Module

This module manages DynamoDB tables and SSM parameters for configuration.

## Resources

- **DynamoDB Table**: `instance-assignments-{environment}` - Tracks EC2 instance assignments to students
- **SSM Parameters**: Configuration for instance timeout values
  - `instance_stop_timeout_minutes`
  - `instance_terminate_timeout_minutes`
  - `instance_hard_terminate_timeout_minutes`

## Outputs

- DynamoDB table name and ARN




