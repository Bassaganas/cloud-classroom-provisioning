# FAQ

## What is this project in one sentence?
Cloud Classroom Provisioning creates and manages AWS workshop environments with fast EC2 lifecycle operations, HTTPS domains, and CI/CD-driven updates.

## Which docs should I read first?
1. [README.md](README.md)
2. [REQUIREMENTS.md](REQUIREMENTS.md)
3. [DEPLOYMENTS.md](DEPLOYMENTS.md)
4. [TESTS.md](TESTS.md)
5. [CHANGELOG.md](CHANGELOG.md)

## Why do we use Spot instances by default?
Spot instances reduce cost significantly (about 70% in typical classroom workloads). The platform includes explicit cancellation of Spot requests during deletion to avoid phantom relaunches.

## Why is EC2 metadata hop limit set to 2?
Containers (for example Caddy) need IMDS access through one network hop. With hop limit 1, IAM credential retrieval from containers fails.

## Why was `route53:GetChange` added?
Caddy’s DNS-01 flow waits for Route53 propagation. Without `route53:GetChange`, certificate issuance and renewal fail.

## What is Golden AMI used for?
Golden AMI pre-pulls workshop images so new instances start quickly. CI/CD updates AMI IDs in SSM so new launches pick up the latest baked image automatically.

## Where are workshop templates stored?
In SSM Parameter Store. The system prefers individual workshop parameters and falls back to a combined map for compatibility.

## Can this run without shared-core mode?
Yes. Shared-core mode is a switch. If disabled, student assignments use per-instance service endpoints.

## What are the most common failure categories?
1. Spot request not cancelled during delete
2. IMDS access blocked from containers
3. Route53 permissions missing
4. Template mismatch in SSM

Use [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for quick fixes.