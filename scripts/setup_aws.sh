#!/bin/bash

# Exit on error
set -e

# Function to display usage
usage() {
  echo "Usage: $0 <classroom-name> <region> [create|destroy] [--with-pool] [--pool-size <number>] [--skip-packaging]"
  echo ""
  echo "Arguments:"
  echo "  classroom-name    Name of the classroom (required)"
  echo "  region           AWS region (required)"
  echo "  action           Action to perform: create or destroy (default: create)"
  echo ""
  echo "Options:"
  echo "  --with-pool      Include EC2 instances pool for classroom"
  echo "  --pool-size      Number of EC2 instances in the pool (default: 4)"
  echo "  --skip-packaging Skip Lambda function packaging (use existing packages)"
  echo "  --help           Show this help message"
  exit 1
}

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

# Parse command line arguments
CLASSROOM_NAME="$1"
REGION="$2"
ACTION="${3:-create}"
WITH_POOL=false
POOL_SIZE=4
SKIP_PACKAGING=false

# Shift past the required arguments
shift 3 2>/dev/null || true

# Parse optional arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --with-pool)
      WITH_POOL=true
      shift
      ;;
    --pool-size)
      POOL_SIZE="$2"
      shift 2
      ;;
    --skip-packaging)
      SKIP_PACKAGING=true
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
if [ -z "$CLASSROOM_NAME" ] || [ -z "$REGION" ]; then
  echo "Error: Classroom name and region are required"
  usage
fi

CLASSROOM_DIR="classrooms/$CLASSROOM_NAME"

# Check prerequisites
check_prerequisites

# Configure AWS credentials if needed
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials not configured or invalid. Please configure AWS credentials."
  configure_aws
fi

# Set up PATH for local Terraform installation
export PATH="$HOME/.homebrew/bin:$PATH"

# Setup backend infrastructure first
echo "Setting up Terraform backend..."
cd iac/backend/aws

# Create terraform.tfvars if it doesn't exist
if [ ! -f terraform.tfvars ]; then
  echo "Creating backend configuration..."
  cat > terraform.tfvars << EOF
aws_region         = "$REGION"
state_bucket_name  = "terraform-state-${CLASSROOM_NAME}-$(date +%s)"
dynamodb_table_name = "terraform-locks-${CLASSROOM_NAME}"
EOF
fi

# Initialize and apply backend
terraform init
terraform apply -auto-approve

# Get backend configuration
BUCKET_NAME=$(terraform output -raw state_bucket_name)
DYNAMODB_TABLE=$(terraform output -raw dynamodb_table_name)

echo "Backend created successfully:"
echo "  S3 Bucket: $BUCKET_NAME"
echo "  DynamoDB Table: $DYNAMODB_TABLE"

# Go back to project root
cd ../../..

# Package Lambda function (conditional)
if [ "$SKIP_PACKAGING" = false ]; then
  echo "Packaging Lambda function..."
  ./scripts/package_lambda.sh --cloud aws
else
  echo "Skipping Lambda function packaging (--skip-packaging specified)"
  
  # Check if packages exist
  if [ ! -d "functions/packages" ] || [ -z "$(ls -A functions/packages 2>/dev/null)" ]; then
    echo "Warning: No Lambda packages found in functions/packages/"
    echo "Run without --skip-packaging to create packages first"
    exit 1
  fi
  
  echo "Using existing Lambda packages from functions/packages/"
fi

# Configure main Terraform with backend
echo "Configuring main Terraform with remote backend..."
cd iac/aws

# Create backend configuration
cat > backend.tf << EOF
terraform {
  backend "s3" {
    bucket         = "$BUCKET_NAME"
    key            = "classroom/$CLASSROOM_NAME/terraform.tfstate"
    region         = "$REGION"
    dynamodb_table = "$DYNAMODB_TABLE"
    encrypt        = true
  }
}
EOF

# Create terraform.tfvars for pool configuration
cat > terraform.tfvars << EOF
classroom_name = "$CLASSROOM_NAME"
environment = "dev"
region = "$REGION"
ec2_pool_size = $POOL_SIZE
EOF

# Add pool size override if --with-pool is not specified
if [ "$WITH_POOL" = false ]; then
  echo "ec2_pool_size = 0" >> terraform.tfvars
  echo "Note: EC2 pool disabled. Use --with-pool to enable instance pool."
fi

if [ "$ACTION" = "destroy" ]; then
  terraform init
  terraform destroy -auto-approve
else
  terraform init
  terraform apply -auto-approve
  
  # Print the Lambda function URLs
  echo -e "\n=== DEPLOYMENT SUCCESSFUL ==="
  echo -e "\nUser Management Lambda URL:"
  terraform output -raw lambda_function_url
  echo -e "\n\nStatus Lambda URL:"
  terraform output -raw status_lambda_url
  
  if [ "$WITH_POOL" = true ]; then
    echo -e "\n\nEC2 Pool Information:"
    echo "Pool Size: $POOL_SIZE instances"
    terraform output pool_instance_ids
  fi
  
  echo -e "\n\nUse the User Management URL to create student accounts on demand"
  echo -e "Use the Status URL to check the status of instances and users\n"
fi 