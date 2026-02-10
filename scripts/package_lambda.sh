#!/bin/bash

# Exit on error
set -e

# Get the absolute path of the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# Check if virtualenv is installed
if ! command -v virtualenv &> /dev/null; then
    echo "virtualenv is not installed. Installing..."
    pip install virtualenv
fi

# Create a temporary directory for packaging
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TEMP_DIR"

# Create and activate virtual environment
python3 -m venv "$TEMP_DIR/venv"
source "$TEMP_DIR/venv/bin/activate"

if [ "$CLOUD_PROVIDER" == "aws" ]; then
    # Package user management Lambda function
    echo "Packaging AWS Lambda user management function..."
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/classroom_user_management.zip"
    pip install -r "$PROJECT_ROOT/functions/aws/requirements.txt"
    cp "$PROJECT_ROOT/functions/aws/testus_patronus/classroom_user_management.py" "$TEMP_DIR/"
    cd "$TEMP_DIR"
    zip -r9 "$PACKAGE_PATH" .
    cd "$PROJECT_ROOT"

    # Package status Lambda function
    echo "Packaging AWS Lambda status function..."
    TEMP_DIR2=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/aws/testus_patronus/testus_patronus_status.py" "$TEMP_DIR2/"
    pip install -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR2/"
    cd "$TEMP_DIR2"
    zip -r9 "$PROJECT_ROOT/functions/packages/testus_patronus_status.zip" .
    cd "$PROJECT_ROOT"
    rm -rf "$TEMP_DIR2"

    # Package stop_old_instances Lambda function
    echo "Packaging AWS Lambda stop_old_instances function..."
    TEMP_DIR3=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/common/classroom_stop_old_instances.py" "$TEMP_DIR3/"
    pip install -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR3/"
    cd "$TEMP_DIR3"
    zip -r9 "$PROJECT_ROOT/functions/packages/classroom_stop_old_instances.zip" .
    cd "$PROJECT_ROOT"
    rm -rf "$TEMP_DIR3"

    # Package admin cleanup Lambda function
    echo "Packaging AWS Lambda admin cleanup function..."
    TEMP_DIR6=$(mktemp -d)
    cp "$PROJECT_ROOT/functions/common/classroom_admin_cleanup.py" "$TEMP_DIR6/"
    pip install -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR6/"
    cd "$TEMP_DIR6"
    zip -r9 "$PROJECT_ROOT/functions/packages/classroom_admin_cleanup.zip" .
    cd "$PROJECT_ROOT"
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
    echo "Created isolated temporary directory: $TEMP_DIR5"
    
    # Verify source file exists and has content
    if [ ! -f "$PROJECT_ROOT/functions/common/classroom_instance_manager.py" ]; then
        echo "ERROR: Source file not found: $PROJECT_ROOT/functions/common/classroom_instance_manager.py"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    SOURCE_SIZE=$(wc -c < "$PROJECT_ROOT/functions/common/classroom_instance_manager.py")
    echo "Source file size: $SOURCE_SIZE bytes"
    
    if [ "$SOURCE_SIZE" -lt 100 ]; then
        echo "ERROR: Source file appears to be empty or too small ($SOURCE_SIZE bytes)"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    # Explicitly copy ONLY the intended file (classroom_instance_manager.py)
    echo "Copying classroom_instance_manager.py to temp directory..."
    cp "$PROJECT_ROOT/functions/common/classroom_instance_manager.py" "$TEMP_DIR5/"
    
    # Verify copy succeeded
    COPIED_SIZE=$(wc -c < "$TEMP_DIR5/classroom_instance_manager.py")
    if [ "$SOURCE_SIZE" -ne "$COPIED_SIZE" ]; then
        echo "ERROR: File copy failed. Source: $SOURCE_SIZE bytes, Copied: $COPIED_SIZE bytes"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    echo "File copied successfully: $COPIED_SIZE bytes"
    
    # Verify temp directory only contains the intended file before installing dependencies
    PYTHON_FILES_IN_TEMP=$(find "$TEMP_DIR5" -maxdepth 1 -name "*.py" -type f | wc -l)
    if [ "$PYTHON_FILES_IN_TEMP" -ne 1 ]; then
        echo "ERROR: Temp directory contains unexpected Python files before dependency installation"
        echo "Found $PYTHON_FILES_IN_TEMP Python files, expected 1"
        rm -rf "$TEMP_DIR5"
        exit 1
    fi
    
    # Install dependencies
    echo "Installing dependencies..."
    pip install -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR5/"
    
    # Create zip from clean temp directory
    echo "Creating zip package..."
    cd "$TEMP_DIR5"
    zip -r9 "$PACKAGE_PATH" .
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
    
    PACKAGE_SIZE=$(unzip -l "$PACKAGE_PATH" | grep "classroom_instance_manager.py" | awk '{print $1}')
    echo "Package created successfully. File size in package: $PACKAGE_SIZE bytes"
    
    # Clean up temp directory
    rm -rf "$TEMP_DIR5"
    echo "✓ Cleanup complete"

    # Package dify_jira API Lambda function
    echo "Packaging AWS Lambda dify_jira API function..."
    TEMP_DIR4=$(mktemp -d)

    # Copy the dify_jira API Lambda function
    cp "$PROJECT_ROOT/functions/aws/testus_patronus/dify_jira_api.py" "$TEMP_DIR4/"

    # Copy the dataset directory with JSON files (make it optional)
    echo "Copying dataset directory..."
    if [ -d "$PROJECT_ROOT/../dify_jira/data/dataset" ]; then
        cp -r "$PROJECT_ROOT/../dify_jira/data/dataset" "$TEMP_DIR4/data/"
    else
        echo "Warning: Dataset directory not found, skipping..."
    fi

    # Install dependencies
    pip install -r "$PROJECT_ROOT/functions/aws/requirements.txt" -t "$TEMP_DIR4/"

    # Create the package
    cd "$TEMP_DIR4"
    zip -r9 "$PROJECT_ROOT/functions/packages/dify_jira_api.zip" .
    cd "$PROJECT_ROOT"
    rm -rf "$TEMP_DIR4"
    
else
    # Azure Function packaging
    echo "Packaging Azure Function..."
    PACKAGE_PATH="$PROJECT_ROOT/functions/packages/azure_function.zip"
    
    # Install dependencies
    pip install -r "$PROJECT_ROOT/functions/azure/requirements.txt"
    
    # Copy all Azure function files
    cp -r "$PROJECT_ROOT/functions/azure/"* "$TEMP_DIR/"
    
    # Create deployment package
    cd "$TEMP_DIR"
    zip -r9 "$PACKAGE_PATH" . -x "*.pyc" "__pycache__/*" "*.git*"
    
    # Verify package
    if [ ! -f "$PACKAGE_PATH" ]; then
        echo "Error: Failed to create Azure Function package at $PACKAGE_PATH"
        exit 1
    fi
    
    # Verify package contents
    echo "Verifying package contents..."
    if ! unzip -l "$PACKAGE_PATH" | grep -q "function_app.py"; then
        echo "Error: Package is missing function_app.py"
        exit 1
    fi
    if ! unzip -l "$PACKAGE_PATH" | grep -q "requirements.txt"; then
        echo "Error: Package is missing requirements.txt"
        exit 1
    fi
    if ! unzip -l "$PACKAGE_PATH" | grep -q "function.json"; then
        echo "Error: Package is missing function.json"
        exit 1
    fi
    
    echo "Azure Function packaged successfully at: $PACKAGE_PATH"
    echo "Package contents verified successfully"
fi

# Clean up
echo "Cleaning up..."
deactivate
cd "$PROJECT_ROOT"
rm -rf "$TEMP_DIR"