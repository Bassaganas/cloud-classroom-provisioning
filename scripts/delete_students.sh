#!/bin/bash

# delete_students.sh
set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if Azure CLI is installed
check_prerequisites() {
    if ! command -v az &> /dev/null; then
        echo -e "${RED}Error: Azure CLI is not installed${NC}"
        echo "Please install it first: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi
}

# Function to check if user is logged in to Azure
check_login() {
    echo -e "${YELLOW}Checking Azure login status...${NC}"
    az account show &> /dev/null || {
        echo -e "${RED}Not logged in to Azure. Please run 'az login' first${NC}"
        exit 1
    }
}

# Function to get and delete student users
delete_students() {
    echo -e "${YELLOW}Getting list of all student users...${NC}"
    
    # Get all users with userPrincipalName starting with 'student_'
    STUDENTS=$(az ad user list --query "[?starts_with(userPrincipalName, 'student_')].{id:id, name:userPrincipalName}" -o json)
    
    # Count total students
    TOTAL_STUDENTS=$(echo $STUDENTS | jq length)
    echo -e "${GREEN}Found $TOTAL_STUDENTS student users${NC}"
    
    if [ "$TOTAL_STUDENTS" -eq 0 ]; then
        echo -e "${YELLOW}No students to delete${NC}"
        exit 0
    fi

    # Confirm deletion
    echo -e "${RED}WARNING: This will delete $TOTAL_STUDENTS student users${NC}"
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Operation cancelled${NC}"
        exit 1
    fi

    # Delete each student
    echo "$STUDENTS" | jq -c '.[]' | while read -r student; do
        USER_ID=$(echo $student | jq -r '.id')
        USER_NAME=$(echo $student | jq -r '.name')
        echo -e "${YELLOW}Deleting user: $USER_NAME${NC}"
        
        if az ad user delete --id "$USER_ID"; then
            echo -e "${GREEN}Successfully deleted: $USER_NAME${NC}"
        else
            echo -e "${RED}Failed to delete: $USER_NAME${NC}"
        fi
    done

    echo -e "${GREEN}Student deletion process completed${NC}"
}

# Main script
main() {
    echo "Starting student cleanup process..."
    
    check_prerequisites
    check_login
    delete_students
}

# Run main function
main