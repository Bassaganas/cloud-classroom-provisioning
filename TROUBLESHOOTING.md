# Problems and Solutions

## Spot instances reappear after deletion
Problem: Deleted Spot instances come back automatically.

Cause: Instance was terminated but Spot request stayed active.

Solution:
1. Use cancellation path with `TerminateInstances=True`.
2. Verify request status becomes `cancelled` or `closed`.
3. Re-run deletion validation test from [TESTS.md](TESTS.md).

## Caddy cannot obtain or renew wildcard certificates
Problem: HTTPS provisioning fails.

Common causes:
1. Missing `route53:GetChange` IAM permission
2. IMDS not reachable from container
3. Domain variable injection mismatch

Solution:
1. Confirm instance role includes `route53:GetChange`.
2. Confirm metadata options include hop limit 2.
3. Confirm domain exports are present in user-data.

## IMDS credential errors inside Docker containers
Problem: Logs show no EC2 IMDS role found.

Cause: `HttpPutResponseHopLimit` is 1.

Solution:
Set `HttpPutResponseHopLimit` to 2 for all launched instances and re-provision affected instances.

## Slow classroom startup after deployment
Problem: First launch takes too long.

Cause: Cold image pulls.

Solution:
1. Ensure Golden AMI bake job completed successfully.
2. Ensure latest AMI ID is stored in workshop template SSM parameter.
3. Launch a fresh instance and verify startup time drops.

## Multi-instance provisioning has wrong domain exports
Problem: Instances have duplicated or stale domain exports.

Cause: User-data mutation reused across loop iterations.

Solution:
Reset user-data from a base copy at the start of each iteration.

## Template not found or wrong config loaded
Problem: Launch uses fallback/default behavior unexpectedly.

Cause: Individual workshop template missing or stale.

Solution:
1. Check individual SSM parameter for the workshop.
2. Republish templates.
3. Clear template cache and retry.

## Delete works but Route53 records remain
Problem: DNS entries linger after cleanup.

Cause: Record already absent, wrong hosted zone, or delete failed silently.

Solution:
1. Verify hosted zone ID.
2. Check delete retries and response code.
3. Treat already-deleted records as non-fatal.

## Quick diagnostics checklist
1. Check Lambda logs for create/delete path.
2. Check instance metadata options.
3. Check Spot request status after delete.
4. Check SSM template source for workshop.
5. Check Route53 change status and permissions.
