#!/bin/bash

# Exit on error
set -e

# Function to display usage
usage() {
  echo "Usage: $0 --name <classroom-name> --cloud [aws|azure] [--region <aws-region>] [--location <azure-location>] [--destroy] [--parallelism <number>] [--force-unlock] [--setup-rbac] [--workshop <name>] [--environment <dev|staging|prod>] [--skip-packaging] [--only-common|--only-workshop] [--validate-only] [--run-e2e] [--e2e-url <url>]"
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

  # Always package Lambda before validation, even in --validate-only mode
  if [ "$VALIDATE_ONLY" = true ] && [ "$SKIP_PACKAGING" = false ]; then
    echo "Ensuring Lambda packages exist for validation..."
    ./scripts/package_lambda.sh --cloud aws
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
  if [ "$ONLY_COMMON" = true ]; then
    AWS_ARGS+=("--only-common")
  fi
  if [ "$ONLY_WORKSHOP" = true ]; then
    AWS_ARGS+=("--only-workshop")
  fi
  if [ "$VALIDATE_ONLY" = true ]; then
    AWS_ARGS+=("--validate-only")
  fi
  ./scripts/setup_aws.sh "${AWS_ARGS[@]}"
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