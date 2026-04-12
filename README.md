# Cloud Classroom Provisioning

[![Documentation](https://img.shields.io/badge/docs-live-brightgreen)](https://Bassaganas.github.io/cloud-classroom-provisioning/)

Provisioning stack for LOTR workshop environments on AWS, with separate student and instructor access paths, EC2 lifecycle automation, and CI/CD deployment workflows.

## Canonical Documentation Set

The documents below are the maintained source of truth for this repository root:

- [README.md](README.md): Project overview, current status, and quick start.
- [REQUIREMENTS.md](REQUIREMENTS.md): Functional, security, and operational requirements.
- [TESTS.md](TESTS.md): Test strategy, test modes, and execution commands.
- [DEPLOYMENTS.md](DEPLOYMENTS.md): CI/CD flow, manual deployment, and checklists.
- [CHANGELOG.md](CHANGELOG.md): Consolidated release and fix history.
- [FAQ.md](FAQ.md): Short answers to common platform and operations questions.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md): Problems and solutions.

Website docs remain available at:
[https://Bassaganas.github.io/cloud-classroom-provisioning/](https://Bassaganas.github.io/cloud-classroom-provisioning/)

## Current State (April 2026)

- Wildcard certificate provisioning fixes are implemented and deployment-ready.
    - EC2 metadata hop limit set to 2 where instances are created.
    - Route53 permission set includes `route53:GetChange`.
- Spot instance lifecycle reliability is improved.
    - Termination path now cancels spot requests to prevent phantom relaunches.
- Core E2E suite is green: 16/16 passing in recent runs.
- Golden AMI pipeline support exists via GitHub Actions bake flow.

## Architecture Summary

- Student path: CloudFront -> workshop Lambda functions serving student experiences.
- Instructor path: CloudFront/S3 React UI -> API Gateway -> instance manager Lambda.
- Shared services: EC2 pool, DynamoDB, SSM Parameter Store, Secrets Manager.
- IaC: Terraform modules under `iac/aws`.

## Quick Start

Deploy a classroom with pool instances:

```bash
./scripts/setup_classroom.sh \
    --name fellowship-dev \
    --cloud aws \
    --region eu-west-1 \
    --environment dev \
    --workshop fellowship \
    --with-pool \
    --pool-size 10
```

Deploy low-cost dev infrastructure without pool provisioning:

```bash
./scripts/setup_classroom.sh \
    --name fellowship-dev \
    --cloud aws \
    --region eu-west-1 \
    --environment dev \
    --workshop fellowship
```

Destroy an environment:

```bash
./scripts/setup_classroom.sh \
    --name fellowship-dev \
    --cloud aws \
    --region eu-west-1 \
    --environment dev \
    --workshop fellowship \
    --destroy
```

## Documentation Structure

**Primary Documentation (Maintained):**
- This README provides overview and quick start
- [REQUIREMENTS.md](REQUIREMENTS.md) details functional, security, and operational requirements
- [TESTS.md](TESTS.md) documents test strategy, modes, and execution
- [DEPLOYMENTS.md](DEPLOYMENTS.md) covers CI/CD workflows, Golden AMI baking, and checklists
- [CHANGELOG.md](CHANGELOG.md) lists fixes and features
- [FAQ.md](FAQ.md) provides concise operational answers
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) provides issue-to-fix playbooks

For most day-to-day work, these seven files are sufficient.
