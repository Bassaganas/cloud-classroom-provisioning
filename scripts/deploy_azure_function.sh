#!/bin/bash

# Exit on error
set -e

# Function to display usage
usage() {
    echo "Usage: $0 --name <function-app-name> --resource-group <resource-group-name> [--remote-build]"
    echo ""
    echo "Options:"
    echo "  --name            Name of the function app (required)"
    echo "  --resource-group  Name of the resource group (required)"
    echo "  --remote-build    Use remote build on Azure instead of local build"
    exit 1
}

# Parse command line arguments
REMOTE_BUILD=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            FUNCTION_APP_NAME="$2"
            shift 2
            ;;
        --resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        --remote-build)
            REMOTE_BUILD=true
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
if [ -z "$FUNCTION_APP_NAME" ] || [ -z "$RESOURCE_GROUP" ]; then
    echo "Error: Function app name and resource group are required"
    usage
fi

# Navigate to the Azure function directory
cd "$(dirname "$0")/../functions/azure"

echo "Setting up Python virtual environment..."
python -m venv .venv
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install --upgrade setuptools wheel
pip install -r requirements.txt

echo "Building and deploying Azure function..."

if [ "$REMOTE_BUILD" = true ]; then
    echo "Using remote build on Azure..."
    func azure functionapp publish "$FUNCTION_APP_NAME" --build remote --python
else
    echo "Using local build..."
    # Clean up any existing packages
    rm -rf .python_packages

    # Create the deployment package
    mkdir -p .python_packages/lib/site-packages
    cp -r .venv/lib/python*/site-packages/* .python_packages/lib/site-packages/

    # Deploy using func core tools
    func azure functionapp publish "$FUNCTION_APP_NAME" --build-native-deps --python
fi

echo "Setting up Azure AD permissions..."
# Get the Microsoft Graph API service principal ID
GRAPH_API_ID=$(az ad sp show --id 00000003-0000-0000-c000-000000000000 --query id -o tsv)

# Get the app registration client ID from function app settings
APP_CLIENT_ID=$(az functionapp config appsettings list \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='AZURE_CLIENT_ID'].value" -o tsv)

# Get the app registration object ID
APP_OBJECT_ID=$(az ad app show --id "$APP_CLIENT_ID" --query id -o tsv)


# Grant admin consent for the application permission
echo "Granting admin consent for application permissions..."
az ad app permission admin-consent --id "$APP_CLIENT_ID"

# Before setting app settings, get the subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Setting up application settings..."
echo "SUBSCRIPTION_ID: $SUBSCRIPTION_ID"

# Set required app settings
az functionapp config appsettings set \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
    "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" \
    "AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)" \
    "AZURE_DOMAIN=paulabassaganasgmail.onmicrosoft.com"

# Restart the function app to apply changes
echo "Restarting function app..."
az functionapp restart --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP"

# Deactivate virtual environment
deactivate

echo "Azure AD permissions and roles setup completed!"
echo "Deployment completed successfully!"

# Function to handle Azure login
azure_login() {
  echo "Logging into Azure..."
  
  # Check if already logged in
  if ! az account show &>/dev/null; then
    # Get number of tenants
    TENANT_COUNT=$(az tenant list --query 'length([])' -o tsv 2>/dev/null || echo "0")
    
    if [ "$TENANT_COUNT" -eq 1 ]; then
      # If only one tenant exists, use it directly
      TENANT_ID=$(az tenant list --query '[0].tenantId' -o tsv)
      az login --tenant "$TENANT_ID" --only-show-errors
    else
      # Regular login if multiple tenants or count couldn't be determined
      az login
    fi
  fi
  
  if [ $? -ne 0 ]; then
    echo "Failed to login to Azure. Please try again."Setting up application settings.
    exit 1
  fi
  
  # Get subscription ID
  SUBSCRIPTION_ID=$(az account show --query id -o tsv)
  if [ -z "$SUBSCRIPTION_ID" ]; then
    echo "No subscription found. Please set up a subscription first."
    exit 1
  fi
  
  # Get tenant ID
  TENANT_ID=$(az account show --query tenantId -o tsv)
  if [ -z "$TENANT_ID" ]; then
    echo "No tenant ID found. Please check your Azure account."
    exit 1
  fi
  
  # Set the subscription
  az account set --subscription "$SUBSCRIPTION_ID"
  
  # Export the values for Terraform
  export ARM_SUBSCRIPTION_ID="$SUBSCRIPTION_ID"
  export ARM_TENANT_ID="$TENANT_ID"
}
