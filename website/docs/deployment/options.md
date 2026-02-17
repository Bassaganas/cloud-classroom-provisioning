---
sidebar_position: 3
---

# Deployment Options

## Environment Selection

```bash
# Deploy to dev environment (default)
./scripts/setup_classroom.sh --name my-class --cloud aws --environment dev

# Deploy to staging environment
./scripts/setup_classroom.sh --name my-class --cloud aws --environment staging

# Deploy to production environment
./scripts/setup_classroom.sh --name my-class --cloud aws --environment prod
```

## Partial Deployments

```bash
# Deploy only common infrastructure (EC2 manager)
./scripts/setup_classroom.sh --name my-class --cloud aws --only-common

# Deploy only workshop infrastructure
./scripts/setup_classroom.sh --name my-class --cloud aws --only-workshop
```

## Workshop Selection

```bash
# Deploy Testus Patronus workshop (default)
./scripts/setup_classroom.sh --name my-class --cloud aws --workshop testus_patronus

# Deploy Fellowship workshop
./scripts/setup_classroom.sh --name my-class --cloud aws --workshop fellowship
```

## EC2 Instance Pool Options

```bash
# Deploy with EC2 instance pool
./scripts/setup_classroom.sh \
  --name my-classroom \
  --cloud aws \
  --with-pool \
  --pool-size 10

# Deploy without EC2 instances (Lambda only, no EC2 costs)
./scripts/setup_classroom.sh \
  --name dev-test \
  --cloud aws
```

## Advanced Options

```bash
# Skip Lambda packaging (use existing packages)
./scripts/setup_classroom.sh --name my-class --cloud aws --skip-packaging

# Force unlock Terraform state
./scripts/setup_classroom.sh --name my-class --cloud aws --force-unlock

# Set custom parallelism
./scripts/setup_classroom.sh --name my-class --cloud aws --parallelism 10
```
