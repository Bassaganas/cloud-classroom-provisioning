---
sidebar_position: 3
---

# Scripts Documentation

## Main Deployment Scripts

### `setup_classroom.sh` - Master Deployment Script

**Purpose:** Main entry point for deploying or destroying classroom infrastructure.

**Usage:**
```bash
./scripts/setup_classroom.sh --name <classroom-name> --cloud [aws|azure] [OPTIONS]
```

**Required Parameters:**
- `--name`: Name of the classroom (used for resource naming)
- `--cloud`: Cloud provider (`aws` or `azure`)

**AWS Options:**
- `--region`: AWS region (default: `eu-west-1`)
- `--environment`: Environment name (`dev`, `staging`, `prod`, default: `dev`)
- `--with-pool`: Create EC2 instance pool for students
- `--pool-size`: Number of EC2 instances (default: 40)
- `--workshop`: Workshop identifier (default: `testus_patronus`)
- `--only-common`: Apply/destroy only the common stack
- `--only-workshop`: Apply/destroy only the workshop stack
- `--skip-packaging`: Skip Lambda packaging (use existing packages)

**Common Options:**
- `--destroy`: Destroy infrastructure instead of creating
- `--parallelism`: Terraform parallelism (default: 4)
- `--force-unlock`: Force unlock Terraform state

**Examples:**
```bash
# Full deployment with EC2 pool
./scripts/setup_classroom.sh \
  --name spring-2024 \
  --cloud aws \
  --region eu-west-1 \
  --environment dev \
  --with-pool \
  --pool-size 20

# Lambda-only deployment
./scripts/setup_classroom.sh \
  --name dev-test \
  --cloud aws \
  --region eu-west-1 \
  --environment dev

# Destroy infrastructure
./scripts/setup_classroom.sh \
  --name spring-2024 \
  --cloud aws \
  --region eu-west-1 \
  --environment dev \
  --destroy
```

### `package_lambda.sh` - Lambda Function Packaging

**Purpose:** Packages Python Lambda functions with their dependencies into deployment-ready ZIP files.

**Usage:**
```bash
./scripts/package_lambda.sh --cloud [aws|azure]
```

**What It Does:**

1. **Creates Virtual Environment:** Isolates Python dependencies
2. **Installs Dependencies:** From `functions/aws/requirements.txt` or `functions/azure/requirements.txt`
3. **Packages Functions:** Creates ZIP files with code + dependencies
4. **Validates Packages:** Ensures all dependencies are included

**Packaged Functions (AWS):**
- `classroom_user_management.zip`: Student account creation
- `testus_patronus_status.zip`: Instance status checking
- `classroom_stop_old_instances.zip`: Cleanup automation
- `classroom_admin_cleanup.zip`: Admin instance cleanup
- `classroom_instance_manager.zip`: Core instance management
- `dify_jira_api.zip`: Dify Jira API integration

**Output Location:**
```
functions/packages/
├── classroom_user_management.zip
├── testus_patronus_status.zip
├── classroom_stop_old_instances.zip
├── classroom_admin_cleanup.zip
├── classroom_instance_manager.zip
└── dify_jira_api.zip
```

### `build_frontend.sh` - Frontend Build and Deployment

**Purpose:** Builds the React application and deploys it to S3/CloudFront.

**Usage:**
```bash
./scripts/build_frontend.sh [--environment dev] [--region eu-west-1]
```

**What It Does:**

1. **Installs Dependencies:** Runs `npm install` if needed
2. **Builds React App:** Creates production-optimized build
3. **Uploads to S3:** Syncs files to S3 bucket with appropriate cache headers
4. **Invalidates CloudFront:** Clears CDN cache for immediate updates

**Options:**
- `--environment`: Environment name (default: `dev`)
- `--region`: AWS region (default: `eu-west-3`)

**Note:** Frontend deployment is normally handled automatically by `setup_aws.sh` during infrastructure deployment. Use this script for manual frontend updates.
