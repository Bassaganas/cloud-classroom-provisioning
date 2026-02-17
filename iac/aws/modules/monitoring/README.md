# Monitoring Module

This module manages CloudWatch Events for scheduled Lambda invocations.

## Resources

- **Stop Old Instances Schedule**: Runs every 10 minutes to stop/terminate old instances
- **Admin Cleanup Schedule**: Configurable schedule (default: weekly on Sunday at 2 AM UTC)

## Dependencies

- Requires Lambda function ARNs from `lambda` module

## Outputs

None (monitoring resources only)




