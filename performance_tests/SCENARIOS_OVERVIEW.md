# k6 Performance Test Scenarios Overview

This document describes all available performance test scenarios for the Lambda user management system, including the business logic they test and edge cases they cover.

## Scenario Summary

| Scenario | Name | Purpose | Key Metrics |
|----------|------|---------|-------------|
| 1 | New User Instance Assignment | Test initial assignment of instances to new users | Instance assignment rate, response time |
| 2 | User Instance Persistence | Verify users maintain same instance across refreshes | Persistence rate, cookie handling |
| 3 | Instance Termination and Reassignment | Test automatic reassignment when instances are terminated | Termination detection, reassignment success |
| 4 | Pool Exhaustion and Recovery | Test behavior when instance pool is exhausted | Pool exhaustion detection, recovery success |
| 5 | Stopped Instance Recovery | Test automatic start of stopped instances | Stopped detection, auto-start success |

---

## Scenario 1: New User Instance Assignment

### Business Logic Tested
- **New users** (without cookies) should receive an EC2 instance from the pool
- Each user should get a **unique instance** (no double-assignment)
- System should handle **concurrent requests** without race conditions
- Instance assignment should be **atomic** (DynamoDB conditional writes prevent conflicts)

### Test Flow
1. Create N users (matching instance pool size)
2. Each user makes a GET request without cookies
3. System assigns an instance and returns cookies
4. Verify all users received instances

### Key Lambda Logic
- `assign_ec2_instance_to_student()` uses DynamoDB conditional writes to prevent race conditions
- `cleanup_expired_assignments()` cleans up stale "assigning" records (10-minute TTL)
- Instance selection is randomized to reduce collision probability

### Edge Cases Covered
- ✅ Concurrent user creation (IAM rate limiting handled)
- ✅ Instance pool exhaustion (tested separately in Scenario 4)
- ✅ Expired assignment cleanup (10-minute TTL)

### Configuration
```bash
export INSTANCE_POOL_SIZE=20  # Must match expected users
./run_k6_tests.sh scenario1
```

---

## Scenario 2: User Instance Persistence

### Business Logic Tested
- Users with **valid cookies** should receive the **same instance** on refresh
- System should **preserve user sessions** across multiple requests
- Cookie parsing and validation should work correctly

### Test Flow
1. Create N users, each gets an instance (initial request)
2. Each user makes M refresh requests (with cookies)
3. Verify same instance ID, user name, and IP address persist

### Key Lambda Logic
- Cookie-based user identification (`testus_patronus_user` cookie)
- Instance lookup from cookies (`testus_patronus_instance_id`)
- DynamoDB query by `student_name` to find existing assignments
- EC2 instance state verification (running, stopped, terminated)

### Edge Cases Covered
- ✅ Cookie parsing from Lambda Function URLs (multiValueHeaders)
- ✅ HTML fallback parsing if cookies not parsed
- ✅ Instance state changes (handled in Scenarios 3 and 5)

### Configuration
```bash
export NUM_USERS=10
export REFRESHES_PER_USER=10
export INSTANCE_POOL_SIZE=10  # Must be >= NUM_USERS
./run_k6_tests.sh scenario2
```

---

## Scenario 3: Instance Termination and Reassignment

### Business Logic Tested
- When a user's assigned instance is **terminated**, the system should:
  1. **Detect** the termination (via EC2 state check)
  2. **Clean up** the old DynamoDB record
  3. **Automatically reassign** a new instance
  4. **Update cookies** with new instance information

### Test Flow
1. Create 10 users, each gets an instance
2. Terminate 5 instances (simulate expiration/cleanup)
3. Users refresh - system detects termination
4. System automatically reassigns new instances
5. Verify all users eventually get new instances

### Key Lambda Logic
- **Termination Detection**: Lines 1076-1083, 1189-1208, 1211-1232
  - Checks EC2 instance state: `terminated`, `shutting-down`
  - Handles `InvalidInstanceID.NotFound` errors
  - Detects missing instances in reservations

- **Automatic Reassignment**: Lines 1158-1164, 1202-1205, 1226-1229
  - Deletes old DynamoDB record
  - Calls `assign_ec2_instance_to_student()` to get new instance
  - Updates user_info with new instance_id and IP

- **Cleanup**: Lines 1150-1155, 1194-1199
  - Removes DynamoDB records for terminated instances
  - Handles cleanup errors gracefully

### Edge Cases Covered
- ✅ Instance terminated while user has active session
- ✅ Instance not found (InvalidInstanceID.NotFound)
- ✅ Instance in "shutting-down" state
- ✅ Reassignment failure (no available instances)
- ✅ Concurrent termination and refresh requests

### Configuration
```bash
export NUM_USERS=10
export INSTANCE_POOL_SIZE=10
export INSTANCE_MANAGER_URL="https://..."
export INSTANCE_MANAGER_PASSWORD="..."
./run_k6_tests.sh scenario3
```

### Expected Behavior
- **Termination Detection Rate**: >80% (system detects terminated instances)
- **Reassignment Success Rate**: >90% (successfully gets new instance)
- **Response Time**: P95 < 10s (includes EC2 operations)

---

## Scenario 4: Pool Exhaustion and Recovery

### Business Logic Tested
- When the instance pool is **exhausted** (all instances assigned):
  - New users should receive appropriate error messages
  - System should handle the exhaustion gracefully
- When instances become **available again**:
  - Previously failed users should be able to get instances
  - System should recover from exhaustion state

### Test Flow
1. Create instance pool equal to number of users (e.g., 10 instances)
2. Have 15 users try to get instances (5 will fail initially)
3. Wait for some instances to become available (via cleanup/expiration)
4. Verify that previously failed users can now get instances

### Key Lambda Logic
- **Pool Exhaustion Detection**: Lines 1684-1706
  - `assign_ec2_instance_to_student()` raises exception if no available instances
  - Filters out instances already assigned in DynamoDB
  - Checks instance state (stopped, running)

- **Error Handling**: Lines 1163-1164, 1179-1180, 1231-1232
  - Sets `user_info['instance_error']` when assignment fails
  - Returns HTML with error message
  - Allows retry on subsequent requests

- **Recovery**: Automatic when instances become available
  - Expired assignments cleaned up (10-minute TTL)
  - Terminated instances removed from pool
  - New requests can get freed instances

### Edge Cases Covered
- ✅ All instances assigned (pool exhaustion)
- ✅ Concurrent requests when pool is limited
- ✅ Recovery after instances become available
- ✅ Error messages when no instances available

### Configuration
```bash
export NUM_USERS=15
export INSTANCE_POOL_SIZE=10  # Smaller than NUM_USERS
./run_k6_tests.sh scenario4
```

### Expected Behavior
- **Instance Assignment Rate**: >60% (at least 60% eventually get instances)
- **Pool Exhaustion Detected**: >30% (system detects exhaustion)
- **Recovery Success**: Users can get instances after initial failure

---

## Scenario 5: Stopped Instance Recovery

### Business Logic Tested
- When a user's instance is **stopped** (not terminated):
  - System should **detect** the stopped state
  - System should **automatically start** the instance
  - User should eventually get access to the instance

### Test Flow
1. Create 10 users, each gets an instance
2. Stop 5 instances (simulate cost optimization)
3. Users refresh - system detects stopped state
4. System automatically starts instances
5. Verify instances are running and accessible

### Key Lambda Logic
- **Stopped Detection**: Lines 1186-1188
  - Checks instance state: `stopped`
  - Detects stopped instances during refresh

- **Automatic Start**: Lines 1187, 221-228 (status Lambda)
  - Calls `ec2.start_instances(InstanceIds=[instance_id])`
  - Updates DynamoDB status to `starting`
  - Returns "Instance is starting..." message

- **State Management**: Lines 1184-1188
  - Handles `running`, `pending`, `stopped`, `terminated` states
  - Different behavior for each state

### Edge Cases Covered
- ✅ Instance stopped while user has active session
- ✅ Instance starting (pending state)
- ✅ Auto-start failure (permissions, instance issues)
- ✅ Multiple refresh requests during start

### Configuration
```bash
export NUM_USERS=10
export INSTANCE_POOL_SIZE=10
export INSTANCE_MANAGER_URL="https://..."
export INSTANCE_MANAGER_PASSWORD="..."
./run_k6_tests.sh scenario5
```

### Expected Behavior
- **Stopped Detection Rate**: >80% (system detects stopped instances)
- **Auto-Start Success Rate**: >90% (instances successfully started)
- **Response Time**: P95 < 10s (includes EC2 start operation)

---

## Additional Edge Cases (Not Yet Covered)

### Scenario 6: Expired Assignment Cleanup (Future)
**Business Logic**: Test the 10-minute TTL for "assigning" status
- Create assignment that times out
- Verify cleanup happens after 10 minutes
- Verify instance becomes available again

### Scenario 7: Concurrent Assignment Race Conditions (Future)
**Business Logic**: Test DynamoDB conditional writes prevent double-assignment
- Multiple users try to get same instance simultaneously
- Verify only one succeeds
- Verify others get different instances

### Scenario 8: Hard Termination Timeout (Future)
**Business Logic**: Test instances terminated after hard timeout
- Create instances that exceed `HARD_TERMINATE_TIMEOUT_MINUTES`
- Verify automatic termination
- Verify reassignment for affected users

### Scenario 9: Instance State Transitions (Future)
**Business Logic**: Test all instance state transitions
- `pending` → `running`
- `running` → `stopped`
- `stopped` → `running`
- `running` → `terminated`
- Verify system handles each transition correctly

---

## Running All Scenarios

```bash
# Run all scenarios sequentially
./run_k6_tests.sh all

# Or run individually
./run_k6_tests.sh scenario1
./run_k6_tests.sh scenario2
./run_k6_tests.sh scenario3
./run_k6_tests.sh scenario4
./run_k6_tests.sh scenario5
```

---

## Key Lambda Functions and Logic

### `assign_ec2_instance_to_student(student_name)`
- **Purpose**: Assign an available EC2 instance to a student
- **Key Features**:
  - Cleans up expired assignments (10-minute TTL)
  - Checks for existing assignments
  - Uses DynamoDB conditional writes to prevent race conditions
  - Randomizes instance selection
  - Handles stopped instances (starts them)

### `cleanup_expired_assignments()`
- **Purpose**: Clean up assignments stuck in "assigning" status
- **TTL**: 10 minutes (`assignment_ttl = 600`)
- **Logic**: Scans DynamoDB for expired "assigning" records and resets instances

### Instance State Handling
- **running**: User gets instance, IP address available
- **pending**: Instance is starting, user sees "starting" message
- **stopped**: System automatically starts instance
- **terminated**: System detects termination and reassigns new instance
- **shutting-down**: Treated same as terminated

### Cookie Management
- **Cookies**: `testus_patronus_user`, `testus_patronus_instance_id`, `testus_patronus_ip`
- **Max-Age**: 7 days
- **Format**: Lambda Function URLs use `multiValueHeaders` for Set-Cookie

---

## Performance Metrics

### Common Metrics
- **http_req_duration**: Response time (P95 < 10-15s)
- **http_req_failed**: Error rate (< 10-30% depending on scenario)
- **Instance Assignment Rate**: % of users who get instances
- **Persistence Rate**: % of refreshes that maintain same instance

### Scenario-Specific Metrics
- **Scenario 3**: Termination detection rate, reassignment success rate
- **Scenario 4**: Pool exhaustion detection, recovery success rate
- **Scenario 5**: Stopped detection rate, auto-start success rate

---

## Troubleshooting

### Common Issues

1. **IAM Rate Limiting**: Scenario 1 uses `constant-arrival-rate` to stay within limits
2. **Cookie Parsing**: All scenarios include HTML fallback parsing
3. **Instance Pool**: Scenarios check pool status before running
4. **Concurrent Requests**: DynamoDB conditional writes prevent race conditions

### Debug Tips

- Check CloudWatch logs for Lambda execution details
- Verify instance pool status: `./run_k6_tests.sh prepare --count N`
- Review k6 summary output for detailed metrics
- Check DynamoDB records for assignment status

---

## References

- **Lambda Function**: `testus_patronus_user_management.py`
- **Instance Manager**: `testus_patronus_instance_manager.py`
- **Status Lambda**: `testus_patronus_status.py`
- **Cleanup Lambda**: `testus_patronus_stop_old_instances.py`

