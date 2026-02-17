# Conference Scale Testing Guide (100 Users)

This guide explains how to run performance tests at conference scale (100 users) to validate system behavior under realistic load.

## Overview

For a conference with 100 users, you need to test:
1. **Scenario 1**: 100 new users arriving and getting instances
2. **Scenario 2**: 100 users refreshing their pages (persistence)
3. **Scenario 3**: Instance termination and reassignment with 50+ users

## Prerequisites

### 1. Instance Pool Preparation

You need to prepare enough instances for each scenario:

```bash
# Scenario 1: 100 instances for 100 users
export INSTANCE_POOL_SIZE=100
./run_k6_tests.sh prepare --count 100

# Scenario 2: 100+ instances (pool should be >= users)
export INSTANCE_POOL_SIZE=100
./run_k6_tests.sh prepare --count 100

# Scenario 3: 150 instances (100 users + 50 terminated)
export INSTANCE_POOL_SIZE=150
./run_k6_tests.sh prepare --count 150
```

### 2. Environment Variables

```bash
export USER_MANAGEMENT_URL="https://testus-patronus.testingfantasy.com/"
export INSTANCE_MANAGER_URL="https://ec2-management.testingfantasy.com/"
export INSTANCE_MANAGER_PASSWORD="your-password"
```

## Running Tests

### Scenario 1: 100 New Users

**Purpose**: Test initial assignment of 100 instances to 100 new users

**Configuration**:
```bash
export INSTANCE_POOL_SIZE=100
./run_k6_tests.sh scenario1
```

**What it tests**:
- 100 concurrent new user requests
- Each user gets a unique instance
- System handles IAM rate limiting (5 req/sec)
- Total duration: ~60-90 seconds (due to IAM limits)

**Expected Results**:
- ✅ 100% instance assignment (all users get instances)
- ✅ Response time: P95 < 15s
- ✅ Error rate < 30% (some IAM throttling expected)
- ✅ Success rate > 70%

**IAM Rate Limiting**:
- Each user creation = 3 IAM calls (CreateUser, CreateLoginProfile, AttachUserPolicy)
- 100 users = 300 IAM calls
- At 5 calls/sec = 60 seconds minimum
- With retries and throttling: ~90-120 seconds total

### Scenario 2: 100 Users Persistence

**Purpose**: Test that 100 users maintain their instances across refreshes

**Configuration**:
```bash
export NUM_USERS=100
export REFRESHES_PER_USER=10
export INSTANCE_POOL_SIZE=100
./run_k6_tests.sh scenario2
```

**What it tests**:
- 100 users each make 11 requests (1 initial + 10 refreshes)
- Total: 1,100 requests
- Each user should maintain same instance across all refreshes

**Expected Results**:
- ✅ 100% persistence rate (same instance on all refreshes)
- ✅ Response time: P95 < 5s
- ✅ Error rate < 5%
- ✅ All users maintain their assigned instances

**Duration**: ~5-10 minutes (depending on refresh rate)

### Scenario 3: Termination with 50 Users

**Purpose**: Test termination and reassignment with larger user count

**Configuration**:
```bash
export NUM_USERS=50
export INSTANCE_POOL_SIZE=75  # 50 users + 25 terminated
./run_k6_tests.sh scenario3
```

**What it tests**:
- 50 users get instances
- First 25 users have their instances terminated
- System automatically reassigns new instances
- Verifies all users eventually get new instances

**Expected Results**:
- ✅ 100% termination detection
- ✅ >70% reassignment success
- ✅ Response time: P95 < 10s
- ✅ Error rate < 10%

**Note**: For full 100-user termination test, you'd need 150 instances:
```bash
export NUM_USERS=100
export INSTANCE_POOL_SIZE=150  # 100 users + 50 terminated
./run_k6_tests.sh scenario3
```

## Running All Scenarios Sequentially

To run a full conference-scale test suite:

```bash
#!/bin/bash
# Full conference test suite

export USER_MANAGEMENT_URL="https://testus-patronus.testingfantasy.com/"
export INSTANCE_MANAGER_URL="https://ec2-management.testingfantasy.com/"
export INSTANCE_MANAGER_PASSWORD="your-password"

echo "=== Preparing 150 instances for all scenarios ==="
export INSTANCE_POOL_SIZE=150
./run_k6_tests.sh prepare --count 150

echo "Waiting 2 minutes for instances to initialize..."
sleep 120

echo "=== Scenario 1: 100 New Users ==="
export INSTANCE_POOL_SIZE=100
./run_k6_tests.sh scenario1

echo "Waiting 30 seconds..."
sleep 30

echo "=== Scenario 2: 100 Users Persistence ==="
export NUM_USERS=100
export REFRESHES_PER_USER=10
export INSTANCE_POOL_SIZE=100
./run_k6_tests.sh scenario2

echo "Waiting 30 seconds..."
sleep 30

echo "=== Scenario 3: Termination with 50 Users ==="
export NUM_USERS=50
export INSTANCE_POOL_SIZE=75
./run_k6_tests.sh scenario3

echo "=== All tests completed ==="
```

## Performance Expectations

### Scenario 1 (100 New Users)
- **Duration**: 60-90 seconds
- **IAM Operations**: 300 calls (3 per user)
- **Rate Limiting**: Handled automatically (2 users/sec)
- **Success Rate**: 70-90% (some throttling expected)

### Scenario 2 (100 Users, 10 Refreshes)
- **Duration**: 5-10 minutes
- **Total Requests**: 1,100
- **Concurrency**: 100 users
- **Success Rate**: >95%

### Scenario 3 (50 Users, 25 Terminations)
- **Duration**: 3-5 minutes
- **Terminations**: 25 instances
- **Reassignments**: 25 new instances
- **Success Rate**: >70%

## Monitoring

### During Test Execution

Watch for:
1. **IAM Throttling**: Check CloudWatch logs for `Throttling` errors
2. **Instance Availability**: Monitor instance pool status
3. **Lambda Timeouts**: Check for 504 errors
4. **DynamoDB Throttling**: Monitor read/write capacity

### Key Metrics

- **Instance Assignment Rate**: Should be 100% for Scenario 1
- **Persistence Rate**: Should be >95% for Scenario 2
- **Reassignment Success**: Should be >70% for Scenario 3
- **Response Time**: P95 should be < 15s for all scenarios
- **Error Rate**: Should be < 30% (accounting for IAM throttling)

## Troubleshooting

### Issue: IAM Rate Limiting

**Symptoms**: High error rate, slow user creation

**Solution**: 
- Tests already use rate limiting (2 users/sec)
- If still throttling, reduce to 1 user/sec
- Check AWS account IAM limits

### Issue: Pool Exhaustion

**Symptoms**: Users not getting instances

**Solution**:
- Ensure pool size >= number of users
- For Scenario 3, need pool_size >= users + terminated_users
- Check instance availability before test

### Issue: High Response Times

**Symptoms**: P95 > 15s

**Solution**:
- Check Lambda cold starts
- Monitor DynamoDB read capacity
- Check EC2 instance state transitions
- Verify network connectivity

## Cost Considerations

### EC2 Instances
- 150 instances × test duration × instance cost
- For 1-hour test: ~$15-30 (depending on instance type)

### Lambda Invocations
- Scenario 1: ~100 invocations
- Scenario 2: ~1,100 invocations
- Scenario 3: ~500 invocations
- Total: ~1,700 invocations (~$0.01)

### DynamoDB
- Read/Write capacity units
- ~10,000 reads + ~5,000 writes
- Cost: ~$0.10-0.50

**Total Estimated Cost**: $15-30 per full test run

## Best Practices

1. **Run during off-peak hours** to avoid affecting production
2. **Monitor AWS costs** during testing
3. **Clean up instances** after testing
4. **Review CloudWatch logs** for errors
5. **Start with smaller scales** (20-50 users) before 100
6. **Allow time for instances to initialize** (2-3 minutes after creation)

## Next Steps

After running conference-scale tests:

1. Review test results and metrics
2. Identify bottlenecks (IAM, DynamoDB, Lambda)
3. Optimize based on findings
4. Re-run tests to validate improvements
5. Document performance characteristics

