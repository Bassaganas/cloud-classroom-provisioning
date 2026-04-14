#!/bin/bash

# Exit on error
set -e

# Function to display usage
usage() {
  echo "Usage: $0 --name <classroom-name> --cloud [aws|azure] [--region <aws-region>] [--location <azure-location>] [--destroy] [--parallelism <number>] [--force-unlock] [--setup-rbac] [--workshop <name>] [--environment <dev|staging|prod>] [--skip-packaging] [--placeholder-packaging] [--only-common|--only-workshop] [--validate-only] [--run-e2e] [--e2e-url <url>]"
  echo ""
  echo "Options:"
  echo "  --name         Name of the classroom (required)"
  echo "  --cloud        Cloud provider (aws or azure, default: aws)"
  echo "  --region       AWS region (default: eu-west-1)"
  echo "  --location     Azure location (default: centralus)"
  echo "  --destroy      Destroy the classroom resources instead of creating them"
  echo "  --parallelism  Number of parallel operations (default: 4)"
  echo "  --force-unlock Force unlock the state if it's locked"
  echo "  --setup-rbac   Setup RBAC roles for Azure (only for Azure)"
  echo "  --with-pool    Include EC2 instances pool for classroom (AWS only)"
  echo "  --pool-size    Number of EC2 instances in the pool (default: 40, AWS only)"
  echo "  --workshop     Workshop root folder under iac/aws/workshops (default: testus_patronus, AWS only)"
  echo "  --environment  Environment name (default: dev, AWS only)"
  echo "  --skip-packaging Skip Lambda packaging (use existing packages, AWS only)"
  echo "  --placeholder-packaging Create placeholder Lambda archives for validation-only runs (AWS only)"
  echo "  --only-common  Apply/destroy only the common stack (AWS only)"
  echo "  --only-workshop Apply/destroy only the workshop stack (AWS only)"
  echo "  --validate-only Validate deployment without making changes"
  echo "  --run-e2e      Trigger Playwright E2E GitHub workflow after successful create"
  echo "  --e2e-url      Base URL for deployed EC2 manager used by E2E workflow"
  exit 1
}

# Default values
CLASSROOM_NAME=""
CLOUD_PROVIDER="aws"
REGION="eu-west-1"
LOCATION="centralus"
ACTION="create"
PARALLELISM=4
FORCE_UNLOCK=false
SETUP_RBAC=false
WITH_POOL=false
POOL_SIZE=40
WORKSHOP_ROOT="testus_patronus"
SKIP_PACKAGING=false
PLACEHOLDER_PACKAGING=false
ENVIRONMENT="dev"
ONLY_COMMON=false
ONLY_WORKSHOP=false
VALIDATE_ONLY=false
RUN_E2E=false
E2E_URL="https://ec2-management-dev.testingfantasy.com"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --name)
      CLASSROOM_NAME="$2"
      shift 2
      ;;
    --cloud)
      CLOUD_PROVIDER="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --location)
      LOCATION="$2"
      shift 2
      ;;
    --destroy)
      ACTION="destroy"
      shift
      ;;
    --parallelism)
      PARALLELISM="$2"
      shift 2
      ;;
    --force-unlock)
      FORCE_UNLOCK=true
      shift
      ;;
    --setup-rbac)
      SETUP_RBAC=true
      shift
      ;;
    --with-pool)
      WITH_POOL=true
      shift
      ;;
    --pool-size)
      POOL_SIZE="$2"
      shift 2
      ;;
    --workshop)
      WORKSHOP_ROOT="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --skip-packaging)
      SKIP_PACKAGING=true
      shift
      ;;
    --placeholder-packaging)
      PLACEHOLDER_PACKAGING=true
      shift
      ;;
    --only-common)
      ONLY_COMMON=true
      shift
      ;;
    --only-workshop)
      ONLY_WORKSHOP=true
      shift
      ;;
    --validate-only)
      VALIDATE_ONLY=true
      shift
      ;;
    --run-e2e)
      RUN_E2E=true
      shift
      ;;
    --e2e-url)
      E2E_URL="$2"
      shift 2
      ;;
    --help)
      usage
      ;;
    *)
      echo "Unknown parameter: $1"
      usage
      ;;
  esac
done

# Validate required parameters
if [ -z "$CLASSROOM_NAME" ]; then
  echo "Error: Classroom name is required (--name)"
  usage
fi

if [ "$CLOUD_PROVIDER" != "aws" ] && [ "$CLOUD_PROVIDER" != "azure" ]; then
  echo "Error: Cloud provider must be either 'aws' or 'azure'"
  usage
fi

if [ "$ONLY_COMMON" = true ] && [ "$ONLY_WORKSHOP" = true ]; then
  echo "Error: --only-common and --only-workshop cannot be used together"
  usage
fi

if [ "$SKIP_PACKAGING" = true ] && [ "$PLACEHOLDER_PACKAGING" = true ]; then
  echo "Error: --skip-packaging and --placeholder-packaging cannot be used together"
  usage
fi

if [ "$PLACEHOLDER_PACKAGING" = true ] && [ "$VALIDATE_ONLY" != true ]; then
  echo "Error: --placeholder-packaging can only be used with --validate-only"
  usage
fi

if [[ ! "$E2E_URL" =~ ^https?:// ]]; then
  echo "Error: --e2e-url must start with http:// or https://"
  usage
fi

case "$ENVIRONMENT" in
  dev|staging|prod) ;;
  *)
    echo "Error: --environment must be one of: dev, staging, prod"
    usage
    ;;
esac

# Handle cloud-specific setup
if [ "$CLOUD_PROVIDER" = "azure" ]; then
  # Call setup_azure.sh with all necessary parameters
  ./scripts/setup_azure.sh \
    --name "$CLASSROOM_NAME" \
    --location "${LOCATION:-centralus}" \
    --action "${ACTION:-create}" \
    --parallelism "${PARALLELISM:-4}" \
    ${FORCE_UNLOCK:+"--force-unlock"} \
    ${SETUP_RBAC:+"--setup-rbac"} \
    ${VALIDATE_ONLY:+"--validate-only"}
else
  # Infer workshop name from classroom name if not explicitly set and a matching folder exists
  if [ "$WORKSHOP_ROOT" = "testus_patronus" ] && [ -d "iac/aws/workshops/$CLASSROOM_NAME" ]; then
    WORKSHOP_ROOT="$CLASSROOM_NAME"
  fi

  # Call setup_aws.sh with all necessary parameters
  AWS_ARGS=("$CLASSROOM_NAME" "$REGION" "$ACTION")
  if [ "$WITH_POOL" = true ]; then
    AWS_ARGS+=("--with-pool" "--pool-size" "$POOL_SIZE")
  fi
  if [ "$WORKSHOP_ROOT" != "testus_patronus" ]; then
    AWS_ARGS+=("--workshop" "$WORKSHOP_ROOT")
  fi
  if [ "$ENVIRONMENT" != "dev" ]; then
    AWS_ARGS+=("--environment" "$ENVIRONMENT")
  fi
  if [ "$SKIP_PACKAGING" = true ]; then
    AWS_ARGS+=("--skip-packaging")
  fi
  if [ "$PLACEHOLDER_PACKAGING" = true ]; then
    AWS_ARGS+=("--placeholder-packaging")
  fi
  if [ "$ONLY_COMMON" = true ]; then
    AWS_ARGS+=("--only-common")
  fi
  if [ "$ONLY_WORKSHOP" = true ]; then
    AWS_ARGS+=("--only-workshop")
  fi
  if [ "$VALIDATE_ONLY" = true ]; then
    AWS_ARGS+=("--validate-only")
  fi

  # Pre-populate TF_VAR_shared_core_* from the existing Secrets Manager secret so that
  # local re-runs do not wipe the secret when the env vars are not set in the shell.
  _SC_SECRET_ID="/classroom/shared-core/${ENVIRONMENT}/deploy"
  if command -v aws >/dev/null 2>&1; then
    _SC_SECRET_JSON=$(aws secretsmanager get-secret-value \
      --secret-id "$_SC_SECRET_ID" \
      --query SecretString \
      --output text 2>/dev/null || echo "")
    if [ -n "$_SC_SECRET_JSON" ] && [ "$_SC_SECRET_JSON" != "None" ]; then
      if [ -z "${TF_VAR_shared_core_ssh_private_key:-}" ]; then
        _val=$(printf '%s' "$_SC_SECRET_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('ssh_private_key',''))" 2>/dev/null || echo "")
        [ -n "$_val" ] && export TF_VAR_shared_core_ssh_private_key="$_val"
      fi
      if [ -z "${TF_VAR_shared_core_gh_repo_token:-}" ]; then
        _val=$(printf '%s' "$_SC_SECRET_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('gh_repo_token',''))" 2>/dev/null || echo "")
        [ -n "$_val" ] && export TF_VAR_shared_core_gh_repo_token="$_val"
      fi
      if [ -z "${TF_VAR_shared_core_jenkins_admin_password:-}" ]; then
        _val=$(printf '%s' "$_SC_SECRET_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('jenkins_admin_password',''))" 2>/dev/null || echo "")
        [ -n "$_val" ] && export TF_VAR_shared_core_jenkins_admin_password="$_val"
      fi
      if [ -z "${TF_VAR_shared_core_gitea_admin_password:-}" ]; then
        _val=$(printf '%s' "$_SC_SECRET_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('gitea_admin_password',''))" 2>/dev/null || echo "")
        [ -n "$_val" ] && export TF_VAR_shared_core_gitea_admin_password="$_val"
      fi
      echo "✓ Restored shared-core deploy secrets from Secrets Manager (${_SC_SECRET_ID})"
    fi
  fi

  ./scripts/setup_aws.sh "${AWS_ARGS[@]}"

  # Post-deploy: verify the secret is fully populated and warn if not.
  if command -v aws >/dev/null 2>&1 && [ "$ACTION" != "destroy" ]; then
    _SC_SECRET_JSON_POST=$(aws secretsmanager get-secret-value \
      --secret-id "$_SC_SECRET_ID" \
      --query SecretString \
      --output text 2>/dev/null || echo "")
    if [ -z "$_SC_SECRET_JSON_POST" ] || [ "$_SC_SECRET_JSON_POST" = "None" ]; then
      echo "⚠ Warning: Deploy secret '${_SC_SECRET_ID}' does not exist or has no value."
      echo "  Set TF_VAR_shared_core_* env vars before running this script, or set the 4 GitHub"
      echo "  secrets (SHARED_CORE_SSH_PRIVATE_KEY, SHARED_CORE_GH_REPO_TOKEN,"
      echo "  SHARED_CORE_JENKINS_ADMIN_PASSWORD, SHARED_CORE_GITEA_ADMIN_PASSWORD)"
      echo "  in the prod GitHub environment and run deploy-aws.yml."
    else
      _missing_keys=""
      for _key in ssh_private_key gh_repo_token jenkins_admin_password gitea_admin_password; do
        _v=$(printf '%s' "$_SC_SECRET_JSON_POST" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('$_key',''))" 2>/dev/null || echo "")
        [ -z "$_v" ] && _missing_keys="${_missing_keys} ${_key}"
      done
      if [ -n "$_missing_keys" ]; then
        echo "⚠ Warning: Deploy secret '${_SC_SECRET_ID}' is missing values for:${_missing_keys}"
        echo "  Export TF_VAR_shared_core_* env vars and re-run, or populate via deploy-aws.yml."
      else
        echo "✓ Deploy secret '${_SC_SECRET_ID}' is fully populated."
      fi
    fi
  fi
fi

# Final success message
if [ "$ACTION" = "create" ]; then
  echo "Classroom '$CLASSROOM_NAME' has been set up successfully!"
  if [ "$CLOUD_PROVIDER" = "aws" ]; then
    echo "AWS Region: $REGION"
    echo "Lambda Function URL will be available in the Terraform outputs"
  else
    echo "Azure Location: $LOCATION"
    echo "Function URL will be available in the Terraform outputs"
  fi
  echo "Use this URL to create student accounts on demand"

  if [ "$RUN_E2E" = true ]; then
    echo ""
    echo "Triggering Playwright E2E workflow against: $E2E_URL"
    if command -v gh >/dev/null 2>&1; then
      if gh workflow run playwright-e2e.yml -f test_url="$E2E_URL"; then
        echo "Playwright workflow triggered successfully."
      else
        echo "Warning: Failed to trigger Playwright workflow via gh CLI."
        echo "You can run it manually from GitHub Actions with test_url=$E2E_URL"
      fi
    else
      echo "Warning: gh CLI is not installed."
      echo "Run manually: gh workflow run playwright-e2e.yml -f test_url='$E2E_URL'"
    fi
  fi
else
  echo "Classroom '$CLASSROOM_NAME' has been destroyed successfully!"
fi 