#!/bin/bash

# Exit on error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Function to display usage
usage() {
  echo "Usage: $0 <classroom-name> <region> [create|destroy] [--environment <dev|staging|prod>] [--workshop <name>] [--with-pool] [--pool-size <number>] [--skip-packaging] [--only-common|--only-workshop]"
  echo ""
  echo "Arguments:"
  echo "  classroom-name    Name of the classroom (required)"
  echo "  region           AWS region (required)"
  echo "  action           Action to perform: create or destroy (default: create)"
  echo ""
  echo "Options:"
  echo "  --environment    Environment name (default: dev)"
  echo "  --workshop       Workshop root folder under iac/aws/workshops (default: testus_patronus)"
  echo "  --with-pool      Emergency option: Create EC2 instances via Terraform (not recommended)"
  echo "  --pool-size      Emergency option: Number of EC2 instances to create via Terraform (default: 4)"
  echo "  --skip-packaging Skip Lambda function packaging (use existing packages)"
  echo "  --only-common    Apply/destroy only the common stack"
  echo "  --only-workshop  Apply/destroy only the workshop stack"
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

publish_template_map() {
  local templates_param="/classroom/templates/${ENVIRONMENT}"
  local root_module_path="${ROOT_DIR}/iac/aws"
  local templates_json="{}"

  if ! command -v jq >/dev/null 2>&1; then
    echo "Warning: jq not found. Skipping workshop template map publish."
    return 0
  fi

  if [ ! -d "$root_module_path" ]; then
    echo "Warning: Root module directory not found at $root_module_path. Skipping template map publish."
    return 0
  fi

  pushd "$root_module_path" >/dev/null || return 0
  
  # Try to initialize backend if needed
  terraform init -backend=false >/dev/null 2>&1 || terraform init -reconfigure >/dev/null 2>&1
  
  # Get template configs from root module outputs (already includes user_data_base64)
  set +e
  fellowship_template=$(terraform output -json workshop_fellowship_template_config 2>/dev/null || echo "null")
  if [ "$fellowship_template" != "null" ] && [ -n "$fellowship_template" ]; then
    templates_json=$(echo "$templates_json" | jq --arg name "fellowship" --argjson tmpl "$fellowship_template" '. + {($name): $tmpl}')
    echo "  ✓ Added template for workshop: fellowship"
  fi
  
  testus_template=$(terraform output -json workshop_testus_patronus_template_config 2>/dev/null || echo "null")
  if [ "$testus_template" != "null" ] && [ -n "$testus_template" ]; then
    templates_json=$(echo "$templates_json" | jq --arg name "testus_patronus" --argjson tmpl "$testus_template" '. + {($name): $tmpl}')
    echo "  ✓ Added template for workshop: testus_patronus"
  fi
  set -e
  
  popd >/dev/null || true

  # Check if we have any templates to publish
  template_count=$(echo "$templates_json" | jq 'length')
  if [ "$template_count" -eq 0 ]; then
    echo "Warning: No workshop templates found to publish"
    return 0
  fi

  echo "Publishing template map with $template_count workshop(s) to SSM..."
  
  # Use Advanced tier to support larger parameter values (up to 8KB)
  # Standard tier only supports 4KB, which is exceeded when multiple workshops include base64 user_data
  set +e
  aws ssm put-parameter \
    --name "$templates_param" \
    --type "String" \
    --value "$templates_json" \
    --tier "Advanced" \
    --overwrite \
    --region "$REGION" >/dev/null 2>&1
  put_status=$?
  set -e

  if [ $put_status -eq 0 ]; then
    echo "✓ Published workshop template map to SSM (Advanced tier): $templates_param"
    echo "  Workshops in map: $(echo "$templates_json" | jq -r 'keys | join(", ")')"
  else
    echo "✗ Failed to publish template map to SSM. Error code: $put_status"
    echo "  Parameter: $templates_param"
    echo "  JSON size: $(echo "$templates_json" | wc -c) bytes"
    return 1
  fi
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
WORKSHOP_ROOT="testus_patronus"
ENVIRONMENT="dev"
ONLY_COMMON=false
ONLY_WORKSHOP=false

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
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --only-common)
      ONLY_COMMON=true
      shift
      ;;
    --only-workshop)
      ONLY_WORKSHOP=true
      shift
      ;;
    --workshop)
      WORKSHOP_ROOT="$2"
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
if [ -z "$CLASSROOM_NAME" ] || [ -z "$REGION" ]; then
  echo "Error: Classroom name and region are required"
  usage
fi

if [ "$ONLY_COMMON" = true ] && [ "$ONLY_WORKSHOP" = true ]; then
  echo "Error: --only-common and --only-workshop cannot be used together"
  usage
fi

case "$ENVIRONMENT" in
  dev|staging|prod) ;;
  *)
    echo "Error: --environment must be one of: dev, staging, prod"
    usage
    ;;
esac

# Root module path (consolidated infrastructure)
ROOT_MODULE_PATH="iac/aws"

# Check prerequisites
check_prerequisites

# Configure AWS credentials if needed
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS credentials not configured or invalid. Please configure AWS credentials."
  configure_aws
fi

# Set up PATH for local Terraform installation
export PATH="$HOME/.homebrew/bin:$PATH"

# Setup backend infrastructure (single shared backend)
echo "Setting up Terraform backend..."
cd iac/backend/aws

# Use region-specific bucket name to avoid conflicts with recently deleted buckets
# Convert region like "eu-west-1" to "euwest1" for bucket name
REGION_CODE=$(echo "$REGION" | tr -d '-')
BACKEND_BUCKET="terraform-state-classroom-shared-${REGION_CODE}"
BACKEND_TABLE="terraform-locks-classroom-shared"
if [ "$ENVIRONMENT" = "dev" ]; then
  STATE_KEY="classroom/dev/terraform.tfstate"
else
  STATE_KEY="classroom/${ENVIRONMENT}/terraform.tfstate"
fi

terraform init -reconfigure

# Shared backend
terraform workspace select common-backend >/dev/null 2>&1 || terraform workspace new common-backend
  cat > terraform.tfvars << EOF
aws_region         = "$REGION"
state_bucket_name  = "$BACKEND_BUCKET"
dynamodb_table_name = "$BACKEND_TABLE"
EOF
terraform apply -auto-approve
STATE_BUCKET=$(terraform output -raw state_bucket_name)
STATE_TABLE=$(terraform output -raw dynamodb_table_name)

echo "Backend created successfully:"
echo "  S3 Bucket: $STATE_BUCKET"
echo "  DynamoDB Table: $STATE_TABLE"

# Go back to project root
cd "$ROOT_DIR"

# Package Lambda function (conditional)
if [ "$SKIP_PACKAGING" = false ]; then
  echo "Packaging Lambda function..."
  ./scripts/package_lambda.sh --cloud aws
else
  echo "Skipping Lambda function packaging (--skip-packaging specified)"
  
  # Check if packages exist
  if [ ! -d "${ROOT_DIR}/functions/packages" ] || [ -z "$(ls -A "${ROOT_DIR}/functions/packages" 2>/dev/null)" ]; then
    echo "Warning: No Lambda packages found in functions/packages/"
    echo "Run without --skip-packaging to create packages first"
    exit 1
  fi
  
  echo "Using existing Lambda packages from functions/packages/"
fi

# Configure root module backend and apply
echo "Configuring root Terraform module with remote backend..."
cd "${ROOT_DIR}/${ROOT_MODULE_PATH}"

# Update backend configuration
cat > backend.tf << EOF
terraform {
  backend "s3" {
    bucket         = "$STATE_BUCKET"
    key            = "$STATE_KEY"
    region         = "$REGION"
    dynamodb_table = "$STATE_TABLE"
    encrypt        = true
  }
}
EOF

# Update terraform.tfvars with environment
  cat > terraform.tfvars << EOF
environment = "$ENVIRONMENT"
owner = "admin"
region = "$REGION"
EOF

terraform init -reconfigure

# Determine target flags for partial deployments
TARGET_FLAGS=""
if [ "$ONLY_COMMON" = true ]; then
  TARGET_FLAGS="-target=module.common"
elif [ "$ONLY_WORKSHOP" = true ]; then
  # Determine which workshop to target based on WORKSHOP_ROOT
  if [ "$WORKSHOP_ROOT" = "fellowship" ]; then
    TARGET_FLAGS="-target=module.workshop_fellowship"
  elif [ "$WORKSHOP_ROOT" = "testus_patronus" ]; then
    TARGET_FLAGS="-target=module.workshop_testus_patronus"
  else
    echo "Warning: Unknown workshop '$WORKSHOP_ROOT'. Deploying all workshops."
    TARGET_FLAGS="-target=module.workshop_fellowship -target=module.workshop_testus_patronus"
  fi
fi

if [ "$ACTION" = "destroy" ]; then
  if [ -n "$TARGET_FLAGS" ]; then
    terraform destroy -auto-approve $TARGET_FLAGS
  else
  terraform destroy -auto-approve
  fi
  exit 0
else
  if [ -n "$TARGET_FLAGS" ]; then
    terraform apply -auto-approve $TARGET_FLAGS
  else
  terraform apply -auto-approve
  fi
    
    # Build and deploy frontend after common infrastructure is deployed
    echo ""
    echo "Building and deploying React frontend..."
    if command -v npm >/dev/null 2>&1; then
      cd "$ROOT_DIR"
      if [ -d "frontend/ec2-manager" ]; then
        # Check if node_modules exists, if not install dependencies
        if [ ! -d "frontend/ec2-manager/node_modules" ]; then
          echo "Installing npm dependencies..."
          cd frontend/ec2-manager
          npm install
          cd "$ROOT_DIR"
        fi
        
        # Build the React app
        echo "Building React app..."
        cd frontend/ec2-manager
        # Set API URL for production build (environment-specific)
        export VITE_API_URL="https://ec2-management-api-${ENVIRONMENT}.testingfantasy.com/api"
        echo "Using API URL: $VITE_API_URL"
        npm run build
        
        if [ -d "dist" ]; then
          # Verify build output
          BUILT_FILES=$(find dist -type f | wc -l | tr -d ' ')
          if [ "$BUILT_FILES" -eq 0 ]; then
            echo "⚠ Build directory is empty - no files to upload"
            cd "$ROOT_DIR"
            continue
          fi
          echo "Build contains $BUILT_FILES file(s)"
          
          # Check for required files
          if [ ! -f "dist/index.html" ]; then
            echo "⚠ Warning: dist/index.html not found - build may be incomplete"
          fi
          
          # Get S3 bucket name from Terraform
          cd "$ROOT_DIR/${ROOT_MODULE_PATH}"
          S3_BUCKET=$(terraform output -raw instance_manager_s3_bucket_name 2>/dev/null || terraform output -raw s3_frontend_bucket_name 2>/dev/null || echo "")
          
          if [ -n "$S3_BUCKET" ]; then
            echo "Uploading frontend to S3 bucket: $S3_BUCKET"
            cd "$ROOT_DIR/frontend/ec2-manager"
            
            # Sync static assets with cache headers (excluding HTML)
            if ! aws s3 sync dist "s3://$S3_BUCKET" \
              --delete \
              --cache-control "public, max-age=31536000, immutable" \
              --exclude "*.html" \
              --region "$REGION"; then
              echo "✗ Failed to upload static assets to S3"
              cd "$ROOT_DIR"
              continue
            fi
            
            # Upload HTML files with no cache (must be separate to override cache headers)
            if ! aws s3 sync dist "s3://$S3_BUCKET" \
              --cache-control "no-cache, no-store, must-revalidate" \
              --include "*.html" \
              --region "$REGION"; then
              echo "✗ Failed to upload HTML files to S3"
              cd "$ROOT_DIR"
              continue
            fi
            
            # Verify upload success
            echo "Verifying upload..."
            UPLOADED_FILES=$(aws s3 ls "s3://$S3_BUCKET" --recursive --region "$REGION" 2>/dev/null | wc -l | tr -d ' ')
            if [ -z "$UPLOADED_FILES" ]; then
              echo "⚠ Warning: Could not verify uploaded file count"
            elif [ "$UPLOADED_FILES" -lt "$BUILT_FILES" ]; then
              echo "⚠ Warning: Uploaded files ($UPLOADED_FILES) < Built files ($BUILT_FILES)"
            else
              echo "✓ Verified: $UPLOADED_FILES file(s) uploaded to S3"
            fi
            
            echo "✓ Frontend uploaded to S3"
            
            # Invalidate CloudFront cache
            echo "Invalidating CloudFront cache..."
            CLOUDFRONT_DOMAIN="ec2-management-${ENVIRONMENT}.testingfantasy.com"
            CLOUDFRONT_DIST_ID=$(aws cloudfront list-distributions \
              --query "DistributionList.Items[?Aliases.Items[?contains(@, '${CLOUDFRONT_DOMAIN}')]].Id" \
              --output text \
              --region "$REGION" 2>/dev/null || echo "")
            
            if [ -n "$CLOUDFRONT_DIST_ID" ] && [ "$CLOUDFRONT_DIST_ID" != "None" ]; then
              INVALIDATION_ID=$(aws cloudfront create-invalidation \
                --distribution-id "$CLOUDFRONT_DIST_ID" \
                --paths "/*" \
                --query "Invalidation.Id" \
                --output text \
                --region "$REGION" 2>/dev/null || echo "")
              
              if [ -n "$INVALIDATION_ID" ] && [ "$INVALIDATION_ID" != "None" ]; then
                echo "✓ CloudFront cache invalidation created: $INVALIDATION_ID"
              else
                echo "⚠ Could not create CloudFront invalidation (distribution may not be ready yet)"
              fi
            else
              echo "⚠ CloudFront distribution not found (may not be created yet)"
            fi
          else
            echo "⚠ Could not get S3 bucket name from Terraform output"
            echo "  Frontend build completed but not uploaded. Run manually:"
            echo "  ./scripts/build_frontend.sh --environment $ENVIRONMENT --region $REGION"
          fi
        else
          echo "⚠ Build failed - dist directory not found"
        fi
        cd "$ROOT_DIR"
      else
        echo "⚠ Frontend directory not found at frontend/ec2-manager"
      fi
    else
      echo "⚠ npm not found - skipping frontend build"
      echo "  Install Node.js and npm, then run manually:"
      echo "  ./scripts/build_frontend.sh --environment $ENVIRONMENT --region $REGION"
    fi

  # Publish template map (only if not --only-common)
  if [ "$ONLY_COMMON" = false ]; then
    publish_template_map
  fi
    
  # Print the Lambda function URLs
  echo -e "\n=== DEPLOYMENT SUCCESSFUL ==="
  
  if [ "$ONLY_COMMON" = false ]; then
    echo -e "\nInstance Manager Lambda URL (API):"
    INSTANCE_MANAGER_URL=$(terraform output -raw instance_manager_url 2>/dev/null || echo "")
    echo "$INSTANCE_MANAGER_URL"
    echo -e "\n  API Endpoint: $INSTANCE_MANAGER_URL/api"
    
    # Check if CloudFront custom URL is available
    CUSTOM_URL=$(terraform output -raw instance_manager_custom_url 2>/dev/null || echo "")
    if [ -n "$CUSTOM_URL" ] && [ "$CUSTOM_URL" != "null" ]; then
      echo -e "\n  React Frontend (CloudFront): $CUSTOM_URL"
      echo -e "\n  Use the React frontend to create and manage EC2 instances dynamically."
    else
      echo -e "\n  React Frontend: Will be available at CloudFront URL after DNS setup"
      echo -e "\n  Use the React frontend to create and manage EC2 instances dynamically."
    fi
    
    # Workshop-specific outputs
    if [ "$ONLY_COMMON" = false ] && [ -z "$TARGET_FLAGS" ] || echo "$TARGET_FLAGS" | grep -q "workshop_fellowship"; then
      echo -e "\nFellowship Workshop:"
      FELLOWSHIP_URL=$(terraform output -raw fellowship_lambda_function_url 2>/dev/null || echo "")
      echo "  Lambda URL: $FELLOWSHIP_URL"
    fi
    
    if [ "$ONLY_COMMON" = false ] && [ -z "$TARGET_FLAGS" ] || echo "$TARGET_FLAGS" | grep -q "workshop_testus_patronus"; then
      echo -e "\nTestus Patronus Workshop:"
      TESTUS_URL=$(terraform output -raw testus_patronus_lambda_function_url 2>/dev/null || echo "")
      echo "  Lambda URL: $TESTUS_URL"
    fi
  else
    echo -e "\nInstance Manager Lambda URL (API):"
    INSTANCE_MANAGER_URL=$(terraform output -raw instance_manager_url 2>/dev/null || echo "")
    echo "$INSTANCE_MANAGER_URL"
  fi
  
  echo -e "\n\nUse the Instance Manager URL to manage EC2 instances (UI at /ui)\n"
fi 