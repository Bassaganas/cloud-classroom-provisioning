# Blue/Green Workshop Migration Runbook

This runbook helps you migrate from the current single-workshop stack to the new
workshop-aware roots without breaking production.

## 1) Snapshot current (legacy) stack

1. Identify the legacy backend (S3 bucket + DynamoDB lock table) used by the
   current production stack.
2. Pull and archive the legacy state:

```bash
cd iac/aws/workshops/testus_patronus
terraform init
terraform state pull > ../../../../migration-legacy-state.json
```

3. Capture current outputs (Lambda URLs, CloudFront, etc.):

```bash
terraform output -json > ../../../../migration-legacy-outputs.json
```

4. Record existing DNS entries (GoDaddy/Route53) for:
- Instance Manager domain
- User Management domain
- Dify Jira domain

## 2) Prepare new workshop backend (do not reuse legacy state)

Before deploying the new stack, update `iac/aws/workshops/testus_patronus/backend.tf`
to a **new** S3 bucket/key and DynamoDB lock table to avoid touching legacy state.

## 3) Deploy shared/common stack (optional)

```bash
cd iac/aws/common
terraform init
terraform apply -auto-approve
```

## 4) Deploy new workshop stack (parallel)

```bash
cd iac/aws/workshops/testus_patronus
terraform init
terraform apply -auto-approve
```

This deployment now also creates the per-workshop storage resources:
- DynamoDB table `instance-assignments-<workshop>-<env>`
- SSM parameters under `/classroom/<workshop>/<env>/...`
- Secrets Manager secret `classroom/<workshop>/<env>/instance-manager/password`

## 5) Validate new stack

- Instance Manager UI `/ui`
- Lambda logs (CloudWatch)
- DynamoDB table `instance-assignments-testus_patronus-<env>`
- SSM params under `/classroom/testus_patronus/<env>/...`
- Resource Group for `WorkshopID=testus_patronus`

## 6) Cutover (DNS)

Update DNS to point to the new CloudFront distributions. Keep the legacy stack
running until validation is complete and stable.

## 7) Decommission legacy stack

After a stable window, destroy the legacy stack from its original backend:

```bash
cd iac/aws/workshops/testus_patronus
terraform destroy -auto-approve
```

Archive the legacy state files and remove old DNS records.
