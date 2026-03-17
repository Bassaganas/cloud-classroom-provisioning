# Fellowship Tutorial: Instructor Guide

## Overview

This guide provides instructors with all the information needed to successfully run the Fellowship tutorial, including setup, monitoring, challenge management, and troubleshooting.

---

## Choosing Tutorial Length

The Fellowship tutorial can be delivered in two formats:

### ⚡ Short Tutorial (1.5 hours)

**Best for:**
- Quick workshops or conference sessions
- Introduction to MCPs and basic monitoring
- Teams with limited time

**What teams complete:**
- Environment setup
- Run tests
- Create basic monitoring agent (direct Jenkins API)
- Generate simple report

**MVP Requirements:**
- SUT web application
- Playwright test suite (basic)
- Jenkins setup
- Basic orchestration (monitoring agent with direct API)
- **NO event tracking required**
- **NO MCP servers required** (use direct APIs)

### 🎯 Full Tutorial (3-4 hours)

**Best for:**
- Comprehensive workshops
- Complete MCP orchestration experience
- Teams wanting full feature set

**What teams complete:**
- Everything in Short Tutorial PLUS
- Test generation with Playwright MCP
- Test fixing with agents
- Multi-agent orchestration
- Dark magic challenges
- Comprehensive reporting

**Full Requirements:**
- Everything in MVP PLUS
- Event tracking SDK
- Jenkins MCP server
- Official MCP integration
- Dark magic system
- Sauron's Eye

**Recommendation**: Start with MVP (Short Tutorial) to validate the concept, then expand to Full Tutorial.

---

## Pre-Tutorial Setup

### MVP Setup (Short Tutorial - 1.5 hours)

**Minimum Infrastructure Required:**
- EC2 instances with:
  - VS Code Server
  - Jenkins
  - SUT web application
  - Basic orchestration repository (monitoring agent with direct API)
- **NO event tracking infrastructure needed**
- **NO MCP servers needed** (use direct APIs)

**Deploy MVP Infrastructure:**
```bash
cd iac/aws/workshops/fellowship
terraform init
terraform plan -var="tutorial_mode=mvp"
terraform apply
```

**MVP Verification:**
- EC2 instances running
- Jenkins accessible
- SUT running
- VS Code Server accessible
- **NO EventBridge/DynamoDB needed yet**

### Full Tutorial Setup (3-4 hours)

**Complete Infrastructure Required:**
- Everything in MVP PLUS:
  - EventBridge event bus
  - DynamoDB tables
  - Lambda functions
  - API Gateway endpoints
  - WebSocket API
  - Progress tracking infrastructure

**Deploy Full Infrastructure:**
```bash
cd iac/aws/workshops/fellowship
terraform init
terraform plan -var="tutorial_mode=full"
terraform apply
```

**Full Verification:**
- Everything in MVP PLUS:
  - EventBridge event bus created
  - DynamoDB tables created
  - Lambda functions deployed
  - API Gateway endpoints active
  - WebSocket API configured

### 1. Infrastructure Deployment

**For MVP (Short Tutorial):**
```bash
cd iac/aws/workshops/fellowship
terraform init
terraform plan -var="tutorial_mode=mvp"
terraform apply
```

**MVP Verification:**
- EC2 instances running
- Jenkins accessible
- SUT running
- VS Code Server accessible
- **NO EventBridge/DynamoDB needed for MVP**

**For Full Tutorial:**
```bash
cd iac/aws/workshops/fellowship
terraform init
terraform plan -var="tutorial_mode=full"
terraform apply
```

**Full Verification:**
- Everything in MVP PLUS:
- EventBridge event bus created
- DynamoDB tables created
- Lambda functions deployed
- API Gateway endpoints active
- WebSocket API configured

### 2. EC2 Instance Pool

**Create EC2 Instance Pool:**
- Use `scripts/setup_classroom.sh` to create EC2 instances
- Each instance will automatically have:
  - VS Code Server installed
  - Jenkins pre-configured
  - **SUT automatically deployed** (downloaded from S3 during instance provisioning)
  - Repositories cloned:
    - `fellowship-orchestration` (from GitHub)
    - `fellowship-sut` (automatically available from S3 deployment)

**SUT Deployment Process:**
1. During `setup_classroom.sh --workshop fellowship`:
   - Terraform creates an S3 bucket for the SUT files
   - The script packages `iac/aws/workshops/fellowship/fellowship-sut/` into a tarball
   - The tarball is uploaded to S3 automatically
   - EC2 IAM roles are configured with S3 read permissions
2. During EC2 instance provisioning:
   - `user_data.sh` downloads the SUT tarball from S3
   - Extracts it to `/home/ec2-user/fellowship-sut/`
   - Starts Docker Compose services automatically
   - SUT is accessible at `http://<EC2-IP>/` on port 80

**No manual SUT deployment required** - everything happens automatically during classroom setup.
  
  **For MVP (Short Tutorial):**
  - **NO packages installed yet** (use direct APIs)
  - **NO event tracking configured yet**
  - Monitoring agent uses direct Jenkins API (not MCP)
  
  **For Full Tutorial:**
  - Packages installed:
    - `fellowship-events` (from PyPI)
    - `mcp-server-jenkins` (from PyPI or repository)
    - Official MCPs (Playwright, Git, Filesystem)
  - Event tracking configured

**Verify Instances:**
```bash
# Check instance status
aws ec2 describe-instances --filters "Name=tag:Workshop,Values=fellowship"

# Verify VS Code Server
curl http://<EC2-IP>:8080/healthz

# Verify Jenkins
curl http://<EC2-IP>:8080/jenkins/api/json
```

### 3. Team Registration

**Register Teams:**
- Teams register via Docusaurus website
- Each team gets:
  - Team ID (e.g., `frodo-sam-01`)
  - EC2 instance assignment
  - VS Code Server credentials
  - API keys for AI services
  - Jenkins credentials

**Verify Registration:**
```bash
# Check DynamoDB for registered teams
aws dynamodb scan --table-name fellowship_teams

# Verify team credentials in Secrets Manager
aws secretsmanager list-secrets --filters Key=tag-key,Values=TeamID
```

---

## Monitoring Team Progress

### Sauron's Eye Dashboard

**Access:** `http://sauron-eye.testingfantasy.com`

**Status:**
- **MVP**: Not available (Phase 4 feature)
- **Full Tutorial**: Available with real-time updates

**Features (Full Tutorial only):**
- Real-time progress map showing all teams
- Team positions on Middle-earth journey
- Color coding by progress level:
  - 🟢 Green: On track (70%+ completion)
  - 🟡 Yellow: Making progress (40-70%)
  - 🔴 Red: Behind (0-40%)
- Leaderboard sidebar
- Click team to view details

**Updates:**
- Updates every 2-3 seconds via WebSocket
- Shows all teams simultaneously
- Displays current milestone for each team

**MVP Alternative:**
- Use simple instructor dashboard or manual tracking
- Check team progress via EC2 instance access
- Monitor Jenkins pipelines manually

### Instructor Dashboard

**Access:** `http://instructor.testingfantasy.com/fellowship`

**MVP Status:**
- Basic team overview available
- Event logs not available (Phase 2)
- Progress analytics not available (Phase 2)
- MCP usage verification not available (Phase 3)

**Full Tutorial Features:**
1. **Team Overview**
   - List of all teams
   - Current progress percentage
   - Last activity timestamp
   - Current milestone

2. **Event Logs** (Phase 2+)
   - Real-time event stream
   - Filter by team, event type, time range
   - Search functionality

3. **Progress Analytics** (Phase 2+)
   - Average completion time
   - Milestone completion rates
   - Points distribution
   - Activity heatmap

4. **MCP Usage Verification** (Phase 3+)
   - Teams using official MCPs
   - Teams using custom MCPs
   - MCP tool invocation counts
   - Test generation via MCP

### Verifying MCP Usage

**Method 1: Event Tracking (Primary)**

Check for MCP-related events:
```python
# Query DynamoDB for MCP events
events = query_events(
    team_id="frodo-sam-01",
    event_type="mcp.tool.invoked"
)

# Verify Playwright MCP usage
playwright_events = [
    e for e in events 
    if e['event_data']['tool'].startswith('playwright_')
]

# Verify Jenkins MCP usage
jenkins_events = [
    e for e in events 
    if e['event_data']['tool'].startswith('jenkins_')
]
```

**Method 2: Dashboard Verification**

Instructor dashboard shows:
- MCP tool invocation count per team
- Tests created via MCP (`test.case.created` with `method: 'mcp'`)
- Tests fixed via MCP (`test.case.fixed` with `method: 'mcp'`)
- Agent creation events (`mcp.agent.created`)

**Method 3: Code Analysis (Optional)**

For deeper verification:
```bash
# SSH into team's EC2 instance
ssh ec2-user@<EC2-IP>

# Check for MCP-generated test files
   cd fellowship-sut
grep -r "Generated by" tests/
grep -r "AI-generated" tests/

# Check git history for MCP usage
git log --grep="mcp\|MCP\|playwright\|jenkins"
```

---

## Dark Magic Challenge Management

### Available Challenges

1. **Database Connection Blocked**
   - **Type**: `database_blocked`
   - **Effect**: Blocks database connections from SUT
   - **Detection**: Tests that check database connectivity fail
   - **Resolution**: Restore database connection via SSM

2. **Jenkins Service Stopped**
   - **Type**: `jenkins_stopped`
   - **Effect**: Stops Jenkins service
   - **Detection**: Jenkins API calls fail
   - **Resolution**: Restart Jenkins service

3. **API Secrets Rotated**
   - **Type**: `secrets_rotated`
   - **Effect**: Changes API keys/secrets
   - **Detection**: API calls fail with authentication errors
   - **Resolution**: Update secrets in configuration

4. **Network Latency Injected**
   - **Type**: `latency_injected`
   - **Effect**: Adds 2-5 second delay to network requests
   - **Detection**: Tests timeout or run slowly
   - **Resolution**: Remove latency injection

5. **Test File Corrupted**
   - **Type**: `test_corrupted`
   - **Effect**: Corrupts a test file (syntax error)
   - **Detection**: Test file fails to parse
   - **Resolution**: Fix syntax error or restore file

6. **Resource Exhaustion**
   - **Type**: `resource_exhaustion`
   - **Effect**: Limits CPU/memory available
   - **Detection**: Tests run slowly or fail
   - **Resolution**: Restore resource limits

### Triggering Challenges

**Method 1: Instructor Dashboard**

1. Navigate to Dark Magic Dashboard
2. Select challenge type
3. Select target team(s):
   - Single team
   - All teams
   - Custom selection
4. Click "Trigger Challenge"
5. Monitor challenge status

**Method 2: API Call**

```bash
curl -X POST https://api.fellowship.testingfantasy.com/api/dark-magic/trigger \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <INSTRUCTOR_TOKEN>" \
  -d '{
    "challenge_type": "database_blocked",
    "team_id": "frodo-sam-01",
    "scheduled_time": null
  }'
```

**Method 3: Scheduled Challenges**

```bash
curl -X POST https://api.fellowship.testingfantasy.com/api/dark-magic/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "challenge_type": "jenkins_stopped",
    "team_id": "all",
    "scheduled_time": "2024-01-15T14:30:00Z"
  }'
```

### Monitoring Challenge Status

**Check Challenge Status:**
```bash
# Get active challenges
curl https://api.fellowship.testingfantasy.com/api/dark-magic/status

# Get challenges for specific team
curl https://api.fellowship.testingfantasy.com/api/dark-magic/status?team_id=frodo-sam-01
```

**Dashboard View:**
- Active challenges list
- Challenge type and target team
- Time triggered
- Detection status (detected/not detected)
- Resolution status (resolved/not resolved)

### Undoing Challenges

**Method 1: Dashboard**
1. Navigate to Dark Magic Dashboard
2. Find active challenge
3. Click "Undo Challenge"
4. Verify challenge is resolved

**Method 2: API Call**

```bash
curl -X POST https://api.fellowship.testingfantasy.com/api/dark-magic/undo \
  -H "Content-Type: application/json" \
  -d '{
    "challenge_id": "challenge-123",
    "team_id": "frodo-sam-01"
  }'
```

### Challenge Timing Recommendations

**For Short Tutorial (1.5 hours):**
- **NO dark magic challenges** - Focus on core monitoring
- Teams should complete basic monitoring agent
- Skip challenges to save time

**For Full Tutorial (3-4 hours):**

**Early Tutorial (0-1 hour):**
- Start with easy challenges (test corruption, latency)
- Give teams time to understand the system

**Mid Tutorial (1-2.5 hours):**
- Introduce medium challenges (database blocked, secrets rotated)
- Teams should have monitoring agents running

**Late Tutorial (2.5-3.5 hours):**
- Introduce harder challenges (resource exhaustion, multiple simultaneous)
- Test teams' resilience

**Final 30 minutes:**
- Reduce challenges to let teams finish
- Only trigger if teams are ahead of schedule

---

## Report Evaluation

### Report Requirements

**Short Tutorial (MVP) - Basic Report:**
Teams submit simple reports with:
1. Executive Summary (basic)
2. Test Suite Overview
3. Monitoring Agent Description
4. What they learned
5. Appendix (code snippets)

**Full Tutorial - Comprehensive Report:**
Teams submit comprehensive reports with:
1. Executive Summary
2. Test Suite Overview
3. MCP Integration Summary
4. Dark Magic Challenges Detected
5. Dark Magic Challenges Resolved
6. Test Cases Generated
7. Test Cases Fixed
8. Monitoring Agent Capabilities
9. Recommendations
10. Appendix (code snippets)

### Evaluating Reports

**Automatic Evaluation:**
- Reports are automatically evaluated when submitted
- Evaluation checks:
  - All required sections present
  - Content quality (length, detail)
  - Code examples provided
  - MCP usage documented

**Manual Review:**
1. Access report in S3: `s3://fellowship-reports/{team_id}/final_report.md`
2. Review content quality
3. Verify MCP usage claims
4. Check dark magic documentation
5. Assign quality score (0-100)

**Scoring:**
- Completeness: 30 points (all sections present)
- Quality: 30 points (detailed, well-written)
- MCP Usage: 20 points (properly documented)
- Dark Magic: 10 points (all challenges documented)
- Code Examples: 10 points (relevant snippets provided)

### Winner Detection

**Automatic Calculation:**
- Winner is calculated automatically based on:
  - Progress points (40%)
  - Report quality (30%)
  - Dark magic handling (20%)
  - Completion time (10%)

**Manual Override:**
```bash
# Manually set winner
curl -X POST https://api.fellowship.testingfantasy.com/api/winner/set \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "frodo-sam-01",
    "reason": "Exceptional MCP integration"
  }'
```

---

## Troubleshooting

### Teams Can't Access EC2 Instances

**Symptoms:**
- VS Code Server not accessible
- Connection timeouts

**Solutions:**
1. Check EC2 instance status:
   ```bash
   aws ec2 describe-instances --instance-ids <INSTANCE_ID>
   ```

2. Check security groups:
   ```bash
   aws ec2 describe-security-groups --group-ids <SG_ID>
   ```
   - Port 8080 (VS Code Server) should be open
   - Port 8080/jenkins should be open
   - Port 3000 (SUT) should be open

3. Check VS Code Server logs:
   ```bash
   ssh ec2-user@<EC2-IP>
   sudo journalctl -u code-server -n 50
   ```

### Events Not Being Tracked

**Symptoms:**
- No events in DynamoDB
- Sauron's Eye not updating
- Student dashboard shows no progress

**Solutions:**
1. Check EventBridge:
   ```bash
   aws events list-rules --name-prefix fellowship
   ```

2. Check Lambda function logs:
   ```bash
   aws logs tail /aws/lambda/fellowship-progress-tracker --follow
   ```

3. Check team environment variables:
   ```bash
   ssh ec2-user@<EC2-IP>
   env | grep FELLOWSHIP
   ```

4. Test event emission:
   ```bash
   python3 -c "from fellowship_events import EventClient; c = EventClient(); c.emit('test.event', {})"
   ```

### MCP Servers Not Working

**Symptoms:**
- Agents can't access MCP tools
- MCP tool invocations fail

**Solutions:**
1. Check MCP server installation:
   ```bash
   ssh ec2-user@<EC2-IP>
   
   # Check event SDK
   pip list | grep fellowship-events
   
   # Check Jenkins MCP
   pip list | grep mcp-server-jenkins
   
   # Check official MCPs
   npm list -g @playwright/mcp
   uvx mcp-server-git
   ```

2. Check MCP server configuration:
   ```bash
   cd fellowship-orchestration
   cat .env
   # Verify credentials are set
   ```

3. Test MCP server directly:
   ```bash
   cd fellowship-orchestration
   python3 src/test_mcp_connection.py
   ```

4. Check agent logs:
   ```bash
   cd fellowship-orchestration
   tail -f logs/agent.log
   ```

### Jenkins Not Responding

**Symptoms:**
- Jenkins API calls fail
- Pipelines don't trigger

**Solutions:**
1. Check Jenkins service:
   ```bash
   ssh ec2-user@<EC2-IP>
   sudo systemctl status jenkins
   ```

2. Restart Jenkins:
   ```bash
   sudo systemctl restart jenkins
   ```

3. Check Jenkins logs:
   ```bash
   sudo tail -f /var/log/jenkins/jenkins.log
   ```

4. Verify Jenkins credentials:
   ```bash
   # Check credentials in Secrets Manager
   aws secretsmanager get-secret-value --secret-id fellowship/jenkins/{team_id}
   ```

### Dark Magic Challenges Not Triggering

**Symptoms:**
- Challenge trigger fails
- Challenge doesn't affect team

**Solutions:**
1. Check Lambda function:
   ```bash
   aws logs tail /aws/lambda/fellowship-dark-magic-trigger --follow
   ```

2. Check SSM document execution:
   ```bash
   aws ssm describe-instance-information --filters "Key=tag:TeamID,Values=frodo-sam-01"
   aws ssm list-command-invocations --instance-id <INSTANCE_ID>
   ```

3. Verify SSM agent is running on EC2:
   ```bash
   ssh ec2-user@<EC2-IP>
   sudo systemctl status amazon-ssm-agent
   ```

4. Test SSM document manually:
   ```bash
   aws ssm send-command \
     --instance-ids <INSTANCE_ID> \
     --document-name "Fellowship-BlockDatabase" \
     --parameters "team_id=frodo-sam-01"
   ```

### Reports Not Submitting

**Symptoms:**
- Report submission fails
- Reports not appearing in S3

**Solutions:**
1. Check API Gateway:
   ```bash
   aws apigateway get-rest-apis --query "items[?name=='fellowship-api']"
   ```

2. Check Lambda function:
   ```bash
   aws logs tail /aws/lambda/fellowship-report-submission --follow
   ```

3. Check S3 bucket permissions:
   ```bash
   aws s3 ls s3://fellowship-reports/
   ```

4. Test submission manually:
   ```bash
   curl -X POST https://api.fellowship.testingfantasy.com/api/teams/{team_id}/submit \
     -H "Content-Type: application/json" \
     -d @test_report.json
   ```

---

## Best Practices

### During Tutorial

1. **Monitor Progress Regularly**
   - **MVP**: Check EC2 instances and Jenkins manually
   - **Full Tutorial**: Check Sauron's Eye every 15-30 minutes
   - Watch for teams that are stuck
   - Identify teams that need help

2. **Time Management**
   - **Short Tutorial (1.5h)**: Keep teams focused on core steps
   - **Full Tutorial (3-4h)**: Allow time for extended features
   - Announce time remaining at 30min, 15min, 5min marks
   - Adjust pace based on team progress

3. **Trigger Challenges Strategically** (Full Tutorial only)
   - Don't overwhelm teams early
   - Space out challenges
   - Adjust difficulty based on team progress
   - **Short Tutorial**: Skip challenges entirely

4. **Provide Help When Needed**
   - Teams stuck for >15 minutes (Short) or >30 minutes (Full): offer hints
   - Teams with no progress for >30 minutes (Short) or >1 hour (Full): intervene
   - Use instructor dashboard to identify issues (Full Tutorial)
   - For MVP, check EC2 instances directly

5. **Encourage Collaboration**
   - Remind teams to work together (Frodo/Sam pairs)
   - Encourage asking questions
   - Share tips with all teams if multiple teams struggle

### Post-Tutorial

1. **Review Reports**
   - Read all submitted reports
   - Identify common issues
   - Note exceptional work

2. **Gather Feedback**
   - Send post-tutorial survey
   - Ask about:
     - Tutorial difficulty
     - Time estimates
     - Most valuable learning
     - Suggestions for improvement

3. **Analyze Data**
   - Review event logs for patterns
   - Identify bottlenecks
   - Calculate success metrics

4. **Follow Up**
   - Announce winner
   - Share highlights
   - Provide resources for continued learning

---

## Emergency Procedures

### System-Wide Issues

**If AWS Services Are Down:**
1. Pause tutorial
2. Notify teams
3. Check AWS status page
4. Wait for service restoration
5. Resume tutorial (extend time if needed)

**If EC2 Instances Fail:**
1. Identify affected teams
2. Create replacement instances
3. Restore team credentials
4. Notify teams of new instance details
5. Allow time for teams to reconnect

### Individual Team Issues

**If Team Can't Progress:**
1. Check their progress in dashboard
2. Review event logs for issues
3. SSH into their instance to investigate
4. Provide targeted help
5. Consider extending their time

**If Team Reports Bug:**
1. Verify it's a real bug (not user error)
2. Check if other teams affected
3. Fix if possible
4. If not fixable, provide workaround
5. Document for post-tutorial fixes

---

## Quick Reference

### Key URLs

- **Sauron's Eye**: `http://sauron-eye.testingfantasy.com` (Full Tutorial only - Phase 4)
- **Instructor Dashboard**: `http://instructor.testingfantasy.com/fellowship`
- **Student Dashboard**: `http://fellowship-of-the-build.testingfantasy.com` (Full Tutorial - Phase 2+)
- **API Endpoint**: `https://api.fellowship.testingfantasy.com` (Full Tutorial - Phase 2+)

### Key Commands

**MVP (Short Tutorial):**
```bash
# Check EC2 instance status
aws ec2 describe-instances --filters "Name=tag:Workshop,Values=fellowship"

# SSH into team instance
ssh ec2-user@<EC2-IP>

# Check Jenkins status
curl http://<EC2-IP>:8080/jenkins/api/json
```

**Full Tutorial (Phase 2+):**
```bash
# Check team progress
aws dynamodb get-item --table-name fellowship_progress --key '{"team_id": {"S": "frodo-sam-01"}}'

# Trigger dark magic challenge (Phase 4)
curl -X POST https://api.fellowship.testingfantasy.com/api/dark-magic/trigger \
  -H "Content-Type: application/json" \
  -d '{"challenge_type": "database_blocked", "team_id": "frodo-sam-01"}'

# Check event logs (Phase 2+)
aws logs filter-log-events --log-group-name /aws/lambda/fellowship-progress-tracker \
  --filter-pattern "team_id frodo-sam-01"

# Get winner (Phase 4)
curl https://api.fellowship.testingfantasy.com/api/winner
```

### Support Contacts

- **Technical Issues**: tech-support@testingfantasy.com
- **Infrastructure**: infra-team@testingfantasy.com
- **Emergency**: on-call@testingfantasy.com

---

## Additional Resources

- [README.md](README.md) - Complete tutorial documentation
- [MCP_SERVERS.md](MCP_SERVERS.md) - MCP server reference
- [JENKINS_MCP_ANALYSIS.md](JENKINS_MCP_ANALYSIS.md) - Jenkins MCP analysis
- [IMPLEMENTATION_TASKS.md](IMPLEMENTATION_TASKS.md) - Implementation details
