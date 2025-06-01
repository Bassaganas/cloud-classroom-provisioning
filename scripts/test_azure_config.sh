#!/bin/bash

# Default values
CLASSROOM_NAME="default-classroom"
ENVIRONMENT="test"
OWNER="paula"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --name)
      CLASSROOM_NAME="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --owner)
      OWNER="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Function to check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        echo "Azure CLI is not installed. Please install it first."
        exit 1
    fi
}

# Function to check if user is logged in to Azure
check_azure_login() {
    if ! az account show &> /dev/null; then
        echo "Please login to Azure first using 'az login'"
        exit 1
    fi
}

# Function to verify resource group exists
verify_resource_group() {
    local rg_name="rg-$CLASSROOM_NAME-$ENVIRONMENT"
    if ! az group show --name "$rg_name" &> /dev/null; then
        echo "Resource group $rg_name does not exist"
        return 1
    fi
    echo "Resource group $rg_name exists"
    return 0
}

# Function to verify function app exists
verify_function_app() {
    local func_name="func-$CLASSROOM_NAME-$ENVIRONMENT"
    if ! az functionapp show --name "$func_name" --resource-group "rg-$CLASSROOM_NAME-$ENVIRONMENT" &> /dev/null; then
        echo "Function app $func_name does not exist"
        return 1
    fi
    echo "Function app $func_name exists"
    return 0
}

# Function to verify RBAC roles
verify_rbac_roles() {
    local roles=("ConferenceUser" "ServicePrincipal")
    for role in "${roles[@]}"; do
        if ! az role definition list --name "$role" &> /dev/null; then
            echo "Role $role does not exist"
            return 1
        fi
        echo "Role $role exists"
    done
    return 0
}

# Function to test function URL
test_function_url() {
    local func_name="func-$CLASSROOM_NAME-$ENVIRONMENT"
    local rg_name="rg-$CLASSROOM_NAME-$ENVIRONMENT"
    
    # Get function URL
    local function_url=$(az functionapp function show \
        --name "$func_name" \
        --resource-group "$rg_name" \
        --function-name "create_user" \
        --query "invokeUrlTemplate" \
        --output tsv)
    
    if [ -z "$function_url" ]; then
        echo "Could not get function URL"
        return 1
    fi
    
    echo "Function URL: $function_url"
    
    # Test function
    echo "Testing function..."
    local response=$(curl -s -w "\n%{http_code}" "$function_url")
    local status_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    if [ "$status_code" != "200" ]; then
        echo "Function test failed with status code $status_code"
        echo "Response: $body"
        return 1
    fi
    
    echo "Function test successful"
    return 0
}

# Main test function
test_configuration() {
    echo "Testing Azure classroom configuration: $CLASSROOM_NAME"
    
    # Check prerequisites
    check_azure_cli
    check_azure_login
    
    # Test each component
    local tests_passed=true
    
    echo "Verifying resource group..."
    if ! verify_resource_group; then
        tests_passed=false
    fi
    
    echo "Verifying function app..."
    if ! verify_function_app; then
        tests_passed=false
    fi
    
    echo "Verifying RBAC roles..."
    if ! verify_rbac_roles; then
        tests_passed=false
    fi
    
    echo "Testing function URL..."
    if ! test_function_url; then
        tests_passed=false
    fi
    
    if [ "$tests_passed" = true ]; then
        echo "All tests passed successfully!"
        exit 0
    else
        echo "Some tests failed. Please check the output above."
        exit 1
    fi
}

# Execute tests
test_configuration 