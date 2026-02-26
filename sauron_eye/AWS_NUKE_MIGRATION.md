# AWS Nuke Migration Guide

## Overview

We've migrated from a custom bash script (`aws_nuke.sh`) to using the official `aws-nuke` tool (`aws_nuke_v2.sh`). This provides better reliability, comprehensive resource coverage, and automatic dependency handling.

## Why Migrate?

### Issues with Custom Script

The custom bash script (`aws_nuke.sh`) had several limitations:

1. **S3 Versioning**: Failed to properly delete versioned S3 buckets (required manual cleanup)
2. **Dependency Handling**: Manual dependency ordering led to failures (e.g., IAM policies still attached)
3. **EC2 Snapshots**: Failed to delete snapshots with dependencies
4. **Bash Compatibility**: Required complex workarounds for bash 3.2 compatibility
5. **Maintenance**: ~1600 lines of custom code to maintain

### Benefits of aws-nuke

1. **Battle-tested**: Widely used, actively maintained tool
2. **Automatic Dependencies**: Handles resource dependencies automatically
3. **S3 Versioning**: Properly handles versioned buckets, delete markers, etc.
4. **Comprehensive**: Supports 100+ AWS resource types
5. **Configuration-based**: YAML config file is easier to maintain than bash code
6. **Better Error Handling**: More robust error handling and retry logic

## Migration Steps

### 1. Install aws-nuke

```bash
# macOS
brew install aws-nuke

# Linux
wget https://github.com/rebuy-de/aws-nuke/releases/latest/download/aws-nuke-v2.25.0-linux-amd64.tar.gz
tar -xzf aws-nuke-v2.25.0-linux-amd64.tar.gz
sudo mv aws-nuke /usr/local/bin/

# Verify installation
aws-nuke version
```

### 2. Test Dry-Run

```bash
# Test the new script (dry-run by default)
./scripts/aws_nuke_v2.sh

# Compare with old script
./scripts/aws_nuke.sh
```

### 3. Review Configuration

The configuration file is at `iac/aws/aws-nuke-config.yml`. It defines:
- Which resources to delete (filters)
- Which resources to protect (exclusions)
- Regions to process

**Important**: The account ID in the config file is automatically updated by the script based on your AWS credentials.

### 4. Execute (When Ready)

```bash
# Actually delete resources
./scripts/aws_nuke_v2.sh --execute
```

## Configuration File

The configuration file (`iac/aws/aws-nuke-config.yml`) uses filters to determine which resources to delete:

### Filter Types

- **regex**: Match resource names/IDs using regular expressions
- **glob**: Match using glob patterns
- **exclude**: Exclude resources matching the pattern

### Example Filters

```yaml
IAMRole:
  - type: regex
    value: "^(lambda-execution|ec2-ssm).*"  # Include
  - type: exclude
    value: ".*terraform.*"  # Exclude
```

### Protected Resources

The following are protected by default:
- `terraform-state-*` buckets
- `terraform-locks-*` tables
- `*testingfantasy.com*` resources
- Default VPC and security groups

## Command-Line Interface

The v2 script maintains the same interface as the original:

```bash
./scripts/aws_nuke_v2.sh [OPTIONS]

Options:
  --execute           Actually delete resources (default: dry-run)
  --region REGION     Specific region to target
  --skip-terraform    Skip terraform destroy step
  --force             Skip confirmation prompts
  --help              Show help message
```

## Differences from Original Script

| Feature | Original (aws_nuke.sh) | New (aws_nuke_v2.sh) |
|---------|------------------------|----------------------|
| **Tool** | Custom bash script | Official aws-nuke tool |
| **S3 Versioning** | ❌ Manual cleanup needed | ✅ Automatic |
| **Dependencies** | ❌ Manual ordering | ✅ Automatic |
| **Resource Coverage** | ~25 types | 100+ types |
| **Configuration** | Bash variables | YAML file |
| **Maintenance** | High (custom code) | Low (config only) |
| **Error Handling** | Basic | Advanced |
| **Terraform Integration** | ✅ Yes | ✅ Yes |

## Troubleshooting

### aws-nuke not found

```bash
# Check if installed
which aws-nuke

# Install if missing
brew install aws-nuke  # macOS
```

### Configuration errors

The script automatically updates the account ID in the config file. If you see errors:
1. Check that `iac/aws/aws-nuke-config.yml` exists
2. Verify AWS credentials: `aws sts get-caller-identity`
3. Check config file syntax (YAML)

### Resources not deleted

1. Check the configuration file filters
2. Verify resources match the filter patterns
3. Check for exclusions that might be protecting resources
4. Review aws-nuke output for specific errors

## Backward Compatibility

The original `aws_nuke.sh` script is still available for:
- Environments where aws-nuke cannot be installed
- Legacy workflows
- Reference implementation

However, **new deployments should use `aws_nuke_v2.sh`**.

## Additional Resources

- [aws-nuke GitHub](https://github.com/rebuy-de/aws-nuke)
- [aws-nuke Documentation](https://github.com/rebuy-de/aws-nuke#documentation)
- [Configuration Examples](https://github.com/rebuy-de/aws-nuke/tree/main/config)
