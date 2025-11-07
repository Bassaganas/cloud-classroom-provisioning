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
  echo "  --with-pool      Emergency option: Create EC2 instances via Terraform (not recommended)"
  echo "  --pool-size      Emergency option: Number of EC2 instances to create via Terraform (default: 4)"
  echo "  --skip-packaging Skip Lambda function packaging (use existing packages)"
  echo "  --help           Show this help message"
  echo ""
  echo "Note: EC2 instances are normally created dynamically via the instance_manager Lambda function."
  echo "      After deployment, use the Instance Manager URL at /ui to create and manage instances."
  echo "      --with-pool is an EMERGENCY OPTION only. Use Lambda UI for normal operations."
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
POOL_SIZE=4  # Default for emergency option
SKIP_PACKAGING=false

# Shift past the required arguments
shift 3 2>/dev/null || true

# Parse optional arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --with-pool)
      echo "WARNING: --with-pool is an EMERGENCY OPTION only."
      echo "         Normally, EC2 instances should be created via the instance_manager Lambda UI at /ui"
      echo "         This option creates instances via Terraform (not recommended for normal use)"
      WITH_POOL=true
      shift
      ;;
    --pool-size)
      echo "WARNING: --pool-size is an EMERGENCY OPTION only."
      echo "         Normally, use the Lambda Function URL at /ui to create instances dynamically."
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

# Create terraform.tfvars
# Set ec2_pool_size based on --with-pool option (emergency option only)
if [ "$WITH_POOL" = true ]; then
  echo "EMERGENCY MODE: Creating $POOL_SIZE EC2 instances via Terraform"
  cat > terraform.tfvars << EOF
classroom_name = "$CLASSROOM_NAME"
environment = "dev"
region = "$REGION"
ec2_pool_size = $POOL_SIZE
EOF
else
  echo "Normal mode: EC2 instances will be created via the instance_manager Lambda function"
  cat > terraform.tfvars << EOF
classroom_name = "$CLASSROOM_NAME"
environment = "dev"
region = "$REGION"
ec2_pool_size = 0
EOF
fi

echo "Note: After deployment, use the Instance Manager URL at /ui to create and manage instances."

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
  echo -e "\n\nInstance Manager Lambda URL:"
  INSTANCE_MANAGER_URL=$(terraform output -raw instance_manager_url)
  echo "$INSTANCE_MANAGER_URL"
  echo -e "\n  Frontend UI: $INSTANCE_MANAGER_URL/ui"
  echo -e "\n  Use the frontend UI to create and manage EC2 instances dynamically."
  
  echo -e "\n\n=== CLOUDFRONT CUSTOM DOMAINS ==="
  echo ""
  
  # Check certificate validation records
  echo "📋 ACM Certificate Validation Records:"
  echo ""
  echo "  Instance Manager (ec2-management.testingfantasy.com):"
  INSTANCE_MGR_VALIDATION=$(terraform output -json instance_manager_acm_certificate_validation_records 2>/dev/null | jq -r '.[0] | "\(.resource_record_name) -> \(.resource_record_value)"' 2>/dev/null || echo "  (No validation records found)")
  echo "    $INSTANCE_MGR_VALIDATION"
  echo ""
  echo "  User Management (testus-patronus.testingfantasy.com):"
  USER_MGMT_VALIDATION=$(terraform output -json user_management_acm_certificate_validation_records 2>/dev/null | jq -r '.[0] | "\(.resource_record_name) -> \(.resource_record_value)"' 2>/dev/null || echo "  (No validation records found)")
  echo "    $USER_MGMT_VALIDATION"
  echo ""
  echo "  Dify Jira API (dify-jira.testingfantasy.com):"
  DIFY_JIRA_VALIDATION=$(terraform output -json dify_jira_acm_certificate_validation_records 2>/dev/null | jq -r '.[0] | "\(.resource_record_name) -> \(.resource_record_value)"' 2>/dev/null || echo "  (No validation records found)")
  echo "    $DIFY_JIRA_VALIDATION"
  echo ""
  
  # Check CloudFront status
  CUSTOM_URL=$(terraform output -raw instance_manager_custom_url 2>/dev/null || echo "null")
  CLOUDFRONT_DOMAIN=$(terraform output -raw instance_manager_cloudfront_domain 2>/dev/null || echo "null")
  USER_MGMT_CUSTOM_URL=$(terraform output -raw user_management_custom_url 2>/dev/null || echo "null")
  USER_MGMT_CF_DOMAIN=$(terraform output -raw user_management_cloudfront_domain 2>/dev/null || echo "null")
  DIFY_JIRA_CUSTOM_URL=$(terraform output -raw dify_jira_custom_url 2>/dev/null || echo "null")
  DIFY_JIRA_CF_DOMAIN=$(terraform output -raw dify_jira_cloudfront_domain 2>/dev/null || echo "null")
  
  # Determine deployment status
  INSTANCE_MGR_CF_CREATED=false
  USER_MGMT_CF_CREATED=false
  DIFY_JIRA_CF_CREATED=false
  
  if [ "$CLOUDFRONT_DOMAIN" != "null" ] && [ -n "$CLOUDFRONT_DOMAIN" ]; then
    INSTANCE_MGR_CF_CREATED=true
  fi
  
  if [ "$USER_MGMT_CF_DOMAIN" != "null" ] && [ -n "$USER_MGMT_CF_DOMAIN" ]; then
    USER_MGMT_CF_CREATED=true
  fi
  
  if [ "$DIFY_JIRA_CF_DOMAIN" != "null" ] && [ -n "$DIFY_JIRA_CF_DOMAIN" ]; then
    DIFY_JIRA_CF_CREATED=true
  fi
  
  echo "🌐 CloudFront Distribution Status:"
  echo ""
  echo "  Instance Manager:"
  if [ "$INSTANCE_MGR_CF_CREATED" = true ]; then
    echo "    ✅ CloudFront Distribution: $CLOUDFRONT_DOMAIN"
    echo "    ✅ Custom URL: $CUSTOM_URL"
    echo "    ✅ Access at: $CUSTOM_URL/ui"
  else
    echo "    ⏳ CloudFront Distribution: Not created yet"
    echo "    ⏳ Custom URL: $CUSTOM_URL (will work after DNS setup)"
    echo "    ℹ️  Status: Waiting for certificate validation and DNS setup"
  fi
  echo ""
  echo "  User Management:"
  if [ "$USER_MGMT_CF_CREATED" = true ]; then
    echo "    ✅ CloudFront Distribution: $USER_MGMT_CF_DOMAIN"
    echo "    ✅ Custom URL: $USER_MGMT_CUSTOM_URL"
    echo "    ✅ Access at: $USER_MGMT_CUSTOM_URL"
  else
    echo "    ⏳ CloudFront Distribution: Not created yet"
    echo "    ⏳ Custom URL: $USER_MGMT_CUSTOM_URL (will work after DNS setup)"
    echo "    ℹ️  Status: Waiting for certificate validation and DNS setup"
  fi
  echo ""
  echo "  Dify Jira API:"
  if [ "$DIFY_JIRA_CF_CREATED" = true ]; then
    echo "    ✅ CloudFront Distribution: $DIFY_JIRA_CF_DOMAIN"
    echo "    ✅ Custom URL: $DIFY_JIRA_CUSTOM_URL"
    echo "    ✅ Access at: $DIFY_JIRA_CUSTOM_URL"
  else
    echo "    ⏳ CloudFront Distribution: Not created yet"
    echo "    ⏳ Custom URL: $DIFY_JIRA_CUSTOM_URL (will work after DNS setup)"
    echo "    ℹ️  Status: Waiting for certificate validation and DNS setup"
  fi
  echo ""
  
  # Provide step-by-step instructions
  echo "📝 DEPLOYMENT STEPS FOR CLOUDFRONT:"
  echo ""
  echo "  STEP 1: Add DNS Validation Records to GoDaddy"
  echo "    └─ These records validate the SSL certificates"
  echo "    └─ Go to GoDaddy DNS Management for testingfantasy.com"
  echo "    └─ Add CNAME records shown above"
  echo "    └─ Wait 5-10 minutes for validation"
  echo ""
  
  if [ "$INSTANCE_MGR_CF_CREATED" = false ] || [ "$USER_MGMT_CF_CREATED" = false ] || [ "$DIFY_JIRA_CF_CREATED" = false ]; then
    echo "  STEP 2: Enable CloudFront Distribution Creation"
    echo "    └─ Edit: iac/aws/main.tf"
    echo "    └─ Set wait_for_certificate_validation = true for the module(s) you want"
    echo "    └─ Currently:"
    INSTANCE_MGR_WAIT=$(grep -A 10 "module \"cloudfront_instance_manager\"" iac/aws/main.tf | grep "wait_for_certificate_validation" | awk '{print $3}' || echo "unknown")
    USER_MGMT_WAIT=$(grep -A 10 "module \"cloudfront_user_management\"" iac/aws/main.tf | grep "wait_for_certificate_validation" | awk '{print $3}' || echo "unknown")
    DIFY_JIRA_WAIT=$(grep -A 10 "module \"cloudfront_dify_jira\"" iac/aws/main.tf | grep "wait_for_certificate_validation" | awk '{print $3}' || echo "unknown")
    echo "      • Instance Manager: $INSTANCE_MGR_WAIT"
    echo "      • User Management: $USER_MGMT_WAIT"
    echo "      • Dify Jira API: $DIFY_JIRA_WAIT"
    echo ""
    echo "  STEP 3: Create CloudFront Distributions"
    echo "    └─ Run: cd iac/aws && terraform apply"
    echo "    └─ This will create the CloudFront distributions"
    echo ""
  fi
  
  if [ "$INSTANCE_MGR_CF_CREATED" = true ] || [ "$USER_MGMT_CF_CREATED" = true ] || [ "$DIFY_JIRA_CF_CREATED" = true ]; then
    echo "  STEP 4: Add Final DNS CNAME Records to GoDaddy"
    echo "    └─ Point your custom domains to CloudFront:"
    if [ "$INSTANCE_MGR_CF_CREATED" = true ]; then
      echo "      • Name: ec2-management"
      echo "        Type: CNAME"
      echo "        Value: $CLOUDFRONT_DOMAIN"
      echo "        TTL: 600"
    fi
    if [ "$USER_MGMT_CF_CREATED" = true ]; then
      echo "      • Name: testus-patronus"
      echo "        Type: CNAME"
      echo "        Value: $USER_MGMT_CF_DOMAIN"
      echo "        TTL: 600"
    fi
    if [ "$DIFY_JIRA_CF_CREATED" = true ]; then
      echo "      • Name: dify-jira"
      echo "        Type: CNAME"
      echo "        Value: $DIFY_JIRA_CF_DOMAIN"
      echo "        TTL: 600"
    fi
    echo ""
    echo "  STEP 5: Wait for DNS Propagation (5-15 minutes)"
    echo "    └─ Then access your custom domains:"
    if [ "$INSTANCE_MGR_CF_CREATED" = true ]; then
      echo "      • Instance Manager: $CUSTOM_URL/ui"
    fi
    if [ "$USER_MGMT_CF_CREATED" = true ]; then
      echo "      • User Management: $USER_MGMT_CUSTOM_URL"
    fi
    if [ "$DIFY_JIRA_CF_CREATED" = true ]; then
      echo "      • Dify Jira API: $DIFY_JIRA_CUSTOM_URL" + "/docs"
    fi
    echo ""
  fi
  
  if [ "$WITH_POOL" = true ]; then
    echo -e "\n\nEMERGENCY MODE: EC2 Pool Information (created via Terraform):"
    echo "Pool Size: $POOL_SIZE instances"
    terraform output pool_instance_ids 2>/dev/null || echo "  (No instances created)"
    terraform output pool_instance_private_ips 2>/dev/null || echo "  (No instances created)"
  fi
  
  echo -e "\n\nUse the User Management URL to create student accounts on demand"
  echo -e "Use the Status URL to check the status of instances and users"
  echo -e "Use the Instance Manager URL to manage EC2 instances (UI at /ui)\n"
fi 