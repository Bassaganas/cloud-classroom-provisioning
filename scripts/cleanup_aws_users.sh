#!/bin/bash

# Function to delete a user and all associated resources
delete_user() {
    local user=$1
    echo "Processing user: $user"
    
    # Delete login profile if it exists
    echo "  Deleting login profile..."
    aws iam delete-login-profile --user-name "$user" 2>/dev/null || true
    
    # Delete access keys
    echo "  Deleting access keys..."
    aws iam list-access-keys --user-name "$user" --query "AccessKeyMetadata[*].AccessKeyId" --output text | while read -r key; do
        echo "    Deleting access key: $key"
        aws iam delete-access-key --user-name "$user" --access-key-id "$key"
    done
    
    # Detach attached policies
    echo "  Detaching policies..."
    aws iam list-attached-user-policies --user-name "$user" --query "AttachedPolicies[*].PolicyArn" --output text | while read -r policy; do
        echo "    Detaching policy: $policy"
        aws iam detach-user-policy --user-name "$user" --policy-arn "$policy"
    done
    
    # Delete inline policies
    echo "  Deleting inline policies..."
    aws iam list-user-policies --user-name "$user" --query "PolicyNames[*]" --output text | while read -r policy; do
        echo "    Deleting inline policy: $policy"
        aws iam delete-user-policy --user-name "$user" --policy-name "$policy"
    done
    
    # Delete the user
    echo "  Deleting user..."
    aws iam delete-user --user-name "$user"
    
    echo "Completed processing user: $user"
    echo "----------------------------------------"
}

# Get all service conference users
echo "Fetching service conference users..."
SERVICE_USERS=$(aws iam list-users --query "Users[?starts_with(UserName, 'service-conference-user')].UserName" --output text)

# Get all conference users
echo "Fetching conference users..."
CONFERENCE_USERS=$(aws iam list-users --query "Users[?starts_with(UserName, 'conference-user')].UserName" --output text)

# Process service conference users
echo "Processing service conference users..."
for user in $SERVICE_USERS; do
    delete_user "$user"
done

# Process conference users
echo "Processing conference users..."
for user in $CONFERENCE_USERS; do
    delete_user "$user"
done

echo "All users have been processed." 