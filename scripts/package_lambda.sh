#!/bin/bash

# Exit on error
set -e

# Get the absolute path of the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Detect pip command (prefer pip3, fallback to pip)
if command -v pip3 >/dev/null 2>&1; then
    PIP_CMD="pip3"
elif command -v pip >/dev/null 2>&1; then
    PIP_CMD="pip"
else
    echo "ERROR: Neither pip nor pip3 found. Please install Python pip."
    exit 1
fi

# Parse command line arguments
CLOUD_PROVIDER=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --cloud)
      CLOUD_PROVIDER="$2"
      shift 2
      ;;
    *)
      echo "Unknown parameter: $1"
      echo "Usage: $0 --cloud [aws|azure]"
      exit 1
      ;;
  esac
done

if [ -z "$CLOUD_PROVIDER" ] || [[ ! "$CLOUD_PROVIDER" =~ ^(aws|azure)$ ]]; then
  echo "Error: --cloud parameter must be either 'aws' or 'azure'"
  exit 1
fi

# Create the packages directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/functions/packages"

if [ "$CLOUD_PROVIDER" == "aws" ]; then
    # Package user management Lambda function
    echo "Packaging AWS Lambda user management function..."
    
    # Delete existing zip file to ensure clean packaging
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_user_management.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        echo "Deleting existing zip file to ensure clean packaging..."
        rm -f "$PACKAGE_PATH"
    fi
    
    TEMP_DIR1=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/aws/testus_patronus/classroom_user_management.py" "$TEMP_DIR1/"
    
    # Verify temp directory only contains the intended file before installing dependencies
    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR1" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        find "$TEMP_DIR1" -maxdepth 1 -name "*.py" -type f
        rm -rf "$TEMP_DIR1"
        exit 1
    fi
    
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR1/"
    
    # Verify no unwanted Lambda function files in root directory (check for other Lambda function patterns)
    UNWANTED_LAMBDA_FILES=$(find "$TEMP_DIR1" -maxdepth 1 -type f \( -name "classroom_*.py" -o -name "testus_patronus_*.py" -o -name "dify_jira_*.py" \) ! -name "classroom_user_management.py")
    if [ -n "$UNWANTED_LAMBDA_FILES" ]; then
        echo "ERROR: Unwanted Lambda function files found in root directory:"
        echo "$UNWANTED_LAMBDA_FILES"
        echo "Expected only: classroom_user_management.py"
        rm -rf "$TEMP_DIR1"
        exit 1
    fi
    
    cd "$TEMP_DIR1"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"
    
    # Verify package contents
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_user_management.zip"
    if ! unzip -l "$PACKAGE_PATH" | grep -q "classroom_user_management.py"; then
        echo "ERROR: Package does not contain classroom_user_management.py"
        rm -rf "$TEMP_DIR1"
        exit 1
    fi
    
    # Verify unwanted files are NOT in package
    if unzip -l "$PACKAGE_PATH" | grep -q "testus_patronus_user_management.py"; then
        echo "ERROR: Package contains unwanted file: testus_patronus_user_management.py"
        rm -f "$PACKAGE_PATH"
        rm -rf "$TEMP_DIR1"
        exit 1
    fi
    
    # Verify lambda_handler function exists in the package
    if ! unzip -p "$PACKAGE_PATH" classroom_user_management.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in packaged file"
        rm -rf "$TEMP_DIR1"
        exit 1
    fi
    echo "✓ Verified: classroom_user_management.py packaged correctly"
    
    rm -rf "$TEMP_DIR1"

    # Package status Lambda function
    echo "Packaging AWS Lambda status function..."
    
    # Delete existing zip file to ensure clean packaging
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/testus_patronus_status.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        echo "Deleting existing zip file to ensure clean packaging..."
        rm -f "$PACKAGE_PATH"
    fi
    
    TEMP_DIR2=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/aws/testus_patronus/testus_patronus_status.py" "$TEMP_DIR2/"
    
    # Verify temp directory only contains the intended file before installing dependencies
    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR2" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        find "$TEMP_DIR2" -maxdepth 1 -name "*.py" -type f
        rm -rf "$TEMP_DIR2"
        exit 1
    fi
    
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR2/"
    
    # Verify no unwanted Lambda function files in root directory (check for other Lambda function patterns)
    UNWANTED_LAMBDA_FILES=$(find "$TEMP_DIR2" -maxdepth 1 -type f \( -name "classroom_*.py" -o -name "testus_patronus_*.py" -o -name "dify_jira_*.py" \) ! -name "testus_patronus_status.py")
    if [ -n "$UNWANTED_LAMBDA_FILES" ]; then
        echo "ERROR: Unwanted Lambda function files found in root directory:"
        echo "$UNWANTED_LAMBDA_FILES"
        echo "Expected only: testus_patronus_status.py"
        rm -rf "$TEMP_DIR2"
        exit 1
    fi
    
    cd "$TEMP_DIR2"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"
    
    # Verify package contents
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/testus_patronus_status.zip"
    if ! unzip -l "$PACKAGE_PATH" | grep -q "testus_patronus_status.py"; then
        echo "ERROR: Package does not contain testus_patronus_status.py"
        rm -rf "$TEMP_DIR2"
        exit 1
    fi
    
    # Verify unwanted files are NOT in package
    if unzip -l "$PACKAGE_PATH" | grep -q "classroom_user_management.py"; then
        echo "ERROR: Package contains unwanted file: classroom_user_management.py"
        rm -f "$PACKAGE_PATH"
        rm -rf "$TEMP_DIR2"
        exit 1
    fi
    
    # Verify lambda_handler function exists in the package
    if ! unzip -p "$PACKAGE_PATH" testus_patronus_status.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in packaged file"
        rm -rf "$TEMP_DIR2"
        exit 1
    fi
    echo "✓ Verified: testus_patronus_status.py packaged correctly"
    
    rm -rf "$TEMP_DIR2"

    # Package stop_old_instances Lambda function
    echo "Packaging AWS Lambda stop_old_instances function..."
    
    # Delete existing zip file to ensure clean packaging
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_stop_old_instances.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        echo "Deleting existing zip file to ensure clean packaging..."
        rm -f "$PACKAGE_PATH"
    fi
    
    TEMP_DIR3=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/common/classroom_stop_old_instances.py" "$TEMP_DIR3/"
    
    # Verify temp directory only contains the intended file before installing dependencies
    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR3" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        find "$TEMP_DIR3" -maxdepth 1 -name "*.py" -type f
        rm -rf "$TEMP_DIR3"
        exit 1
    fi
    
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR3/"
    
    # Verify no unwanted Lambda function files in root directory (check for other Lambda function patterns)
    UNWANTED_LAMBDA_FILES=$(find "$TEMP_DIR3" -maxdepth 1 -type f \( -name "classroom_*.py" -o -name "testus_patronus_*.py" -o -name "dify_jira_*.py" \) ! -name "classroom_stop_old_instances.py")
    if [ -n "$UNWANTED_LAMBDA_FILES" ]; then
        echo "ERROR: Unwanted Lambda function files found in root directory:"
        echo "$UNWANTED_LAMBDA_FILES"
        echo "Expected only: classroom_stop_old_instances.py"
        rm -rf "$TEMP_DIR3"
        exit 1
    fi
    
    cd "$TEMP_DIR3"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"
    
    # Verify package contents
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_stop_old_instances.zip"
    if ! unzip -l "$PACKAGE_PATH" | grep -q "classroom_stop_old_instances.py"; then
        echo "ERROR: Package does not contain classroom_stop_old_instances.py"
        rm -rf "$TEMP_DIR3"
        exit 1
    fi
    
    # Verify unwanted files are NOT in package
    if unzip -l "$PACKAGE_PATH" | grep -q "testus_patronus_stop_old_instances.py"; then
        echo "ERROR: Package contains unwanted file: testus_patronus_stop_old_instances.py"
        rm -f "$PACKAGE_PATH"
        rm -rf "$TEMP_DIR3"
        exit 1
    fi
    
    # Verify lambda_handler function exists in the package
    if ! unzip -p "$PACKAGE_PATH" classroom_stop_old_instances.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in packaged file"
        rm -rf "$TEMP_DIR3"
        exit 1
    fi
    echo "✓ Verified: classroom_stop_old_instances.py packaged correctly"
    
    rm -rf "$TEMP_DIR3"

    # Package admin cleanup Lambda function
    echo "Packaging AWS Lambda admin cleanup function..."
    
    # Delete existing zip file to ensure clean packaging
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_admin_cleanup.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        echo "Deleting existing zip file to ensure clean packaging..."
        rm -f "$PACKAGE_PATH"
    fi
    
    TEMP_DIR6=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/common/classroom_admin_cleanup.py" "$TEMP_DIR6/"
    
    # Verify temp directory only contains the intended file before installing dependencies
    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR6" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        find "$TEMP_DIR6" -maxdepth 1 -name "*.py" -type f
        rm -rf "$TEMP_DIR6"
        exit 1
    fi
    
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR6/"
    
    # Verify no unwanted Lambda function files in root directory (check for other Lambda function patterns)
    UNWANTED_LAMBDA_FILES=$(find "$TEMP_DIR6" -maxdepth 1 -type f \( -name "classroom_*.py" -o -name "testus_patronus_*.py" -o -name "dify_jira_*.py" \) ! -name "classroom_admin_cleanup.py")
    if [ -n "$UNWANTED_LAMBDA_FILES" ]; then
        echo "ERROR: Unwanted Lambda function files found in root directory:"
        echo "$UNWANTED_LAMBDA_FILES"
        echo "Expected only: classroom_admin_cleanup.py"
        rm -rf "$TEMP_DIR6"
        exit 1
    fi
    
    cd "$TEMP_DIR6"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"
    
    # Verify package contents
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_admin_cleanup.zip"
    if ! unzip -l "$PACKAGE_PATH" | grep -q "classroom_admin_cleanup.py"; then
        echo "ERROR: Package does not contain classroom_admin_cleanup.py"
        rm -rf "$TEMP_DIR6"
        exit 1
    fi
    
    # Verify unwanted files are NOT in package
    if unzip -l "$PACKAGE_PATH" | grep -q "testus_patronus_admin_cleanup.py"; then
        echo "ERROR: Package contains unwanted file: testus_patronus_admin_cleanup.py"
        rm -f "$PACKAGE_PATH"
        rm -rf "$TEMP_DIR6"
        exit 1
    fi
    
    # Verify lambda_handler function exists in the package
    if ! unzip -p "$PACKAGE_PATH" classroom_admin_cleanup.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in packaged file"
        rm -rf "$TEMP_DIR6"
        exit 1
    fi
    echo "✓ Verified: classroom_admin_cleanup.py packaged correctly"
    
    rm -rf "$TEMP_DIR6"

    # Package instance manager Lambda function (MOVED BEFORE dify_jira to ensure it runs)
    echo "Packaging AWS Lambda instance manager function..."
    
    # Clean up extracted directory if it exists (leftover from previous extractions)
    if [ -d "$PROJECT_ROOT/functions/packages/classroom_instance_manager" ]; then
        echo "Cleaning up extracted directory: functions/packages/classroom_instance_manager"
        rm -rf "$PROJECT_ROOT/functions/packages/classroom_instance_manager"
    fi
    
    # Delete existing zip file to ensure clean packaging
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_instance_manager.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        echo "Deleting existing zip file to ensure clean packaging..."
        rm -f "$PACKAGE_PATH"
    fi
    
    # Create fresh temporary directory for this Lambda (completely isolated)
    TEMP_DIR5=$(mktemp -d)
    
    # Verify source file exists and has content
    if [ ! -f "$PROJECT_ROOT/functions/common/classroom_instance_manager.py" ]; then
        echo "ERROR: Source file not found: $PROJECT_ROOT/functions/common/classroom_instance_manager.py"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    SOURCE_SIZE=$(wc -c < "$PROJECT_ROOT/functions/common/classroom_instance_manager.py")
    
    if [ "$SOURCE_SIZE" -lt 100 ]; then
        echo "ERROR: Source file appears to be empty or too small ($SOURCE_SIZE bytes)"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    cp "$PROJECT_ROOT/functions/common/classroom_instance_manager.py" "$TEMP_DIR5/"
    
    # Verify copy succeeded
    COPIED_SIZE=$(wc -c < "$TEMP_DIR5/classroom_instance_manager.py")
    if [ "$SOURCE_SIZE" -ne "$COPIED_SIZE" ]; then
        echo "ERROR: File copy failed. Source: $SOURCE_SIZE bytes, Copied: $COPIED_SIZE bytes"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    # Verify temp directory only contains the intended file before installing dependencies
    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR5" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR5/"
    
    cd "$TEMP_DIR5"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"
    
    # Verify the package was created
    if [ ! -f "$PACKAGE_PATH" ]; then
        echo "ERROR: Package file was not created"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    # Verify the package contains the correct file
    if ! unzip -l "$PACKAGE_PATH" | grep -q "classroom_instance_manager.py"; then
        echo "ERROR: Package does not contain classroom_instance_manager.py"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    # Verify lambda_handler function exists in the package
    if ! unzip -p "$PACKAGE_PATH" classroom_instance_manager.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in packaged file"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    # Verify that testus_patronus_instance_manager.py is NOT in the package
    if unzip -l "$PACKAGE_PATH" | grep -q "testus_patronus_instance_manager.py"; then
        echo "ERROR: Package contains unwanted file: testus_patronus_instance_manager.py"
        echo "This file should not be in the package. Cleaning up..."
        rm -f "$PACKAGE_PATH"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    echo "✓ Verified: testus_patronus_instance_manager.py is not in the package"
    
    # Clean up temp directory
    rm -rf "$TEMP_DIR5"

    # Package dify_jira API Lambda function
    echo "Packaging AWS Lambda dify_jira API function..."
    
    # Delete existing zip file to ensure clean packaging
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/dify_jira_api.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        echo "Deleting existing zip file to ensure clean packaging..."
        rm -f "$PACKAGE_PATH"
    fi
    
    TEMP_DIR4=$(mktemp -d)

    # Copy the dify_jira API Lambda function
    cp "$PROJECT_ROOT/functions/aws/testus_patronus/dify_jira_api.py" "$TEMP_DIR4/"

    # Copy the dataset directory with JSON files (make it optional)
    if [ -d "$PROJECT_ROOT/../dify_jira/data/dataset" ]; then
        cp -r "$PROJECT_ROOT/../dify_jira/data/dataset" "$TEMP_DIR4/data/"
    fi

    # Verify temp directory only contains the intended file before installing dependencies
    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR4" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        find "$TEMP_DIR4" -maxdepth 1 -name "*.py" -type f
        rm -rf "$TEMP_DIR4"
        exit 1
    fi

    # Install dependencies
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR4/"

    # Verify no unwanted Lambda function files in root directory (check for other Lambda function patterns)
    UNWANTED_LAMBDA_FILES=$(find "$TEMP_DIR4" -maxdepth 1 -type f \( -name "classroom_*.py" -o -name "testus_patronus_*.py" -o -name "dify_jira_*.py" \) ! -name "dify_jira_api.py")
    if [ -n "$UNWANTED_LAMBDA_FILES" ]; then
        echo "ERROR: Unwanted Lambda function files found in root directory:"
        echo "$UNWANTED_LAMBDA_FILES"
        echo "Expected only: dify_jira_api.py"
        rm -rf "$TEMP_DIR4"
        exit 1
    fi

    # Create the package
    cd "$TEMP_DIR4"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"
    
    # Verify package contents
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/dify_jira_api.zip"
    if ! unzip -l "$PACKAGE_PATH" | grep -q "dify_jira_api.py"; then
        echo "ERROR: Package does not contain dify_jira_api.py"
        rm -rf "$TEMP_DIR4"
        exit 1
    fi
    
    # Verify lambda_handler function exists in the package
    if ! unzip -p "$PACKAGE_PATH" dify_jira_api.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in packaged file"
        rm -rf "$TEMP_DIR4"
        exit 1
    fi
    echo "✓ Verified: dify_jira_api.py packaged correctly"
    
    rm -rf "$TEMP_DIR4"

    # Package leaderboard consumer Lambda function
    echo "Packaging AWS Lambda leaderboard consumer function..."

    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/leaderboard_lambda.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        rm -f "$PACKAGE_PATH"
    fi

    TEMP_DIR7=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/aws/leaderboard_lambda.py" "$TEMP_DIR7/"
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR7/"

    cd "$TEMP_DIR7"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"

    if ! unzip -l "$PACKAGE_PATH" | grep -q "leaderboard_lambda.py"; then
        echo "ERROR: Package does not contain leaderboard_lambda.py"
        rm -rf "$TEMP_DIR7"
        exit 1
    fi
    if ! unzip -p "$PACKAGE_PATH" leaderboard_lambda.py | grep -q "def handler"; then
        echo "ERROR: handler function not found in leaderboard_lambda.py"
        rm -rf "$TEMP_DIR7"
        exit 1
    fi

    echo "✓ Verified: leaderboard_lambda.py packaged correctly"
    rm -rf "$TEMP_DIR7"

    # Package leaderboard API Lambda function
    echo "Packaging AWS Lambda leaderboard API function..."

    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/leaderboard_api.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        rm -f "$PACKAGE_PATH"
    fi

    TEMP_DIR8=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/aws/leaderboard_api.py" "$TEMP_DIR8/"
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR8/"

    cd "$TEMP_DIR8"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"

    if ! unzip -l "$PACKAGE_PATH" | grep -q "leaderboard_api.py"; then
        echo "ERROR: Package does not contain leaderboard_api.py"
        rm -rf "$TEMP_DIR8"
        exit 1
    fi
    if ! unzip -p "$PACKAGE_PATH" leaderboard_api.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in leaderboard_api.py"
        rm -rf "$TEMP_DIR8"
        exit 1
    fi

    echo "✓ Verified: leaderboard_api.py packaged correctly"
    rm -rf "$TEMP_DIR8"

    # Package shared_core_provisioner Lambda function (async provisioning worker)
    echo "Packaging AWS Lambda shared_core_provisioner function..."

    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/shared_core_provisioner.zip"
    if [ -f "$PACKAGE_PATH" ]; then
        echo "Deleting existing zip file to ensure clean packaging..."
        rm -f "$PACKAGE_PATH"
    fi

    TEMP_DIR9=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/aws/shared_core_provisioner.py" "$TEMP_DIR9/"

    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR9" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        find "$TEMP_DIR9" -maxdepth 1 -name "*.py" -type f
        rm -rf "$TEMP_DIR9"
        exit 1
    fi

    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR9/"

    cd "$TEMP_DIR9"
    zip -r9q "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"

    if ! unzip -l "$PACKAGE_PATH" | grep -q "shared_core_provisioner.py"; then
        echo "ERROR: Package does not contain shared_core_provisioner.py"
        rm -rf "$TEMP_DIR9"
        exit 1
    fi
    if ! unzip -p "$PACKAGE_PATH" shared_core_provisioner.py | grep -q "def lambda_handler"; then
        echo "ERROR: lambda_handler function not found in shared_core_provisioner.py"
        rm -rf "$TEMP_DIR9"
        exit 1
    fi

    echo "✓ Verified: shared_core_provisioner.py packaged correctly"
    rm -rf "$TEMP_DIR9"

else
    # Azure Function packaging
    echo "Packaging Azure Function..."
    TEMP_DIR=$(mktemp -d)
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/azure_function.zip"
    
    # Install dependencies
    $PIP_CMD install -q -r "$PROJECT_ROOT/functions/azure/requirements.txt" -t "$TEMP_DIR/"
    
    # Copy all Azure function files
    cp -r "$PROJECT_ROOT/functions/azure/"* "$TEMP_DIR/"
    
    # Create deployment package
    cd "$TEMP_DIR"
    zip -r9q "$PACKAGE_PATH" . -x "*.pyc" "__pycache__/*" "*.git*"
    cd "$PROJECT_ROOT"
    
    # Verify package
    if [ ! -f "$PACKAGE_PATH" ]; then
        echo "Error: Failed to create Azure Function package at $PACKAGE_PATH"
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    
    # Verify package contents
    if ! unzip -l "$PACKAGE_PATH" | grep -q "function_app.py"; then
        echo "Error: Package is missing function_app.py"
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    if ! unzip -l "$PACKAGE_PATH" | grep -q "requirements.txt"; then
        echo "Error: Package is missing requirements.txt"
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    if ! unzip -l "$PACKAGE_PATH" | grep -q "function.json"; then
        echo "Error: Package is missing function.json"
        rm -rf "$TEMP_DIR"
        exit 1
    fi
    
    echo "✓ Azure Function packaged successfully at: $PACKAGE_PATH"
    
    # Clean up
    rm -rf "$TEMP_DIR"
fi

# Clean up
echo "Packaging complete."
cd "$PROJECT_ROOT"