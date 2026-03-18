# E2E Test Suite for EC2 Manager

## Overview

This directory contains end-to-end (e2e) tests for the EC2 Manager frontend, combining Playwright for UI automation with Boto3 for AWS state validation.

## Features

- **BDD-based**: Tests written in Gherkin (`.feature` files)
- **UI + AWS validation**: Each test verifies both UI state and AWS resources
- **Isolated resources**: All test resources tagged with `e2e-tests-*` prefix for easy cleanup
- **FIRST principle**: Fast, Independent, Repeatable, Self-validating, Timely tests
- **Automatic cleanup**: Global teardown removes all leftover test resources

## Folder Structure

```
e2e/
  features/                 # Gherkin feature files
    instance_management.feature
    admin_instance_days.feature
    tutorial_session.feature
    landing_page.feature
  steps/                    # Pytest-BDD step definitions
    conftest.py
    instance_management_steps.py
    admin_instance_days_steps.py
    tutorial_session_steps.py
    landing_page_steps.py
  utils/                    # Shared utilities
    aws_boto3_client.py     # AWS client initialization
    aws_helpers.py          # AWS operations (EC2, Route53, Lambda)
    uuid_utils.py           # Unique identifier utilities
  playwright.config.js      # Playwright configuration
  pytest.ini                # Pytest configuration
  requirements.txt          # Python dependencies
  .env                      # Environment configuration (AWS credentials, etc.)
  cleanup.py                # Global cleanup script
  README.md                 # This file
```

## Setup

### Prerequisites

- Python 3.9+
- pip
- AWS account credentials (DEV environment)

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Configure `.env` file with:
   - AWS credentials (access key ID and secret)
   - Route53 hosted zone ID (from your AWS account)
   - EC2 Manager URL

3. Get Route53 Hosted Zone ID:
   ```bash
   aws route53 list-hosted-zones
   ```
   Add the zone ID to `.env` as `INSTANCE_MANAGER_HOSTED_ZONE_ID`

## Running Tests

### Run all tests:
```bash
pytest features/ -v
```

### Run specific feature:
```bash
pytest features/instance_management.feature -v
```

### Run tests with specific marker:
```bash
pytest -m instance_management -v
```

### Run tests with detailed output:
```bash
pytest features/ -v -s
```

### Generate HTML report:
```bash
pytest features/ --html=report.html
```

## Test Scenarios

### Instance Management (`instance_management.feature`)
- Create pool instance via UI
- Delete pool instance via UI
- Bulk delete pool instances
- Delete admin instance via UI

### Admin Instance Days (`admin_instance_days.feature`)
- Display remaining days for admin instance
- Extend admin instance days
- Auto-delete admin instance after days expire (via Lambda trigger)

### Tutorial Session (`tutorial_session.feature`)
- Add new tutorial session
- Delete tutorial session (cascade deletion of resources)

### Landing Page (`landing_page.feature`)
- Display overview and workshop cards
- Display and filter cost by time period

## Key Concepts

### Resource Naming
All test-created resources are prefixed with `e2e-tests-<uuid>` to ensure isolation and enable cleanup.

### AWS Validation
Each scenario uses Boto3 to verify:
- EC2 instances exist/are terminated
- Route53 records created/deleted
- Instance tags are correct
- Lambda invocations succeed

### FIRST Principles
- **Fast**: Tests run in parallel where possible
- **Independent**: Each test creates and cleans up its own resources
- **Repeatable**: Tests can run multiple times without conflicts
- **Self-validating**: Clear pass/fail assertions
- **Timely**: Tests verify critical cost-impacting operations

## Cleanup

### Automatic Cleanup
All tests run a global teardown that automatically removes leftover resources.

### Manual Cleanup
To manually clean up all E2E test resources:
```bash
python cleanup.py
```

## Environment Variables

Required (in `.env`):
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_REGION`: AWS region (default: eu-west-3)
- `INSTANCE_MANAGER_HOSTED_ZONE_ID`: Route53 hosted zone ID
- `INSTANCE_MANAGER_BASE_DOMAIN`: Route53 base domain (default: testingfantasy.com)

Optional:
- `TEST_HEADLESS`: Run Playwright in headless mode (default: true)
- `TEST_TIMEOUT`: Test timeout in ms (default: 30000)

## Assumptions

1. **EC2 Manager URL**: The frontend is deployed at `https://ec2-management-dev.testingfantasy.com/`
2. **AWS Region**: All resources are created in `eu-west-3`
3. **Workshop/Environment**: Tests target the `fellowship` workshop in `dev` environment
4. **Instance IDs**: AWS-generated instance IDs (e.g., `i-xxxxxxxxxxxxxxx`) are displayed in the UI
5. **Lambda Functions**: `classroom_admin_cleanup` and `classroom_stop_old_instances` are deployed
6. **DynamoDB**: Table `instance-assignments-fellowship-dev` exists
7. **Route53**: Hosted zone is configured for `testingfantasy.com`
8. **IAM Permissions**: AWS credentials have permissions for EC2, Route53, Lambda, DynamoDB operations

## Troubleshooting

### Test fails with "No hosted zone found"
- Ensure `INSTANCE_MANAGER_HOSTED_ZONE_ID` is set in `.env`
- Verify the zone ID with: `aws route53 list-hosted-zones`

### Test fails with "Instance not found in AWS"
- Wait a moment after UI operations for AWS to process
- Check CloudWatch logs for Lambda errors

### Cleanup not removing resources
- Manually check AWS console for leftover instances
- Run `python cleanup.py` with verbose logging:
  ```bash
  python -u cleanup.py
  ```

## Continuous Integration

To run in CI/CD:
1. Set environment variables instead of using `.env`
2. Run: `pytest features/ -v --junitxml=junit.xml`
3. Archive test results and cleanup at the end

## Contributing

When adding new scenarios:
1. Write feature file in Gherkin syntax
2. Implement step definitions in corresponding `steps/*.py`
3. Use `e2e-tests-*` prefix for all resources
4. Ensure cleanup is implemented
5. Test locally before committing

## License

Internal use only.
