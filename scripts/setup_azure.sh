#!/bin/bash

# Exit on error
set -e

# Function to display usage
usage() {
  echo "Usage: $0 --name <classroom-name> --location <azure-location> --action [create|destroy] [--parallelism <number>] [--force-unlock] [--setup-rbac] [--validate-only]"
  exit 1
}

# Check prerequisites
check_prerequisites() {
  command -v terraform >/dev/null 2>&1 || { echo "Terraform is required but not installed. Aborting." >&2; exit 1; }
  command -v az >/dev/null 2>&1 || { echo "Azure CLI is required but not installed. Aborting." >&2; exit 1; }
}

# Function to configure Azure login
configure_azure() {
  echo "Configuring Azure login..."
  if ! az account show >/dev/null 2>&1; then
    az login
  fi
  
  # Get subscription ID and tenant ID
  SUBSCRIPTION_ID=$(az account show --query id -o tsv)
  TENANT_ID=$(az account show --query tenantId -o tsv)
  
  if [ -z "$SUBSCRIPTION_ID" ] || [ -z "$TENANT_ID" ]; then
    echo "Error: Could not get subscription or tenant ID"
    exit 1
  fi
  
  # Export for Terraform
  export ARM_SUBSCRIPTION_ID="$SUBSCRIPTION_ID"
  export ARM_TENANT_ID="$TENANT_ID"
}

# Function to setup and run Terraform
run_terraform() {
  local action=$1
  local classroom_name=$2
  local parallelism=$3
  local validate_only=$4
  
  # First setup state backend
  echo "Setting up Terraform state backend..."
  cd iac/azure/state
  terraform init
  terraform apply -auto-approve
  
  # Get state storage details
  STORAGE_ACCOUNT=$(terraform output -raw storage_account_name)
  STORAGE_KEY=$(terraform output -raw storage_account_key)
  
  # Move to main Terraform directory
  cd ../
  
  # Initialize with backend config
  echo "Initializing Terraform with Azure storage backend..."
  terraform init \
    -backend-config="storage_account_name=$STORAGE_ACCOUNT" \
    -backend-config="container_name=tfstate" \
    -backend-config="key=${classroom_name}.tfstate" \
    -backend-config="resource_group_name=terraform-state-rg" \
    -backend-config="access_key=$STORAGE_KEY" \
    -backend=true
  
  # Run Terraform plan first
  echo "Running Terraform plan..."
  terraform plan -no-color -parallelism="$parallelism"
  
  # If validation only, exit here
  if [ "$validate_only" = true ]; then
    echo ""
    echo "✓ Validation completed successfully!"
    echo "Terraform plan shows the planned changes above."
    echo "Run without --validate-only to apply these changes."
    cd - > /dev/null
    return 0
  fi
  
  # Run Terraform apply/destroy
  if [ "$action" = "destroy" ]; then
    terraform destroy -auto-approve -parallelism="$parallelism"
  else
    terraform apply -auto-approve -parallelism="$parallelism"
    
    # Get outputs for app settings
    FUNCTION_APP_NAME=$(terraform output -raw function_app_name)
    RESOURCE_GROUP_NAME=$(terraform output -raw resource_group_name)
    KEY_VAULT_NAME=$(terraform output -raw key_vault_name)
    
    # Wait for Key Vault propagation
    echo "Waiting for Key Vault and secrets to be fully provisioned..."
    sleep 30
    
    # Update function app settings
    update_function_app_settings "$FUNCTION_APP_NAME" "$RESOURCE_GROUP_NAME" "$KEY_VAULT_NAME"
    
    # Deploy the Azure Function
    echo "Deploying Azure Function..."
    echo "Current directory: $(pwd)"
    ls -la
    cd ../..
    ls -la
    cd scripts
    ./deploy_azure_function.sh \
      --name "$FUNCTION_APP_NAME" \
      --resource-group "$RESOURCE_GROUP_NAME" \
    cd - > /dev/null
  fi
  echo "Deployed Azure Function from setup_azure.sh"
  cd - > /dev/null
}

# Function to update app settings
update_function_app_settings() {
  local FUNCTION_APP_NAME=$1
  local RESOURCE_GROUP_NAME=$2
  local KEY_VAULT_NAME=$3
  
  echo "Updating function app settings..."
  set +e  # Temporarily disable exit on error
  
  # Get the actual values from Terraform outputs
  local TERRAFORM_CLIENT_ID=$(terraform output -raw terraform_client_id)
  local TERRAFORM_CLIENT_SECRET=$(terraform output -raw terraform_client_secret)
  
  az functionapp config appsettings set \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --settings \
    "TERRAFORM_CLIENT_ID=$TERRAFORM_CLIENT_ID" \
    "TERRAFORM_CLIENT_SECRET=$TERRAFORM_CLIENT_SECRET"
  
  # Verify settings
  az functionapp config appsettings list \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[?name=='TERRAFORM_CLIENT_ID' || name=='TERRAFORM_CLIENT_SECRET']" -o table
  
  set -e  # Re-enable exit on error
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --name)
      CLASSROOM_NAME="$2"
      shift 2
      ;;
    --location)
      LOCATION="$2"
      shift 2
      ;;
    --action)
      ACTION="$2"
      shift 2
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
    --validate-only)
      VALIDATE_ONLY=true
      shift
      ;;
    *)
      echo "Unknown parameter: $1"
      usage
      ;;
  esac
done

# Main execution
check_prerequisites
configure_azure

if [ "$SETUP_RBAC" = true ]; then
  echo "Setting up Azure RBAC roles..."
  ./scripts/setup_azure_rbac.sh --create
fi

run_terraform "$ACTION" "$CLASSROOM_NAME" "${PARALLELISM:-4}" "${VALIDATE_ONLY:-false}" 