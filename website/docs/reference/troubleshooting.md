---
sidebar_position: 1
---

# Troubleshooting

## Common Issues

### Terraform State Locked

```bash
cd iac/aws
terraform force-unlock <LOCK_ID>
# Or use the script
./scripts/setup_classroom.sh --name my-class --cloud aws --force-unlock
```

### Lambda Packaging Fails

```bash
# Install missing dependencies
pip3 install virtualenv
./scripts/package_lambda.sh --cloud aws
```

### AWS Credentials Not Found

```bash
aws configure
# Or use environment variables
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
```

### Backend Already Exists

- The script handles existing backends gracefully
- Use `--destroy` to clean up if needed

## Debug Mode

Enable verbose Terraform output:

```bash
export TF_LOG=DEBUG
./scripts/setup_classroom.sh --name debug-class --cloud aws
```
