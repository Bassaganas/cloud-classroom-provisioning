#!/bin/bash

# Function to delete a user and all associated resources
delete_user() {
    local user=$1
    echo "Processing user: $user"
    
    # Get user object ID
    local user_object_id=$(az ad user show --id "$user" --query id -o tsv)
    if [ -z "$user_object_id" ]; then
        echo "User not found: $user"
        return
    fi
    
    # Delete service principal if it exists
    echo "  Deleting service principal..."
    local sp_id=$(az ad sp list --filter "displayName eq '$user-service'" --query "[0].id" -o tsv)
    if [ ! -z "$sp_id" ]; then
        echo "    Deleting service principal: $sp_id"
        az ad sp delete --id "$sp_id"
    fi
    
    # Delete resource group if it exists
    echo "  Deleting resource group..."
    local rg_name="rg-$user"
    if az group show --name "$rg_name" &>/dev/null; then
        echo "    Deleting resource group: $rg_name"
        az group delete --name "$rg_name" --yes --no-wait
    fi
    
    # Remove role assignments
    echo "  Removing role assignments..."
    az role assignment list --assignee "$user_object_id" --query "[].id" -o tsv | while read -r assignment; do
        echo "    Removing role assignment: $assignment"
        az role assignment delete --ids "$assignment"
    done
    
    # Delete the user
    echo "  Deleting user..."
    az ad user delete --id "$user_object_id"
    
    echo "Completed processing user: $user"
    echo "----------------------------------------"
}

# Get all service conference users
echo "Fetching service conference users..."
SERVICE_USERS=$(az ad user list --filter "startswith(displayName, 'service-conference-user')" --query "[].userPrincipalName" -o tsv)

# Get all conference users
echo "Fetching conference users..."
CONFERENCE_USERS=$(az ad user list --filter "startswith(displayName, 'conference-user')" --query "[].userPrincipalName" -o tsv)

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