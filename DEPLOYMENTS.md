# Deployments

## CI/CD Overview

Deployments are automated via GitHub Actions on pushes to `main` and triggered manually for environment-specific tasks. All infrastructure is managed via Terraform; all code is containerized and versioned.

**File:** `.github/workflows/build-deploy.yml`

## Automated Deployment Flow

### On Every Push to `main`

**1. Unit Tests**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: cd functions && python -m pytest tests/ -v
```
- Validates Lambda function logic and IAM policies
- Fails fast; no further jobs run if tests fail

**2. Build & Publish SUT (System Under Test)**
```yaml
  build:
    needs: test
    steps:
      - name: Build Docker image (SUT)
        run: docker build -t $ECR_REGISTRY/$ECR_REPO:$COMMIT_SHA .
      - name: Push to ECR
        run: docker push $ECR_REGISTRY/$ECR_REPO:$COMMIT_SHA
      - name: Upload SUT tarball to S3
        run: docker save | gzip > sut.tar.gz && aws s3 cp sut.tar.gz s3://$SUT_BUCKET/
```
- Builds Docker image from Dockerfile
- Publishes to AWS ECR with commit SHA tag
- Uploads compressed tarball to S3 for instance download

**3. Deploy Lambda Functions**
```yaml
  deploy:
    needs: build
    steps:
      - name: Package Lambda functions
        run: |
          cd functions
          zip -r lambda-bundle.zip common/ handlers/
      - name: Update classroom_instance_manager
        run: |
          aws lambda update-function-code \
            --function-name classroom_instance_manager \
            --zip-file fileb://lambda-bundle.zip
      - name: Update classroom_stop_old_instances
        run: |
          aws lambda update-function-code \
            --function-name classroom_stop_old_instances \
            --zip-file fileb://lambda-bundle.zip
```
- Bundles all Python Lambda code
- Updates both instance manager and lifecycle Lambdas
- Changes take effect immediately (no restart needed)

**4. Bake Golden AMI** (optional, if SUT changed)
```yaml
  bake-ami:
    needs: deploy
    if: success()
    steps:
      - name: Resolve current AMI
        run: |
          aws ssm get-parameter \
            --name /classroom/templates/$CLASSROOM_ENV/fellowship \
            --query 'Parameter.Value' > template.json
      - name: Launch bake instance
        run: |
          aws ec2 run-instances \
            --image-id ami-xxxxx \
            --subnet-id $BAKE_SUBNET_ID \
            --security-group-ids $BAKE_SG_ID \
            --iam-instance-profile $BAKE_INSTANCE_PROFILE \
            --user-data file://bake-userdata.sh > bake-instance.json
      - name: Wait for instance to stop
        run: |
          aws ec2 wait instance-stopped --instance-ids $BAKE_INSTANCE_ID --max-attempts 90
      - name: Create AMI snapshot
        run: |
          aws ec2 create-image \
            --instance-id $BAKE_INSTANCE_ID \
            --name fellowship-sut-golden-$COMMIT_SHA-$(date +%s) \
            --no-reboot > ami.json
      - name: Wait for AMI available
        run: |
          aws ec2 wait image-available --image-ids $AMI_ID --max-attempts 120
      - name: Update SSM parameter with new AMI
        run: |
          jq --arg ami_id $AMI_ID '.ami_id = $ami_id' template.json > template-updated.json
          aws ssm put-parameter \
            --name /classroom/templates/$CLASSROOM_ENV/fellowship \
            --value "$(cat template-updated.json)" \
            --overwrite
      - name: Terminate bake instance
        run: aws ec2 terminate-instances --instance-ids $BAKE_INSTANCE_ID
```
- Pre-pulls Docker images into new AMI (cold-start speedup)
- Atomically updates AMI ID in SSM Parameter Store
- Next classroom provision uses new AMI automatically

**Bake Instance User Data:**
```bash
#!/bin/bash
set -e

# Install Docker
amazon-linux-extras install docker -y
systemctl start docker

# Install Docker Compose
curl -L https://github.com/docker/compose/releases/download/...

# Download SUT tarball from S3
aws s3 cp s3://$SUT_BUCKET/sut.tar.gz /tmp/
docker load < /tmp/sut.tar.gz

# Pre-pull all images
cd /tmp/extract && docker compose pull

# Shutdown (bake task will snapshot)
shutdown -h now
```

### Required GitHub Secrets/Variables

| Name | Type | Description |
|------|------|-------------|
| `AWS_REGION` | Variable | Deployment region (e.g., `eu-west-1`) |
| `CLASSROOM_ENVIRONMENT` | Variable | Target environment (e.g., `prod`, `dev`) |
| `ECR_REGISTRY` | Secret | AWS ECR registry URI (`123456789012.dkr.ecr.eu-west-1.amazonaws.com`) |
| `ECR_REPO` | Secret | Repository name in ECR (e.g., `lotr-sut`) |
| `SUT_BUCKET` | Secret | S3 bucket for SUT tarballs (e.g., `classroom-sut-builds`) |
| `BAKE_SUBNET_ID` | Secret | Subnet for temporary bake instance (must route to Internet/ECR) |
| `BAKE_SECURITY_GROUP_ID` | Secret | Security group for bake instance (egress to DockerHub, ECR, S3) |
| `BAKE_IAM_INSTANCE_PROFILE` | Secret | Instance profile with S3:GetObject on SUT bucket + EC2:CreateImage |

## Manual Deployments

### Deploy via Terraform (Infrastructure)

```bash
cd iac/aws

# Validate syntax
terraform fmt -check && terraform validate

# Plan changes
terraform plan -out=tfplan -var="environment=prod" -var="region=eu-west-1"

# Apply (requires approval)
terraform apply tfplan

# Verify state
terraform output
```

**Caution:** Terraform changes affect all students in the classroom. Coordinate with instructors.

### Redeploy Specific Lambda (without CI/CD)

```bash
cd functions

# Package code
zip -r lambda-bundle.zip common/ handlers/

# Update Lambda
aws lambda update-function-code \
  --function-name classroom_instance_manager \
  --zip-file fileb://lambda-bundle.zip

# Verify
aws lambda get-function --function-name classroom_instance_manager | jq .Configuration.LastModified
```

### Force AMI Rebake (Skip Instance Manager Change)

```bash
# If SUT changed but GitHub Actions didn't trigger bake:
./scripts/bake_golden_ami.sh \
  --environment prod \
  --workshop fellowship \
  --dry-run  # preview before applying
```

## Deployment Validation Checklist

### After Deploying Lambda
- [ ] Unit tests passed in CI/CD
- [ ] Lambda function code was updated: `aws lambda get-function --function-name classroom_instance_manager | grep CodeSha256`
- [ ] Create test instance via UI to verify Lambda invocation
- [ ] Check CloudWatch logs for errors: `aws logs tail /aws/lambda/classroom_instance_manager --follow`

### After Baking Golden AMI
- [ ] Bake job completed without timeout
- [ ] New AMI ID published to SSM: `aws ssm get-parameter --name /classroom/templates/prod/fellowship | jq .Parameter.Value`
- [ ] Create new classroom with pool; verify instances boot in <60s (vs. cold-start 5-10 min)
- [ ] Verify Docker images are pre-pulled: `docker images` on new instance
- [ ] Check CloudWatch logs for bake instance user data errors

### Spot Instance Cleanup Validation
- [ ] E2E test passes: spot requests are properly cancelled after deletion
- [ ] No orphaned spot requests remain in AWS Console
- [ ] CloudWatch logs show `cancel_spot_instance_requests` being called

### Caddy Certificate Validation
- [ ] Instance has `HttpPutResponseHopLimit = 2`: `aws ec2 describe-instances ... | grep HttpPutResponseHopLimit`
- [ ] IAM role includes `route53:GetChange`: `aws iam get-role-policy --role-name ... --policy-name ...` 
- [ ] Caddy logs show DNS-01 challenge success: check instance SSM logs
- [ ] HTTPS endpoint accessible: `curl https://instance-domain.workshop.com/`

## Runbook: Deploy New Workshop

1. **Build workshop content** (Docker image, exercises, Dockerfile)
2. **Publish to ECR** (manual or via CI/CD)
3. **Update `setup_fellowship.sh`** (or equivalent) to reference new image
4. **Add workshop template** to SSM: `aws ssm put-parameter --name /classroom/templates/prod/new-workshop --value '...' --tier Standard`
5. **Bake AMI** with new template: `.github/workflows/build-deploy.yml` will auto-trigger on next push
6. **Test in dev** using mocked E2E: `npm run test:e2e`
7. **Manual test in live AWS**: Create instance via UI, verify endpoints
8. **Deploy to production** (requires approval) via GitHub Actions merge to `main`

## Runbook: Rollback a Deployment

### Lambda Code Rollback
```bash
# Get previous version
aws lambda list-versions-by-function --function-name classroom_instance_manager \
  --query 'Versions[-2]' | jq -r .CodeSha256

# Publish previous version as live
aws lambda publish-version --function-name classroom_instance_manager

# Update Lambda alias to point to previous version
aws lambda update-alias \
  --function-name classroom_instance_manager \
  --name live \
  --function-version <VERSION_NUMBER>
```

### Golden AMI Rollback
```bash
# Get previous AMI ID
aws ssm get-parameters-by-path --path /classroom/templates/prod \
  | jq '.Parameters[] | select(.Name == "...fellowship")'

# Manually publish previous AMI ID back to SSM
aws ssm put-parameter \
  --name /classroom/templates/prod/fellowship \
  --value '{"ami_id":"ami-xxxxx",...}' \
  --overwrite
```

New classrooms will use rolled-back AMI on next provision.

## Cost Tracking

- **Golden AMI snapshots:** Retain for 7 days or latest 3 (to save storage costs)
- **Bake instances:** Always terminated (even on failure) to prevent runaway costs
- **Spot instances:** Default choice (~70% savings); cleanup properly to prevent phantom relaunches
- **S3 SUT buckets:** Use Intelligent-Tiering or Archive rules for old tarballs
