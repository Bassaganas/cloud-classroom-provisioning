#!/bin/bash

# Exit on error
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Function to display usage
usage() {
  echo "Usage: $0 <classroom-name> <region> [create|destroy] [--environment <dev|staging|prod>] [--workshop <name>] [--with-pool] [--pool-size <number>] [--skip-packaging] [--only-common|--only-workshop] [--validate-only]"
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
  echo "  --validate-only  Validate deployment without making changes"
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
  
  # Store each workshop template in a separate parameter to avoid size limits
  # Advanced tier supports up to 8KB per parameter, but combined templates exceed this
  set +e
  publish_success=true
  
  # Publish each workshop template individually
  for workshop_name in $(echo "$templates_json" | jq -r 'keys[]'); do
    workshop_template=$(echo "$templates_json" | jq --arg name "$workshop_name" '.[$name]')
    workshop_param="${templates_param}/${workshop_name}"
    
    # Check template size before publishing
    template_size=$(echo "$workshop_template" | wc -c)
    if [ "$template_size" -gt 8192 ]; then
      echo "  ✗ Template for workshop '$workshop_name' is too large: ${template_size} bytes (max: 8192 bytes)"
      echo "     This exceeds SSM Parameter Store Advanced tier limit (8KB)"
      echo "     Consider reducing user_data.sh script size or using S3 for user_data storage"
      publish_success=false
      continue
    fi
    
    # Try to publish with error capture
    set +e
    publish_output=$(aws ssm put-parameter \
      --name "$workshop_param" \
      --type "String" \
      --value "$workshop_template" \
      --tier "Advanced" \
      --overwrite \
      --region "$REGION" 2>&1)
    publish_exit_code=$?
    set -e
    
    if [ $publish_exit_code -eq 0 ]; then
      echo "  ✓ Published template for workshop: $workshop_name (${template_size} bytes)"
    else
      echo "  ✗ Failed to publish template for workshop: $workshop_name"
      echo "     Error: $publish_output"
      echo "     Template size: ${template_size} bytes"
      publish_success=false
    fi
  done
  
  # Also publish the combined map for backward compatibility (if it fits)
  # Note: Lambda now prioritizes individual parameters, so combined map is only used as fallback
  json_size=$(echo "$templates_json" | wc -c)
  if [ "$json_size" -le 8192 ]; then
    if aws ssm put-parameter \
      --name "$templates_param" \
      --type "String" \
      --value "$templates_json" \
      --tier "Advanced" \
      --overwrite \
      --region "$REGION" >/dev/null 2>&1; then
      echo "  ✓ Published combined template map (backward compatibility, Lambda prioritizes individual parameters)"
    else
      echo "  ⚠ Combined template map too large ($json_size bytes), using individual parameters only"
    fi
  else
    echo "  ⚠ Combined template map too large ($json_size bytes), using individual parameters only"
    echo "  Note: Old combined map may still exist - Lambda will use individual parameters instead"
  fi
  
  set -e

  if [ "$publish_success" = true ]; then
    echo "✓ Published workshop templates to SSM (Advanced tier)"
    echo "  Individual parameters: ${templates_param}/{workshop_name}"
    return 0
  else
    echo "✗ Failed to publish some workshop templates to SSM"
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

# Function to upload workshop setup scripts to S3
upload_sut_to_s3() {
  # Skip if only common infrastructure was deployed
  if [ "$ONLY_COMMON" = true ]; then
    return 0
  fi

  # Determine which workshops to upload for
  # If --only-workshop is used, only upload for that workshop
  # Otherwise, try to upload for both if they exist
  WORKSHOPS_TO_UPLOAD=""
  
  if [ "$ONLY_WORKSHOP" = true ]; then
    # Only upload for the specified workshop
    if [ "$WORKSHOP_ROOT" = "fellowship" ] || [ "$WORKSHOP_ROOT" = "fellowship-of-the-build" ] || [ "$WORKSHOP_ROOT" = "testus_patronus" ]; then
      WORKSHOPS_TO_UPLOAD="$WORKSHOP_ROOT"
    else
      echo "Warning: Workshop '$WORKSHOP_ROOT' does not require S3 upload, skipping"
      return 0
    fi
  else
    # Upload for all workshops that were deployed
    # Check which workshop modules exist in Terraform outputs
    cd "${ROOT_DIR}/${ROOT_MODULE_PATH}"
    
    # Check for fellowship
    if terraform output -raw sut_bucket_name >/dev/null 2>&1; then
      WORKSHOPS_TO_UPLOAD="${WORKSHOPS_TO_UPLOAD} fellowship"
    fi
    
    # Check for testus_patronus
    if terraform output -raw testus_patronus_sut_bucket_name >/dev/null 2>&1; then
      WORKSHOPS_TO_UPLOAD="${WORKSHOPS_TO_UPLOAD} testus_patronus"
    fi
    
    if [ -z "$WORKSHOPS_TO_UPLOAD" ]; then
      echo "Warning: No workshop S3 buckets found in Terraform outputs, skipping upload"
      return 0
    fi
  fi

  # Upload for each workshop
  for WORKSHOP in $WORKSHOPS_TO_UPLOAD; do
    echo ""
    if [ "$WORKSHOP" = "testus_patronus" ]; then
      echo "Uploading Testus Patronus setup script to S3..."
    else
      echo "Uploading Fellowship SUT to S3..."
    fi
    
    # Get bucket name from Terraform output with retry logic
    cd "${ROOT_DIR}/${ROOT_MODULE_PATH}"
    SUT_BUCKET=""
    MAX_RETRIES=5
    RETRY_DELAY=2
    
    for i in $(seq 1 $MAX_RETRIES); do
      if [ "$WORKSHOP" = "testus_patronus" ]; then
        # For testus_patronus, get bucket from workshop_testus_patronus module
        SUT_BUCKET=$(terraform output -raw testus_patronus_sut_bucket_name 2>/dev/null || echo "")
      else
        # For fellowship, get bucket from workshop_fellowship module
        SUT_BUCKET=$(terraform output -raw sut_bucket_name 2>/dev/null || echo "")
      fi
      
      if [ -n "$SUT_BUCKET" ] && [ "$SUT_BUCKET" != "" ]; then
        break
      fi
      
      if [ $i -lt $MAX_RETRIES ]; then
        echo "  Waiting for Terraform output to be available (attempt $i/$MAX_RETRIES)..."
        sleep $RETRY_DELAY
      fi
    done
    
    if [ -z "$SUT_BUCKET" ] || [ "$SUT_BUCKET" = "" ]; then
      echo "✗ Error: SUT bucket not found in Terraform outputs for workshop '$WORKSHOP'"
      echo "  Expected output: $([ "$WORKSHOP" = "testus_patronus" ] && echo "testus_patronus_sut_bucket_name" || echo "sut_bucket_name")"
      echo "  This may indicate the workshop module was not deployed or the output is not available yet"
      continue
    fi
    
    # Verify bucket exists in S3
    if ! aws s3 ls "s3://${SUT_BUCKET}" --region "$REGION" >/dev/null 2>&1; then
      echo "✗ Error: S3 bucket '$SUT_BUCKET' does not exist or is not accessible"
      echo "  Verify the bucket was created by Terraform"
      continue
    fi
    echo "  ✓ Found S3 bucket: $SUT_BUCKET"

    # Fellowship-specific: Upload SUT tarball
    if [ "$WORKSHOP" = "fellowship" ] || [ "$WORKSHOP" = "fellowship-of-the-build" ]; then
      SUT_DIR="${ROOT_DIR}/iac/aws/workshops/fellowship/fellowship-sut"
      TARBALL="/tmp/fellowship-sut.tar.gz"

      # Check if SUT directory exists
      if [ ! -d "$SUT_DIR" ]; then
        echo "  Warning: SUT directory not found at $SUT_DIR, skipping SUT tarball upload"
      else
        # Create tarball (exclude common ignore patterns)
        echo "  Packaging SUT..."
        if ! tar -czf "$TARBALL" \
          --exclude='.git' \
          --exclude='node_modules' \
          --exclude='__pycache__' \
          --exclude='*.pyc' \
          --exclude='.pytest_cache' \
          --exclude='*.db' \
          --exclude='.DS_Store' \
          --exclude='dist' \
          --exclude='build' \
          -C "$(dirname "$SUT_DIR")" \
          "$(basename "$SUT_DIR")" 2>/dev/null; then
          echo "  ✗ Failed to create SUT tarball"
          rm -f "$TARBALL"
          continue
        fi

        # Upload SUT tarball to S3
        echo "  Uploading SUT to s3://${SUT_BUCKET}/fellowship-sut.tar.gz..."
        if ! aws s3 cp "$TARBALL" "s3://${SUT_BUCKET}/fellowship-sut.tar.gz" --region "$REGION"; then
          echo "  ✗ Failed to upload SUT to S3"
          rm -f "$TARBALL"
          continue
        fi
        echo "  ✓ SUT uploaded successfully to s3://${SUT_BUCKET}/fellowship-sut.tar.gz"
        rm -f "$TARBALL"
      fi
    fi

    # Upload setup script to S3 (for both workshops)
    if [ "$WORKSHOP" = "testus_patronus" ]; then
      SETUP_SCRIPT="${ROOT_DIR}/iac/aws/workshops/testus_patronus/setup_testus_patronus.sh"
      S3_KEY="setup_testus_patronus.sh"
    else
      SETUP_SCRIPT="${ROOT_DIR}/iac/aws/workshops/fellowship/setup_fellowship.sh"
      S3_KEY="setup_fellowship.sh"
    fi
    
    if [ ! -f "$SETUP_SCRIPT" ]; then
      if [ "$WORKSHOP" = "fellowship" ] || [ "$WORKSHOP" = "fellowship-of-the-build" ]; then
        echo "  ℹ Fellowship setup script is managed by the external SUT repository; skipping local upload"
      else
        echo "  ✗ Error: Setup script not found at $SETUP_SCRIPT"
        echo "  Expected location: $SETUP_SCRIPT"
      fi
      continue
    fi
    
    echo "  Uploading setup script to s3://${SUT_BUCKET}/${S3_KEY}..."
    if ! aws s3 cp "$SETUP_SCRIPT" "s3://${SUT_BUCKET}/${S3_KEY}" --region "$REGION"; then
      echo "  ✗ Failed to upload setup script to S3"
      echo "  Verify AWS credentials and S3 bucket permissions"
      continue
    fi
    echo "  ✓ Setup script uploaded successfully to s3://${SUT_BUCKET}/${S3_KEY}"
    
    # Verify upload by checking if file exists in S3
    if aws s3 ls "s3://${SUT_BUCKET}/${S3_KEY}" --region "$REGION" >/dev/null 2>&1; then
      echo "  ✓ Verified: Setup script exists in S3"
    else
      echo "  ⚠ Warning: Could not verify setup script exists in S3 (upload may have failed)"
    fi
  done
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
VALIDATE_ONLY=false

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
    --validate-only)
      VALIDATE_ONLY=true
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

# Make backend bootstrap idempotent: import existing resources before apply
BUCKET_EXISTS=false
TABLE_EXISTS=false

if aws s3api head-bucket --bucket "$BACKEND_BUCKET" >/dev/null 2>&1; then
  BUCKET_EXISTS=true
  echo "Detected existing backend bucket: $BACKEND_BUCKET"
fi

if aws dynamodb describe-table --table-name "$BACKEND_TABLE" --region "$REGION" >/dev/null 2>&1; then
  TABLE_EXISTS=true
  echo "Detected existing backend lock table: $BACKEND_TABLE"
fi

if [ "$BUCKET_EXISTS" = true ]; then
  terraform import aws_s3_bucket.terraform_state "$BACKEND_BUCKET" >/dev/null 2>&1 || true
fi

if [ "$TABLE_EXISTS" = true ]; then
  terraform import aws_dynamodb_table.terraform_locks "$BACKEND_TABLE" >/dev/null 2>&1 || true
fi

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

# Always package Lambda before validation, even in --validate-only mode
if [ "$VALIDATE_ONLY" = true ] && [ "$SKIP_PACKAGING" = false ]; then
  echo "Ensuring Lambda packages exist for validation..."
  ./scripts/package_lambda.sh --cloud aws
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
  # Run plan to show what will be applied
  echo "Running Terraform plan..."
  if [ -n "$TARGET_FLAGS" ]; then
    terraform plan -no-color $TARGET_FLAGS
  else
    terraform plan -no-color
  fi

  # If validation only, exit here
  if [ "$VALIDATE_ONLY" = true ]; then
    echo ""
    echo "✓ Validation completed successfully!"
    echo "Terraform plan shows the planned changes above."
    echo "Run without --validate-only to apply these changes."
    exit 0
  fi

  # Apply the plan
  if [ -n "$TARGET_FLAGS" ]; then
    terraform apply -auto-approve $TARGET_FLAGS
  else
  terraform apply -auto-approve
  fi
    
    # Upload workshop setup scripts to S3 (for fellowship and/or testus_patronus)
    upload_sut_to_s3
    
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