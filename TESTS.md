# Tests

## Test Strategy

The test suite covers three layers: **unit** (Lambda functions), **integration** (local + AWS), and **E2E** (full classroom workflow via UI).

### Unit Tests
**Location:** `functions/tests/`  
**Framework:** pytest  
**Purpose:** Validate Lambda function logic, IAM policies, user data generation, and instance manager contracts

**Key Test Files:**
- `test_golden_ami_launch_contract.py` - Validates golden AMI, domain injection, and multi-instance handling
- `test_iam_policies.py` - Verifies least-privilege IAM role definitions
- `test_instance_manager_*.py` - Tests user data scripts, domain exports, and instance tags

**Run Locally:**
```bash
cd functions
python -m pytest tests/ -v
```

### Integration Tests
**Location:** `e2e/tests/`  
**Framework:** pytest + Playwright (Python)  
**Purpose:** Test classroom provisioning workflow with mocked or real AWS calls

**Test Modes:**
1. **Mock mode** (default, no AWS credentials needed):
   - Simulates AWS API responses using `mockData.js`
   - Fast (~5-10 min per suite)
   - Useful for CI/CD and developer iteration

2. **Live AWS mode** (requires AWS credentials and environment setup):
   - Creates real instances, domains, security groups
   - Slow (~30-45 min per suite)
   - Validates actual provisioning path
   - **Requires cleanup**: E2E cleanup function cancels persistent spot requests to prevent phantom relaunches

**Key Test Files:**
- `test_instance_management.py::TestInstanceManagement::test_delete_pool_instance_via_ui` - **Spot instance bug test**
  - Creates 2 pool instances via UI
  - Deletes both via UI
  - Validates spot requests are properly cancelled (not left active)
  - Takes ~8-9 min; fails if spot request remains active after deletion (indicates unpatched backend)

**Run in Mock Mode:**
```bash
cd frontend/ec2-manager
npm run test:e2e  # Optional: MOCK_AWS=true npm run test:e2e
```

**Run Against Live AWS:**
```bash
export AWS_REGION=eu-west-1
export TEST_MODE=live  # or omit; defaults to mock
cd e2e
python -m pytest tests/test_instance_management.py -v --tb=short
```

### E2E Frontend Tests (Playwright)
**Location:** `frontend/ec2-manager/tests/e2e/`  
**Framework:** Playwright + BDD (Gherkin via `steps.js`)  
**Purpose:** Validate React UI rendering, form interactions, and API contracts

**Key Scenarios:**
- Tutorial dashboard loads and displays instances
- Create instance dialog accepts pool size, workshop, region
- Instance endpoint links display https_domain (fellowship-pool-0.domain.com)
- Delete button removes instance from table

**BDD Step Definitions:** `frontend/ec2-manager/tests/e2e/bdd/steps.js`

**Page Objects:** `frontend/ec2-manager/tests/e2e/pom/`

**Run:**
```bash
cd frontend/ec2-manager
npm run test:e2e
```

## Test Execution & Validation

### Local Development Workflow
1. Write/modify code
2. Run unit tests: `cd functions && python -m pytest tests/ -k <test_name> -v`
3. Verify in mock E2E: `cd e2e && npm test` (mock mode)
4. If changing infrastructure, run live E2E in dev environment (manual triggers only)

### CI/CD Workflow (GitHub Actions)
**File:** `.github/workflows/build-deploy.yml`

**On every push to `main`:**
1. **Unit tests** (functions/tests/) - must pass
2. **Build** SUT Docker image, publish to ECR + S3
3. **Deploy** updated Lambda functions and Terraform modules
4. **Bake Golden AMI** - launch instance, pre-pull Docker images, snapshot
5. **Publish** new AMI ID to SSM (for next classroom provision)

**Golden AMI Bake Job Details:**
- Resolves current `ami_id` from SSM `/classroom/templates/{env}/{workshop}`
- Launches temporary EC2 instance with user-data that pulls SUT images
- Waits for instance to stop (up to 15 min)
- Snapshots to named AMI (`fellowship-sut-golden-<commit>-<timestamp>`)
- Publishes new AMI ID back to SSM
- Always terminates bake instance (even on failure)

**Spot Instance Cleanup (E2E):**
- E2E tests create spot instances via UI or Lambda
- Cleanup fixtures call `terminate_instance_properly()` which:
  1. Detects spot instance via `InstanceLifecycle == 'spot'`
  2. Extracts `SpotInstanceRequestId` from instance tags
  3. Calls `cancel_spot_instance_requests(SpotInstanceRequestIds=[...], TerminateInstances=True)`
  4. Falls back to regular termination if spot cancellation fails
- **Why required**: Spot instances created with `SpotInstanceType: 'persistent'` are auto-replaced if terminated without cancellation

## Test Coverage & Known Gaps

### Covered
- ✅ Instance provisioning (pool + on-demand)
- ✅ Domain injection and tag correctness
- ✅ Multi-instance user data (no accumulation)
- ✅ Spot instance termination (cancellation verified)
- ✅ Golden AMI caching and cold-start reduction
- ✅ Caddy wildcard certificate provisioning (DNS-01)
- ✅ IMDS hop limit protection (Docker containers access IAM)

### Not Yet Covered (Known Gaps)
- [ ] Instructor SSH ingress (security group rules)
- [ ] Workshop content validation (exercises artifact integrity)
- [ ] CloudFront distribution caching headers
- [ ] Cost reporting and spot savings validation
- [ ] Multi-region failover (if one region is unavailable)

## Debugging Failed Tests

### Spot Instance Test Failure ("active" state)
**Symptom:** `AssertionError: Spot request sir-xxxxx is still active (active) after instance deletion. Expected cancelled/closed.`

**Cause:** Backend Lambda (`classroom_stop_old_instances.py`) not calling `cancel_spot_instance_requests()`.

**Fix:** Verify Lambda deployment includes the spot termination fix:
```bash
aws lambda get-function-code --function-name classroom_stop_old_instances \
  | grep -i cancel_spot_instance_requests
```

### Golden AMI Accumulation Bug ("export CADDY_DOMAIN" duplicated)
**Symptom:** User data contains multiple `export CADDY_DOMAIN=` lines with stale values.

**Cause:** Instance manager decoded user data once before loop, mutated in-place.

**Fix:** Verify Lambda deployment includes the golden AMI fix (base_user_data reset each iteration).

### IMDS Credential Errors (Docker containers)
**Symptom:** Caddy logs show `no EC2 IMDS role found` inside container.

**Cause:** EC2 metadata hop limit is 1 (default); Docker bridges require hop limit 2.

**Fix:** Verify instances have `HttpPutResponseHopLimit = 2`:
```bash
aws ec2 describe-instances --instance-ids <id> \
  --query 'Reservations[0].Instances[0].MetadataOptions'
```

### DNS-01 Challenge Failure (Caddy)
**Symptom:** Caddy logs show `route53:GetChange permission denied`.

**Cause:** Instance IAM role missing `route53:GetChange` permission.

**Fix:** Update instance IAM policy to include `route53:GetChange` (ARN: `*`, reads only).
