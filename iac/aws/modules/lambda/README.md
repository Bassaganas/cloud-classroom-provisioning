# Lambda Module

This module manages all Lambda functions for the cloud classroom provisioning system.

## Resources

- **user_management**: Creates and manages student users, assigns EC2 instances
- **status**: Checks the status of EC2 instances and user assignments
- **stop_old_instances**: Automatically stops and terminates old, unassigned instances
- **instance_manager**: Manages EC2 instance pools (create, list, delete) via web UI
- **admin_cleanup**: Periodically cleans up admin instances based on age
- **dify_jira_api**: API for Dify and Jira integration

## Dependencies

- Requires `iam-lambda` module for execution role
- Requires `compute` module for subnet and security group IDs (for instance_manager)
- Status Lambda is created first, then user_management uses its URL

## Outputs

- All Lambda function ARNs
- All Lambda Function URLs




