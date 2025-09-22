#!/bin/bash

# Exit on error
set -e

# Check if required tools are installed
check_prerequisites() {
  command -v terraform >/dev/null 2>&1 || { echo "Terraform is required but not installed. Aborting." >&2; exit 1; }
  command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed. Aborting." >&2; exit 1; }
}

# Function to configure AWS credentials
configure_aws() {
  echo "Configuring AWS credentials..."
  echo "Please enter your AWS Access Key ID:"
  read -r aws_access_key_id
  echo "Please enter your AWS Secret Access Key:"
  read -r -s aws_secret_access_key
  echo "Please enter your AWS region (default: eu-west-1):"
  read -r aws_region
  aws_region=${aws_region:-eu-west-1}
  
  aws configure set aws_access_key_id "$aws_access_key_id"
  aws configure set aws_secret_access_key "$aws_secret_access_key"
  aws configure set region "$aws_region"
  aws configure set output json
}

# Get parameters
CLASSROOM_NAME="$1"
REGION="$2"
ACTION="$3"
CLASSROOM_DIR="classrooms/$CLASSROOM_NAME"

# Check prerequisites
check_prerequisites

# Configure AWS credentials if needed
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials not configured or invalid. Please configure AWS credentials."
  configure_aws
fi

# Copy AWS configuration
#echo "Copying AWS configuration..."
#cp -r iac/aws/* "$CLASSROOM_DIR/"
#mkdir -p "$CLASSROOM_DIR/functions"
#cp -r functions/aws/* "$CLASSROOM_DIR/functions/"

# Package Lambda function
echo "Packaging Lambda function..."
./scripts/package_lambda.sh --cloud aws

# Initialize and apply Terraform
#cd "$CLASSROOM_DIR"
cd iac/aws
if [ "$ACTION" = "destroy" ]; then
  terraform init
  terraform destroy -auto-approve
else
  terraform init
  terraform apply -auto-approve
  
  # Print the status Lambda URL
  echo -e "\nStatus Lambda URL:"
  terraform output -raw status_lambda_url
  echo -e "\n"
fi 