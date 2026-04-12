# Requirements

## Functional Requirements

### Classroom Provisioning
- **Student workshops**: Deploy learning environments with isolated EC2 instances per student
- **Instance pooling**: Pre-provision warm instances for rapid student allocation (sub-minute startup)
- **Golden AMI support**: Cache Docker images in Gold AMI to reduce cold-start latency
- **Multi-region**: Support deployments across AWS regions (eu-west-1, eu-west-3, us-east-1)
- **Workshop flexibility**: Support multiple workshop types (fellowship, LOTR, core)

### Instance Lifecycle
- **Persistent spot instances**: Use spot pricing for cost optimization (customer trades availability for 70% cost savings)
- **Graceful termination**: Properly cancel persistent spot requests before termination to prevent auto-replacement
- **Stable DNS**: Allocate domain names per instance (subdomain of wildcard certificate)
- **Caddy HTTPS**: Automatic wildcard certificate provisioning via Let's Encrypt DNS-01 challenge with Route53

### Access Paths
- **Student path**: CloudFront → Lambda functions → workshop content
- **Instructor UI**: CloudFront/S3 → React application → API Gateway → instance manager Lambda
- **SSH/Console**: Instance tags contain endpoints (domain names, Jenkins, IDE)

### Instance Tagging & Metadata
- **Required tags**: SessionID, StudentID, Workshop, Environment, InstanceType, HttpsDomain, JenkinsDomain, IdeDomain
- **Instance metadata**: User data exports domain names for container environment variables
- **Proper domain injection**: Each instance receives unique CADDY_DOMAIN, JENKINS_DOMAIN, IDE_DOMAIN exports

## Security Requirements

### IAM & Roles
- **Least privilege**: Instance roles have min-required EC2, Route53, SSM, Secrets Manager permissions
- **Route53 permissions**: Include `route53:GetChange` for asynchronous DNS-01 validation monitoring
- **No overpermission**: No AdministratorAccess or wildcard resource policies

### EC2 Metadata Protection
- **IMDSv2 required**: `HttpTokens = 'required'` on all instances
- **Hop limit = 2**: `HttpPutResponseHopLimit = 2` allows Docker containers (not just EC2 host) to reach IMDS
  - Hop 1: EC2 host
  - Hop 2: Docker container via bridge gateway
- **No public IP required for IMDS**: Metadata service is fully internal

### HTTPS & Certificates
- **Wildcard certificates only**: All instance endpoints (*.workshop.domain) covered by single cert
- **DNS-01 validation**: Avoids HTTP-01 (stateless containers) or manual cert renewal
- **Let's Encrypt acceptable use**: Acceptable for workshop environments; large-scale production apps may use ACM
- **Automatic renewal**: Caddy renews before expiry via DNS-01

### Secrets Management
- **AWS Secrets Manager**: Store sensitive data (API keys, tokens) not in code
- **SSM Parameter Store**: Store configuration (template JSON, domain mappings) in Standard or Advanced tier
- **No hardcoded credentials**: All credentials injected at runtime via instance role

## Operational Requirements

### Deployment
- **IaC via Terraform**: All infrastructure versioned; apply idempotent
- **UI-driven provisioning**: Students provision via React UI, not CLI
- **Golden AMI bake flow**: Automated GitHub Actions job pre-pulls Docker images into new AMI after SUT changes
- **Manual override capability**: Admins can force instances without waiting for bake job

### Monitoring & Debugging
- **Instance boot logs**: SSM Session Manager provides shell access for troubleshooting
- **Caddy domain status**: Instance tags reflect current domain allocation
- **Spot instance tracking**: Spot request IDs and states visible in CloudWatch logs
- **Test modes**: E2E tests can run in mocked mode (no AWS calls) or against live AWS

### Cost Optimization
- **Spot instances**: Default choice; ~70% savings vs on-demand
- **Pool pre-provisioning**: Reduces student wait time vs on-demand launch (60s → <5s)
- **Golden AMI reuse**: Cached Docker images avoid repeated pulls from registry
- **Resource cleanup**: E2E tests and manual teardown properly cancel spot requests to prevent phantom relaunches

### Reliability
- **Spot replacement prevention**: Terminating persistent spot instances requires `cancel_spot_instance_requests(TerminateInstances=True)`
- **No orphaned instances**: Spot requests in active state after deletion = failed cleanup
- **Idempotent Lambda**: Instance manager handles duplicate invocations safely
- **E2E stability window**: Test polls for 120s after deletion to catch delayed spot replacements
