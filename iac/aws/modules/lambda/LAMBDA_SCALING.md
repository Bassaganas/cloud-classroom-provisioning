# Lambda Scaling and Performance Options

This document explains the scaling and performance options available for Lambda functions, particularly for conference scenarios with high concurrent load.

## Quick Reference: Conference Scenario (100 Users)

For a conference with 100 users arriving within 1 minute:

```hcl
# terraform.tfvars
user_management_memory_size              = 1024  # 1 GB (better CPU)
user_management_timeout                  = 180   # 3 minutes
user_management_provisioned_concurrency  = 20    # Pre-warm 20 environments
user_management_reserved_concurrency     = 0     # Unlimited scaling
skip_iam_user_creation                  = true   # Skip IAM (no throttling)
```

**Expected Results:**
- ✅ No cold starts (20 provisioned environments)
- ✅ Fast response times (~2-5 seconds per user)
- ✅ Handles 100 concurrent users
- ✅ Cost: ~$7.20/day for provisioned concurrency

## Current Configuration

### User Management Lambda (Critical for Conference Scenarios)
- **Memory**: 512 MB (default, configurable)
- **Timeout**: 120 seconds (default, configurable)
- **Provisioned Concurrency**: 0 (disabled by default)
- **Reserved Concurrency**: 0 (unlimited by default)

### Instance Manager Lambda
- **Memory**: 512 MB (configurable)
- **Timeout**: 300 seconds (configurable)

## Scaling Options

### 1. **Memory/CPU Allocation** (Recommended First Step)

**What it does:**
- Lambda automatically allocates CPU power proportional to memory
- More memory = more CPU = faster execution
- Linear relationship: 2x memory ≈ 2x CPU

**Configuration:**
```hcl
user_management_memory_size = 1024  # 1 GB (was 256 MB)
```

**Benefits:**
- ✅ Simple to configure
- ✅ Immediate performance improvement
- ✅ No additional cost for faster execution (you pay for GB-seconds)
- ✅ Can reduce total execution time, potentially saving money

**Trade-offs:**
- ⚠️ Higher memory = higher cost per invocation
- ⚠️ Diminishing returns after ~1-2 GB for most workloads

**Recommendation for Conference (100 users):**
- Start with **512-1024 MB** for user_management
- Monitor CloudWatch metrics to find optimal value

### 2. **Provisioned Concurrency** (Eliminates Cold Starts)

**What it does:**
- Pre-initializes execution environments
- Keeps them "warm" and ready to respond immediately
- Eliminates cold start latency (typically 1-5 seconds for Python)

**Configuration:**
```hcl
user_management_provisioned_concurrency = 20  # Pre-warm 20 execution environments
```

**Benefits:**
- ✅ Eliminates cold starts completely
- ✅ Predictable latency (always fast)
- ✅ Critical for latency-sensitive applications

**Trade-offs:**
- ⚠️ **Costs money even when idle** (~$0.015/hour per provisioned execution)
- ⚠️ 20 provisioned = ~$7.20/day = ~$216/month
- ⚠️ Only useful if you have predictable traffic patterns

**Recommendation for Conference (100 users):**
- **10-20 provisioned** for conference day (enable before, disable after)
- **0 provisioned** for normal operation (cost optimization)

**Cost Example:**
- 20 provisioned concurrency × $0.015/hour × 24 hours = $7.20/day
- For a 1-day conference: ~$7.20
- For continuous operation: ~$216/month

### 3. **Reserved Concurrency** (Guarantees Capacity)

**What it does:**
- Guarantees a minimum number of concurrent executions for your function
- Prevents other functions from consuming all account-level concurrency
- Limits maximum concurrent executions (can cause throttling if exceeded)

**Configuration:**
```hcl
user_management_reserved_concurrency = 100  # Reserve 100 concurrent executions
```

**Benefits:**
- ✅ Guarantees capacity for critical functions
- ✅ Protects other functions from being starved
- ✅ Useful for multi-tenant scenarios

**Trade-offs:**
- ⚠️ Limits scaling (if you need more than reserved, requests will be throttled)
- ⚠️ Can cause 429 (Too Many Requests) errors if exceeded

**Recommendation for Conference (100 users):**
- **0 (unlimited)** for most scenarios
- **100+** only if you need to guarantee capacity and limit other functions

### 4. **Timeout Increase** (For Long-Running Operations)

**What it does:**
- Allows Lambda to run longer before timing out
- Useful for operations that take time (EC2 instance assignment, IAM operations)

**Configuration:**
```hcl
user_management_timeout = 180  # 3 minutes (was 60 seconds)
```

**Benefits:**
- ✅ Prevents premature timeouts
- ✅ Allows for retries and complex operations

**Trade-offs:**
- ⚠️ Higher timeout = higher cost if function hangs
- ⚠️ Should match actual execution time (not too high)

**Recommendation:**
- **120-180 seconds** for conference scenarios
- Monitor actual execution times in CloudWatch

### 5. **Automatic Concurrency Scaling** (Default Behavior)

**What it does:**
- Lambda automatically scales concurrent executions based on incoming requests
- Default account limit: 1,000 concurrent executions per region
- Can be increased by AWS Support request

**Configuration:**
- No configuration needed (automatic)
- Can request limit increase from AWS Support if needed

**Benefits:**
- ✅ Automatic and free
- ✅ Scales to handle traffic spikes

**Limitations:**
- ⚠️ Cold starts on new execution environments
- ⚠️ Account-level limits apply

## Recommended Configuration for Conference (100 Users)

### Scenario: 100 users arriving within 1 minute

```hcl
# terraform.tfvars or terraform apply -var="..."
user_management_memory_size              = 1024  # 1 GB for better CPU
user_management_timeout                  = 180   # 3 minutes for safety
user_management_provisioned_concurrency  = 20    # Pre-warm 20 environments
user_management_reserved_concurrency     = 0     # Unlimited scaling
skip_iam_user_creation                  = true   # Skip IAM to avoid throttling
```

**Expected Performance:**
- **Cold starts**: Eliminated (20 provisioned)
- **Execution time**: ~2-5 seconds per user (with IAM skipped)
- **Concurrent capacity**: 20 immediate + automatic scaling for remaining 80
- **Cost**: ~$7.20 for provisioned concurrency (1 day)

### Cost Breakdown (Conference Day)

1. **Provisioned Concurrency**: 20 × $0.015/hour × 24 hours = **$7.20/day**
2. **Lambda Invocations**: 100 users × $0.0000002/invocation = **$0.00002**
3. **Lambda Duration**: 100 users × 3 seconds × 1 GB = 300 GB-seconds = **$0.005**
4. **Total**: ~**$7.21/day** for conference

### Normal Operation (No Conference)

```hcl
user_management_memory_size              = 512   # Standard memory
user_management_timeout                  = 120   # Standard timeout
user_management_provisioned_concurrency  = 0     # Disabled (cost optimization)
user_management_reserved_concurrency     = 0     # Unlimited
```

## Monitoring and Optimization

### CloudWatch Metrics to Monitor

1. **Duration**: Actual execution time
   - Target: < 5 seconds (with IAM skipped)
   - Action: Increase memory if consistently high

2. **ConcurrentExecutions**: Number of concurrent invocations
   - Target: Should scale automatically
   - Action: Increase provisioned concurrency if cold starts are an issue

3. **Throttles**: Number of throttled requests
   - Target: 0
   - Action: Increase reserved concurrency or account limit

4. **Errors**: Number of errors
   - Target: < 1%
   - Action: Check logs for root cause

5. **Cold Start Duration**: Time to initialize (in X-Ray or custom metrics)
   - Target: < 1 second
   - Action: Use provisioned concurrency

### Optimization Tips

1. **Start with Memory**: Increase memory first (easiest, cheapest)
2. **Monitor Cold Starts**: If cold starts are a problem, add provisioned concurrency
3. **Profile Execution**: Use X-Ray to identify bottlenecks
4. **Optimize Code**: Reduce package size, lazy initialization, connection pooling
5. **Skip IAM**: Use `skip_iam_user_creation=true` for conference scenarios

## Example: Enabling Provisioned Concurrency for Conference

```bash
# Before conference (enable provisioned concurrency)
terraform apply \
  -var="user_management_provisioned_concurrency=20" \
  -var="user_management_memory_size=1024" \
  -var="user_management_timeout=180" \
  -var="skip_iam_user_creation=true"

# After conference (disable to save costs)
terraform apply \
  -var="user_management_provisioned_concurrency=0" \
  -var="user_management_memory_size=512" \
  -var="user_management_timeout=120"
```

**Note:** When `provisioned_concurrency > 0`, Terraform will:
1. Set `publish = true` on the Lambda function (creates a version)
2. Create an alias pointing to that version
3. Apply provisioned concurrency to the alias
4. When you update the function code, a new version is published and the alias is updated automatically

## References

- [AWS Lambda Provisioned Concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)
- [AWS Lambda Reserved Concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)
- [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [Lambda Performance Optimization](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

