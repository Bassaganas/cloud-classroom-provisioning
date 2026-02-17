---
sidebar_position: 3
---

# Component Details

## Student-Facing Components

### Workshop Lambda Functions (HTML-Serving)

**User Management Lambda**: Creates student accounts and serves HTML pages with credentials
- Function name: `lambda-user-management-{workshop}-{env}-{region}`
- Source: `functions/aws/{workshop}/classroom_user_management.py`
- Serves HTML directly (not REST API)
- Custom domain via CloudFront: `testus-patronus.testingfantasy.com`, `fellowship-of-the-build.testingfantasy.com`
- Also accessible via Lambda Function URL
- Workshop-specific (Testus Patronus, Fellowship)

**Status Lambda**: Checks workshop instance status
- Function name: `lambda-status-{workshop}-{env}-{region}`
- Source: `functions/aws/testus_patronus/testus_patronus_status.py`
- Accessible via Lambda Function URL

**Dify Jira API Lambda**: Dify Jira API integration
- Function name: `lambda-dify-jira-api-{workshop}-{env}-{region}`
- Source: `functions/aws/testus_patronus/dify_jira_api.py`
- Custom domain via CloudFront: `dify-jira.testingfantasy.com`, `dify-jira-fellowship.testingfantasy.com`

### Student Access CloudFront

**Amazon CloudFront**: Global CDN for workshop Lambda functions
- Custom domains: `testus-patronus.testingfantasy.com`, `fellowship-of-the-build.testingfantasy.com`
- Routes directly to Lambda Function URLs
- SSL/TLS termination via ACM certificates (us-east-1)

## Instructor-Facing Components

### EC2 Manager Frontend

**Amazon CloudFront**: Global CDN serving the React SPA and routing API requests
- Custom domain: `ec2-management-{environment}.testingfantasy.com`
- SSL/TLS termination via ACM certificates

**Amazon S3**: Static website hosting for React application files
- Bucket: `s3-ec2-manager-frontend-common-{env}-{region}`
- Versioning and encryption enabled

### EC2 Manager API

**Amazon API Gateway**: REST API endpoint routing `/api/*` requests
- Custom domain: `ec2-management-api-{environment}.testingfantasy.com`
- Regional endpoint type
- CORS enabled for frontend access

**CloudFront Function**: URL rewriting for API path routing

### Instance Manager Lambda

**Instance Manager Lambda**: Core Lambda function handling EC2 lifecycle
- Function name: `lambda-instance-manager-common-{env}-{region}`
- Source: `functions/common/classroom_instance_manager.py`
- Supports both API Gateway and Function URL invocation
- Manages instance creation, assignment, deletion, HTTPS setup
- **Instructor-only** - not accessible to students

## Shared Compute Layer

### Automation Lambda Functions

**Stop Old Instances Lambda**: Scheduled function stopping idle instances
- Function name: `lambda-stop-old-instances-{workshop}-{env}-{region}`
- Source: `functions/common/classroom_stop_old_instances.py`
- Runs every 5 minutes via EventBridge

**Admin Cleanup Lambda**: Scheduled function terminating admin instances
- Function name: `lambda-admin-cleanup-{workshop}-{env}-{region}`
- Source: `functions/common/classroom_admin_cleanup.py`
- Runs on configurable schedule (default: weekly)

### EC2 Infrastructure

**Amazon EC2 Instances**: Pre-configured instances for students
- Pool instances: `{workshop}-pool-{i}`
- Admin instances: `{workshop}-admin-{i}`
- Pre-installed applications: Dify AI, Jenkins, etc.

**Application Load Balancer (ALB)**: On-demand HTTPS endpoints
- Creates subdomains: `{instance-id}.{workshop}.testingfantasy.com`
- Wildcard certificate for `*.testingfantasy.com`

**DNS & Certificates:**
- **AWS Certificate Manager (ACM)**: SSL/TLS certificates (must be in `us-east-1` for CloudFront)
- **Amazon Route53**: DNS management for custom domains

## Data Layer

**DynamoDB - Instance Assignments**: Tracks EC2 instance assignments
- Table: `dynamodb-instance-assignments-{workshop}-{env}-{region}`
- Hash key: `instance_id`
- GSI: `student_name`

**DynamoDB - Tutorial Sessions**: Tracks tutorial session metadata
- Table: `dynamodb-tutorial-sessions-{workshop}-{env}-{region}`
- Hash key: `session_id`
- GSI: `workshop_name`

**AWS Systems Manager Parameter Store**: Configuration storage
- `/classroom/templates/{env}`: Workshop template configurations (AMI, instance type, user_data)
- `/classroom/{workshop}/{env}/*`: Workshop-specific timeout settings

**AWS Secrets Manager**: Secure credential storage
- `classroom/{workshop}/{env}/instance-manager/password`: Instance manager authentication password

## Monitoring & Automation

**Amazon EventBridge**: Scheduled rules triggering cleanup functions
- Stop old instances: Every 5 minutes
- Admin cleanup: Configurable (default: weekly on Sunday 2 AM)

## Security

**IAM Roles**: Lambda execution roles with least-privilege permissions
- Role name: `iam-lambda-execution-role-{workshop}-{env}-{region}`
- Permissions: EC2, DynamoDB, SSM, Secrets Manager, ALB management
- Instance profiles for EC2 instances
