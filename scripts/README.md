# User Cleanup Scripts

This directory contains scripts to clean up users and their associated resources in both AWS and Azure environments.

## AWS Cleanup Script (`cleanup_aws_users.sh`)

This script deletes AWS IAM users and their associated resources, including:
- Login profiles
- Access keys
- Attached policies
- Inline policies

### Prerequisites
- AWS CLI installed and configured
- Appropriate AWS permissions to manage IAM users

### Usage
```bash
./cleanup_aws_users.sh
```

### What it does
1. Finds all users with names starting with:
   - `service-conference-user-*` (service users)
   - `conference-user-*` (conference users)
2. For each user:
   - Deletes login profile (if exists)
   - Deletes all access keys
   - Detaches all attached policies
   - Deletes all inline policies
   - Deletes the user

## Azure Cleanup Script (`cleanup_azure_users.sh`)

This script deletes Azure AD users and their associated resources, including:
- Service principals
- Resource groups
- Role assignments

### Prerequisites
- Azure CLI installed and configured
- Appropriate Azure permissions to manage AD users and resources

### Usage
```bash
./cleanup_azure_users.sh
```

### What it does
1. Finds all users with names starting with:
   - `service-conference-user-*` (service users)
   - `conference-user-*` (conference users)
2. For each user:
   - Deletes associated service principal (if exists)
   - Deletes associated resource group (if exists)
   - Removes all role assignments
   - Deletes the user

## Important Notes

1. **Backup**: Before running these scripts, ensure you have backed up any important data or configurations.

2. **Permissions**: The scripts require appropriate permissions in both AWS and Azure:
   - AWS: IAM permissions to manage users, policies, and access keys
   - Azure: AD permissions to manage users and service principals, plus resource management permissions

3. **Resource Cleanup**:
   - AWS: Focuses on IAM resources (users, policies, keys)
   - Azure: Also cleans up resource groups and service principals

4. **Error Handling**:
   - Both scripts include error handling and will continue processing even if individual operations fail
   - Check the output for any errors or skipped operations

5. **Dry Run**: Consider adding a `--dry-run` flag if you want to preview changes before executing them.

## Security Considerations

1. **Access Control**: Ensure only authorized administrators can run these scripts
2. **Audit Logging**: Consider enabling audit logging in both AWS and Azure
3. **Resource Protection**: Consider adding resource tags or locks to prevent accidental deletion
4. **Backup Strategy**: Implement a backup strategy for critical resources

## Example Output

```
Fetching service conference users...
Processing service conference users...
Processing user: service-conference-user-1
  Deleting login profile...
  Deleting access keys...
    Deleting access key: AKIAXXXXXXXXXXXXXXXX
  Detaching policies...
    Detaching policy: arn:aws:iam::XXXXXXXXXXXX:policy/UserRestrictedPolicy
  Deleting inline policies...
  Deleting user...
Completed processing user: service-conference-user-1
----------------------------------------
```

## Troubleshooting

1. **Permission Issues**:
   - Check AWS IAM permissions
   - Verify Azure AD permissions
   - Ensure proper role assignments

2. **Resource Dependencies**:
   - Some resources might have dependencies that prevent deletion
   - Check for resource locks or protection policies

3. **API Rate Limits**:
   - Be aware of API rate limits in both platforms
   - Consider adding delays between operations if needed

## Contributing

Feel free to submit issues and enhancement requests! 