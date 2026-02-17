# Scripts Directory

This directory contains all deployment and utility scripts for the cloud classroom provisioning system.

## 🚀 Core Deployment Scripts

### `setup_classroom.sh`
**Main entry point for all deployments**

```bash
# Deploy AWS classroom
./scripts/setup_classroom.sh --name my-classroom --cloud aws --region eu-west-3

# Deploy with specific workshop
./scripts/setup_classroom.sh --name my-classroom --cloud aws --region eu-west-3 --workshop fellowship

# Destroy infrastructure
./scripts/setup_classroom.sh --name my-classroom --cloud aws --region eu-west-3 --destroy
```

**Features:**
- Handles both AWS and Azure deployments
- Automatically infers workshop name from classroom name
- Supports `--only-common` and `--only-workshop` for partial deployments
- Clean Terraform workflow (no manual imports needed)

### `setup_aws.sh`
**AWS-specific deployment logic**

Called automatically by `setup_classroom.sh`. Handles:
- Terraform backend setup
- Lambda packaging (via `package_lambda.sh`)
- Frontend build and deployment (via `build_frontend.sh`)
- Workshop template map publishing

### `package_lambda.sh`
**Packages Lambda functions for deployment**

```bash
./scripts/package_lambda.sh --cloud aws
```

Creates deployment packages in `functions/packages/` directory.

### `build_frontend.sh`
**Builds and deploys React frontend to S3**

```bash
./scripts/build_frontend.sh --environment dev --region eu-west-3
```

Usually called automatically by `setup_aws.sh`, but can be run standalone for frontend-only updates.

---

## 🧪 Development & Testing

### `test_local.sh`
**Local development environment setup**

```bash
./scripts/test_local.sh
```

Starts:
- Mock API server (option 1) OR connects to real Lambda API (option 2)
- React development server on `http://localhost:5173`

The script automatically detects Lambda URL from Terraform outputs if using real API.

### `mock_api_server.py`
**Mock API server for local frontend development**

Used by `test_local.sh` when testing without deployed infrastructure.

---

## 🧹 Cleanup Scripts

### `cleanup_aws_users.sh`
**Clean up AWS IAM users and associated resources**

```bash
./scripts/cleanup_aws_users.sh
```

Deletes:
- Login profiles
- Access keys
- Attached policies
- Inline policies
- The user itself

### `cleanup_azure_users.sh`
**Clean up Azure AD users and associated resources**

```bash
./scripts/cleanup_azure_users.sh
```

Deletes:
- Service principals
- Resource groups
- Role assignments
- The user itself

### `delete_students.sh`
**Delete student users (Azure)**

```bash
./scripts/delete_students.sh
```

---

## ☁️ Azure Scripts (if using Azure)

### `setup_azure.sh`
**Azure-specific deployment**

Called automatically by `setup_classroom.sh` for Azure deployments.

### `setup_azure_rbac.sh`
**Setup Azure RBAC roles**

```bash
./scripts/setup_azure_rbac.sh
```

### `deploy_azure_function.sh`
**Deploy Azure Functions**

```bash
./scripts/deploy_azure_function.sh
```

### `test_azure_config.sh`
**Test Azure configuration**

```bash
./scripts/test_azure_config.sh
```

---

## 🎯 Quick Start

**For new deployments:**
```bash
./scripts/setup_classroom.sh --name my-classroom --cloud aws --region eu-west-3
```

**For local development:**
```bash
./scripts/test_local.sh
```

**For frontend-only updates:**
```bash
./scripts/build_frontend.sh --environment dev --region eu-west-3
```

---

## 📝 Notes

- All scripts use relative paths and can be run from the project root
- Terraform manages state automatically - no manual imports needed
- Frontend deployment is integrated into the main deployment flow
- Lambda packaging is automatic unless `--skip-packaging` is used
- For clean deployments, see `CLEAN_DEPLOYMENT.md` in the project root

---

## 🔄 Clean Deployment Workflow

The deployment system is designed to work cleanly without manual state management:

1. **First deployment**: Run `setup_classroom.sh` - Terraform creates everything
2. **Updates**: Run `setup_classroom.sh` again - Terraform updates existing resources
3. **Clean slate**: Use `--destroy` then redeploy for a fresh start

No import scripts or state patching needed - Terraform handles it all.
