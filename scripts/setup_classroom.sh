#!/bin/bash

# Exit on error
set -e

# Function to display usage
usage() {
  echo "Usage: $0 --name <classroom-name> --cloud [aws|azure] [--region <aws-region>] [--location <azure-location>] [--destroy] [--parallelism <number>] [--force-unlock] [--setup-rbac]"
  echo ""
  echo "Options:"
  echo "  --name         Name of the classroom (required)"
  echo "  --cloud        Cloud provider (aws or azure, default: aws)"
  echo "  --region       AWS region (default: eu-west-3)"
  echo "  --location     Azure location (default: centralus)"
  echo "  --destroy      Destroy the classroom resources instead of creating them"
  echo "  --parallelism  Number of parallel operations (default: 4)"
  echo "  --force-unlock Force unlock the state if it's locked"
  echo "  --setup-rbac   Setup RBAC roles for Azure (only for Azure)"
  exit 1
}

# Default values
CLASSROOM_NAME=""
CLOUD_PROVIDER="aws"
REGION="eu-west-3"
LOCATION="centralus"
ACTION="create"
PARALLELISM=4
FORCE_UNLOCK=false
SETUP_RBAC=false

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

# Handle cloud-specific setup
if [ "$CLOUD_PROVIDER" = "azure" ]; then
  # Call setup_azure.sh with all necessary parameters
  ./scripts/setup_azure.sh \
    --name "$CLASSROOM_NAME" \
    --location "${LOCATION:-centralus}" \
    --action "${ACTION:-create}" \
    --parallelism "${PARALLELISM:-4}" \
    ${FORCE_UNLOCK:+"--force-unlock"} \
    ${SETUP_RBAC:+"--setup-rbac"}
else
  echo "AWS setup not implemented yet"
  exit 1
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
else
  echo "Classroom '$CLASSROOM_NAME' has been destroyed successfully!"
fi 