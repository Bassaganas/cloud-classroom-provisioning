# Changelog

All notable changes to cloud-classroom-provisioning are documented here. This changelog focuses on user-visible and operational changes; see the individual reports in LEGACY_REPORTS.md for detailed technical analysis.

## [April 2026] — Golden AMI & Wildcard Certificate Stability

### Added
- **Golden AMI Pipeline** - GitHub Actions `bake-ami` job automatically snapshots EC2 instances after SUT deployment
  - Pre-pulls Docker images (10-15 min bake time vs. 5-10 min cold-start on first launch)
  - Atomically publishes AMI ID to SSM (`/classroom/templates/{env}/{workshop}`)
  - Bake instance always terminated, even on failure (prevents cost runaway)

- **Domain Endpoint Tags** - Instance tags now include `JenkinsDomain` and `IdeDomain`
  - Jenkins URL: `https://jenkins-{caddy-domain}`
  - IDE URL: `https://ide-{caddy-domain}`
  - Enables frontend to surface all workshop endpoints without fetching additional metadata

- **E2E Spot Instance Safeguard** - Comprehensive test for persistent spot termination
  - Validates that spot requests are properly cancelled (not just instances terminated)
  - Detects phantom replacement instances via 120-second stability window
  - Fails if spot request remains active (early warning before production)

### Fixed
- **User Data Accumulation Bug** - Multi-instance launches (count > 1) no longer duplicate domain exports
  - Root cause: Instance manager decoded user data once, mutated in-place for each instance
  - Fix: Reset `user_data = base_user_data` at start of each loop iteration
  - Regression test: `test_golden_ami_launch_contract.py`

- **Missing Route53 Permission** - Caddy DNS-01 challenge now succeeds
  - Root cause: Instance IAM role lacked `route53:GetChange` permission (required to wait for DNS propagation)
  - Fix: Added `route53:GetChange` to all instance IAM policies
  - Verified in both Terraform modules and Lambda instance manager

- **EC2 Metadata Hop Limit** - Docker containers can now access IMDS (required for IAM token refresh)
  - Root cause: Default `HttpPutResponseHopLimit = 1` blocks packets from containers (one hop away)
  - Fix: Set `HttpPutResponseHopLimit = 2` on all instances (EC2 host + containers)
  - Verified in both pool instances (Terraform) and on-demand instances (Lambda)

- **Spot Instance Phantom Relaunches** - Persistent spot requests properly cancelled on deletion
  - Root cause: Calling `terminate_instances()` without `cancel_spot_instance_requests()` leaves request active
  - Fix: New `terminate_instance_properly()` helper in Lambda detects spot instances and cancels requests
  - Verified in both E2E cleanup and Lambda lifecycle manager
  - Test: `test_delete_pool_instance_via_ui` now passes (spot request is cancelled, not active)

- **Caddyfile Domain Mapping** - Correct domain exports in `setup_fellowship.sh`
  - Root cause: Script derived `JENKINS_DOMAIN` and `IDE_DOMAIN` variables locally but never exported them for container use
  - Fix: Export all three domain variables (CADDY_DOMAIN, JENKINS_DOMAIN, IDE_DOMAIN) in user data
  - Result: Containers can read endpoints from environment instead of instance tags

- **Golden AMI SSM Template Publishing** - `republish_template.sh` now publishes individual workshop parameters
  - Root cause: Script only published combined template JSON fallback, leaving individual workshop parameters stale
  - Fix: Loop over workshop names and publish each one (Standard tier) before combined fallback (Advanced tier)
  - Result: Lambda falls back to individual parameter on first try (faster, cheaper)

### Security
- **IMDS Access Hardening** - Hop limit of 2 is minimum; no higher (prevents privilege escalation via container escape)
- **No Credential Exposure** - All domain names and secrets in environment variables, never in logs
- **Least Privilege IAM** - Spot cancellation permission granular (only `ec2:CancelSpotInstanceRequests` needed)

### Testing
- **Unit Tests**: 15+ passing (IAM policies, user data generation, spot termination logic)
- **Integration Tests**: 16 passing E2E tests in mock mode
- **Live AWS Validation**: Spot termination test passes (verifies fix deployed)

### Deployment
- All changes deployed via GitHub Actions on `main` pushes
- Golden AMI bake job runs after successful unit tests + deploy
- No manual Terraform apply required for bake setup (GHA uses automated role)
- Rollback: Previous AMI ID can be restored in SSM Parameter Store

---

## [Before April 2026] — Initial Setup & Architecture

### Baseline Features
- Student/instructor multi-tenancy with isolated EC2 instances
- CloudFront edge distribution for workshop content
- Lambda instance manager with TTL-based cleanup
- Route53 integration for domain allocation
- Secrets Manager for API key storage
- Terraform IaC for infrastructure versioning
- E2E test suite (Playwright + pytest)

### Known Limitations (Addressed in April 2026)
- ⚠️ Caddy certificate provisioning required manual troubleshooting (missing permissions/hops)
- ⚠️ Spot instance cleanup could leave requests active, causing phantom relaunches
- ⚠️ Instance cold-start 5-10 minutes (before golden AMI caching)
- ⚠️ Domain endpoints not reflected in instance tags (frontend had to infer)
- ⚠️ Multi-instance launches could have duplicate user data exports

---

## Breaking Changes

- **IMDS Hop Limit Change** - Existing instances created before April 2026 cannot be updated post-launch
  - Workaround: Terminate and re-provision instances (Pool/Lambda will use updated settings)
  - Impact: Low (classroom instances are ephemeral, typically <24 hr lifetime)

- **IAM Permission Addition** - New `route53:GetChange` permission required on instance roles
  - Automated via Terraform `apply` (no manual action needed)
  - Impact: Minimal (read-only, no risk to existing permissions)

---

## Deprecations

- **Individual Workshop SSM Parameters** - Still supported but combined template JSON is preferred
  - Old path: `/classroom/templates/{env}/{workshop}` (Standard tier)
  - New path: `/classroom/templates/{env}` (Advanced tier, auto-fallback)
  - Migration: Run `republish_template.sh` to create both formats

---

## Migration Guide: From Broken Spot/Certificate Setup

**Scenario:** Classroom provisioned before April 2026 spot/cert fixes applied

**Steps:**
1. **Terminate existing classroom instances** (will auto-relaunch if spot requests not cancelled)
   ```bash
   ./scripts/setup_classroom.sh --name fellowship-oldprod --destroy
   ```

2. **Update Lambda functions** (baked into next GH Actions push or manually):
   ```bash
   cd functions
   zip -r lambda-bundle.zip common/ handlers/
   aws lambda update-function-code --function-name classroom_instance_manager --zip-file fileb://lambda-bundle.zip
   aws lambda update-function-code --function-name classroom_stop_old_instances --zip-file fileb://lambda-bundle.zip
   ```

3. **Update Terraform modules** (IAM roles, hop limit):
   ```bash
   cd iac/aws
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

4. **Rebake Golden AMI** (optional, for cold-start speedup):
   ```bash
   ./scripts/bake_golden_ami.sh --environment prod --workshop fellowship
   ```

5. **Re-provision classroom** with new Lambdas + Terraform changes:
   ```bash
   ./scripts/setup_classroom.sh \
     --name fellowship-prod \
     --cloud aws \
     --region eu-west-1 \
     --environment prod \
     --workshop fellowship \
     --with-pool \
     --pool-size 10
   ```

6. **Validate fixes**:
   - [ ] Instances boot and get HTTPS certificates (check Caddy logs)
   - [ ] Spot instances are properly cleaned up (no phantom relaunches)
   - [ ] Golden AMI is used (cold-start <60s)

---

## Contributors & Attribution

- **Wildcard Certificate Fix** - Identified IMDS hop limit issue, verified Route53:GetChange permission
- **Spot Instance Safeguard** - Designed E2E test, implemented cancel path, verified cleanup
- **Golden AMI Pipeline** - Built GitHub Actions bake job, metrics for cold-start improvement
- **User Data Accumulation** - Caught multi-instance bug, implemented regression test

See LEGACY_REPORTS.md for detailed investigation timelines and root cause analysis.
