# E2E Test Suite for EC2 Manager

## Overview

This directory contains end-to-end (e2e) tests for the EC2 Manager frontend, combining Pytest fixtures for test organization with Boto3 for AWS state validation.

## Features

- **Requirement specs**: Tests documented in Gherkin (`.feature` files) for clarity
- **Pytest-based**: Test implementations using standard Pytest fixtures
- **UI + AWS validation**: Each test verifies both UI state and AWS resources (future Playwright integration)
- **Isolated resources**: All test resources tagged with `e2e-tests-*` prefix for easy cleanup
- **FIRST principle**: Fast, Independent, Repeatable, Self-validating, Timely tests
- **Automatic cleanup**: Global teardown removes all leftover test resources
- **AWS Integration**: Direct Boto3 integration for verifying EC2, Route53, Lambda state

## Folder Structure

```
e2e/
  features/                 # Gherkin feature files (requirements specification)
    instance_management.feature
    admin_instance_days.feature
    tutorial_session.feature
    landing_page.feature
  tests/                    # Pytest test implementations
    conftest.py            # Pytest fixtures and session setup
    test_instance_management.py
    test_admin_instance_days.py
    test_tutorial_session.py
    test_landing_page.py
  utils/                    # Shared utilities
    aws_boto3_client.py     # AWS client initialization
    aws_helpers.py          # AWS operations (EC2, Route53, Lambda)
    uuid_utils.py           # Unique identifier utilities
  playwright.config.js      # Playwright configuration (future Playwright UI tests)
  pytest.ini                # Pytest configuration and markers
  requirements.txt          # Python dependencies
  .env                      # Environment configuration (AWS credentials)
  .gitignore                # Git ignore file
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
pytest tests/ -v
```

### Run specific test file:
```bash
pytest tests/test_instance_management.py -v
```

### Run tests with specific marker:
```bash
pytest tests/ -m instance -v
```

### Run tests with detailed output:
```bash
pytest tests/ -v -s
```

### Generate HTML report:
```bash
pytest tests/ --html=report.html
```

## Test Organization

Tests are organized into four main modules:

- **test_instance_management.py**: Pool and admin instance creation, deletion, and validation
- **test_admin_instance_days.py**: Admin instance days management and auto-deletion
- **test_tutorial_session.py**: Tutorial session creation, deletion, and cascade operations
- **test_landing_page.py**: Landing page overview and cost display

Each test module contains test cases organized by feature and function.

## Available Pytest Markers

- `@pytest.mark.e2e`: All e2e tests
- `@pytest.mark.instance`: Instance management tests
- `@pytest.mark.admin`: Admin instance tests
- `@pytest.mark.session`: Tutorial session tests
- `@pytest.mark.landing`: Landing page tests
- `@pytest.mark.slow`: Slow-running tests

Run tests by marker:
```bash
pytest tests/ -m instance -v
```

## Test Scenarios

### Instance Management
- Create pool instance via UI
- Delete pool instance via UI
- Bulk delete pool instances
- Delete admin instance via UI
- Verify EC2 instance creation in AWS
- Verify Route53 record operations
- Verify instance tags

### Admin Instance Days
- Display remaining days for admin instance
- Extend admin instance days
- Auto-delete admin instance after days expire
- Verify cleanup Lambda availability

### Tutorial Session
- Add new tutorial session
- Delete tutorial session (cascade deletion)
- Verify instances created for sessions

### Landing Page
- Display workshop overview
- Display instance count
- Display and filter cost
- Verify AWS integration

## Key Concepts

### Resource Naming
All test-created resources are prefixed with `e2e-tests-<uuid>` to ensure isolation and enable cleanup.

### AWS Validation
Each test can use Boto3 utilities to verify:
- EC2 instances exist/are terminated
- Route53 records created/deleted
- Instance tags are correct
- Lambda invocations succeed

### FIRST Principles
- **Fast**: Tests run in ~1 second for current structure
- **Independent**: Each test has its own fixtures and cleanup
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
9. **Playwright**: UI automation tests will require Playwright when implemented (currently test structure is ready)

## Test Status

✅ **16 tests passing**

### Current Test Coverage
- ✅ Instance management structure (5 tests)
- ✅ Admin instance days (4 tests)
- ✅ Tutorial session (3 tests)
- ✅ Landing page (4 tests)

## Future Enhancements

- **Playwright Integration**: Add Playwright for UI automation tests
- **Database Validation**: Add DynamoDB verification for instance assignments
- **Cost Explorer Validation**: Verify AWS Cost Explorer data
- **Performance Tests**: Add load and performance testing
- **Error Scenarios**: Add negative testing for error cases

## Contributing

When adding new scenarios:
1. Add feature spec to relevant `.feature` file
2. Implement test in corresponding `tests/test_*.py`
3. Use `e2e-tests-*` prefix for all resources
4. Ensure cleanup is implemented
5. Test locally before committing

## Troubleshooting

### Test fails with "No hosted zone found"
- Ensure `INSTANCE_MANAGER_HOSTED_ZONE_ID` is set in `.env`
- Verify the zone ID with: `aws route53 list-hosted-zones`

### Test fails with "Instance not found in AWS"
- Wait a moment after UI operations for AWS to process (tests already include waits)
- Check CloudWatch logs for Lambda errors

### Cleanup not removing resources
- Manually check AWS console for leftover instances
- Run `python cleanup.py` with verbose logging

## License

Internal use only.
