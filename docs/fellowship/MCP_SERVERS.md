# MCP Servers Reference Guide

## Overview

This document provides detailed information about all MCP servers used in the Fellowship tutorial, including official servers from the [Model Context Protocol servers repository](https://github.com/modelcontextprotocol/servers) and custom servers created for the tutorial.

## Official MCP Servers

### Playwright MCP (Official)

**Package**: `@playwright/mcp`  
**Status**: ✅ Official  
**Documentation**: https://playwright.dev/agents  
**Repository**: https://github.com/microsoft/playwright

#### Installation

```bash
# Global installation
npm install -g @playwright/mcp

# Or use npx (no installation needed)
npx @playwright/mcp@latest
```

#### Configuration

**VS Code / Cursor:**
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp"]
    }
  }
}
```

**Claude Desktop:**
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp"]
    }
  }
}
```

#### Features

- **Test Generation**: Generate Playwright tests from natural language requirements
- **Browser Automation**: Control browsers using accessibility snapshots (not pixels)
- **Trace Capture**: Save detailed traces with `--save-trace` flag
- **Session Logging**: Record MCP tool calls with `--save-session` flag
- **Screenshots & PDFs**: Generate artifacts via `--output-dir`

#### Tools Available

The official Playwright MCP provides tools for:
- Browser navigation and interaction
- Test generation
- Trace analysis
- Screenshot capture

#### Usage in Tutorial

Teams use the official Playwright MCP for:
1. Generating test cases from requirements
2. Browser automation and interaction
3. Test debugging with traces
4. Creating test reports with screenshots

**Example:**
```python
# Agent automatically has access to Playwright MCP tools
# No custom code needed - MCP client handles it
```

#### Verification

Teams are verified to use Playwright MCP through:
- `mcp.tool.invoked` events with `tool` starting with `playwright_`
- `test.case.created` events with `method: 'mcp'`
- Trace files in `.playwright-mcp/` directory

---

### Git MCP (Official)

**Package**: `mcp-server-git`  
**Status**: ✅ Official  
**Repository**: https://github.com/modelcontextprotocol/servers (Python)

#### Installation

```bash
# Using uvx (recommended)
uvx mcp-server-git

# Or using pip
pip install mcp-server-git
python -m mcp_server_git
```

#### Configuration

```json
{
  "mcpServers": {
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "/path/to/fellowship-tests"]
    }
  }
}
```

#### Features

- Repository status and information
- Commit history and tracking
- File change detection
- Branch operations

#### Tools Available

- `git_status` - Get repository status
- `git_log` - Get commit history
- `git_diff` - Get file differences
- `git_branch` - Branch operations

#### Usage in Tutorial

Teams use Git MCP for:
1. Tracking test file changes
2. Monitoring repository activity
3. Integrating with event tracking (via git hooks)

**Example:**
```python
# Git MCP can be used to track repository changes
# Integrated with event tracking system
```

---

### Filesystem MCP (Official - Optional)

**Package**: `@modelcontextprotocol/server-filesystem`  
**Status**: ✅ Official  
**Repository**: https://github.com/modelcontextprotocol/servers

#### Installation

```bash
npx -y @modelcontextprotocol/server-filesystem /path/to/allowed/files
```

#### Configuration

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/ec2-user/fellowship-tests"]
    }
  }
}
```

#### Features

- File read/write operations
- Directory listing
- File management

#### Tools Available

- `read_file` - Read file contents
- `write_file` - Write file contents
- `list_directory` - List directory contents
- `create_directory` - Create directories

#### Usage in Tutorial

Teams can use Filesystem MCP for:
1. Reading test files
2. Writing test files
3. Managing test repository structure

**Note**: This is optional - teams can also use custom Playwright MCP or direct file operations.

---

### GitHub MCP (Official - Optional)

**Package**: `@modelcontextprotocol/server-github`  
**Status**: ✅ Official  
**Repository**: https://github.com/modelcontextprotocol/servers

#### Installation

```bash
npx -y @modelcontextprotocol/server-github
```

#### Configuration

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<YOUR_TOKEN>"
      }
    }
  }
}
```

#### Features

- GitHub repository operations
- Issue management
- Pull request operations
- CI/CD integration (GitHub Actions)

#### Usage in Tutorial

**Optional** - Only if tutorial uses GitHub Actions instead of Jenkins. Not used in current tutorial design.

---

### Postgres MCP (Official - Optional)

**Package**: `@modelcontextprotocol/server-postgres`  
**Status**: ✅ Official  
**Repository**: https://github.com/modelcontextprotocol/servers

#### Installation

```bash
npx -y @modelcontextprotocol/server-postgres postgresql://localhost/mydb
```

#### Configuration

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/sut_db"]
    }
  }
}
```

#### Features

- Database queries
- Schema operations
- Data management

#### Usage in Tutorial

**Optional** - Only if SUT uses Postgres database. Can be used for database testing scenarios.

---

## Custom MCP Servers

### Jenkins MCP Server (Custom - Required)

**Status**: ❌ No official MCP server exists  
**Implementation**: Custom Python MCP server  
**Repository**: `mcp-server-jenkins` (separate public repository)  
**Location**: `https://github.com/testingfantasy/mcp-server-jenkins`  
**Installation**: `pip install mcp-server-jenkins` or `uvx mcp-server-jenkins`

#### Why Custom?

- **No Official Server**: No Jenkins MCP server exists in the [official repository](https://github.com/modelcontextprotocol/servers)
- **Tutorial Requirement**: Jenkins is critical for CI/CD in the tutorial
- **Learning Opportunity**: Students learn MCP server creation
- **Community Value**: Published to PyPI and can be submitted to official MCP registry

#### Analysis

See [JENKINS_MCP_ANALYSIS.md](JENKINS_MCP_ANALYSIS.md) for:
- Detailed analysis of options
- Comparison with direct API approach
- Implementation recommendations
- Publication considerations

#### Installation

**From PyPI (Recommended):**
```bash
pip install mcp-server-jenkins
```

**From Repository:**
```bash
git clone https://github.com/testingfantasy/mcp-server-jenkins.git
cd mcp-server-jenkins
pip install -e .
```

**Using uvx:**
```bash
uvx mcp-server-jenkins
```

#### Implementation

**Repository Structure:**
```
mcp-server-jenkins/
├── src/
│   └── mcp_server_jenkins/
│       ├── __init__.py
│       ├── server.py          # Main MCP server
│       └── tools.py            # MCP tools implementation
├── setup.py                    # PyPI package configuration
├── README.md                   # Documentation
└── tests/                      # Unit tests
```

**Tools Provided:**

1. **`get_jenkins_job_status`**
   - Get current status of a Jenkins job
   - Parameters: `job_name` (string)
   - Returns: Job status, last build number, health

2. **`trigger_jenkins_job`**
   - Trigger a Jenkins job execution
   - Parameters: `job_name` (string), `parameters` (dict, optional)
   - Returns: Build number, queue item

3. **`get_jenkins_build_logs`**
   - Retrieve build logs for a specific build
   - Parameters: `job_name` (string), `build_number` (int)
   - Returns: Console output, build status

4. **`get_jenkins_job_history`**
   - Get recent build history for a job
   - Parameters: `job_name` (string), `limit` (int, default: 10)
   - Returns: List of builds with status and timestamps

5. **`analyze_jenkins_failure`**
   - Analyze why a Jenkins build failed
   - Parameters: `job_name` (string), `build_number` (int)
   - Returns: Failure analysis, error patterns, recommendations

6. **`get_jenkins_console_output`**
   - Get console output for a build
   - Parameters: `job_name` (string), `build_number` (int)
   - Returns: Full console output

7. **`cancel_jenkins_build`**
   - Cancel a running Jenkins build
   - Parameters: `job_name` (string), `build_number` (int)
   - Returns: Cancellation status

#### Code Example

```python
# mcp-server-jenkins (installed via pip)
from mcp import MCPServer, Tool
from typing import Dict
import requests
from fellowship_events import EventClient

class JenkinsMCPServer(MCPServer):
    def __init__(self, jenkins_url: str, username: str, api_token: str):
        super().__init__("jenkins-mcp")
        self.jenkins_url = jenkins_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self.event_client = EventClient()  # Requires fellowship-events package
        self._register_tools()
    
    def _register_tools(self):
        """Register all Jenkins MCP tools."""
        self.register_tool(Tool(
            name="get_jenkins_job_status",
            description="Get the current status of a Jenkins job",
            input_schema={
                "type": "object",
                "properties": {
                    "job_name": {"type": "string", "description": "Name of the Jenkins job"}
                },
                "required": ["job_name"]
            },
            handler=self._get_job_status
        ))
        # ... register other tools
    
    async def _get_job_status(self, job_name: str) -> Dict:
        """Get Jenkins job status."""
        # Emit event for tracking
        self.event_client.emit('mcp.tool.invoked', {
            'tool': 'get_jenkins_job_status',
            'parameters': {'job_name': job_name}
        })
        
        try:
            url = f"{self.jenkins_url}/job/{job_name}/api/json"
            response = requests.get(
                url,
                auth=(self.username, self.api_token),
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": "success",
                "job_name": job_name,
                "last_build": data.get('lastBuild', {}).get('number'),
                "last_successful_build": data.get('lastSuccessfulBuild', {}).get('number'),
                "last_failed_build": data.get('lastFailedBuild', {}).get('number'),
                "health": data.get('healthReport', [{}])[0].get('score', 100)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
```

#### Authentication

Supports:
- Jenkins API tokens (recommended)
- Basic authentication
- Jenkins credentials plugin

#### Event Integration

All tool invocations emit events:
- `mcp.tool.invoked` - Every tool call
- Event data includes tool name and parameters
- Integrated with `fellowship-events` SDK

#### Usage in Tutorial

Teams use Jenkins MCP for:
1. Monitoring Jenkins pipelines
2. Retrieving build information
3. Triggering job executions
4. Analyzing build failures
5. Generating reports from Jenkins data

**Installation in Tutorial:**
```bash
# Install from PyPI
pip install mcp-server-jenkins

# Or install from repository if not yet published
git clone https://github.com/testingfantasy/mcp-server-jenkins.git
cd mcp-server-jenkins
pip install -e .
```

**Dependencies:**
- `fellowship-events` (installed via pip)
- `mcp` Python SDK

---

## MCP Server Comparison

| MCP Server | Status | Package | Installation | Use Case | Tutorial Priority |
|------------|--------|---------|--------------|----------|-------------------|
| **Playwright** | ✅ Official | `@playwright/mcp` | `npm install -g @playwright/mcp` | Test generation | **Critical** |
| **Jenkins** | ❌ Custom | Custom | Part of `fellowship-mcp-agent` | CI/CD monitoring | **Critical** |
| **Git** | ✅ Official | `mcp-server-git` | `uvx mcp-server-git` | Repository management | **High** |
| **Filesystem** | ✅ Official | `@modelcontextprotocol/server-filesystem` | `npx -y @modelcontextprotocol/server-filesystem` | File operations | **Medium** |
| **GitHub** | ✅ Official | `@modelcontextprotocol/server-github` | `npx -y @modelcontextprotocol/server-github` | GitHub integration | **Low** (optional) |
| **Postgres** | ✅ Official | `@modelcontextprotocol/server-postgres` | `npx -y @modelcontextprotocol/server-postgres` | Database ops | **Low** (optional) |

---

## Integration with LangChain Agents

### Converting MCP Tools to LangChain Tools

```python
from langchain.tools import StructuredTool

def get_langchain_tools(mcp_server):
    """Convert MCP tools to LangChain tools."""
    langchain_tools = []
    
    for tool in mcp_server.tools:
        langchain_tool = StructuredTool.from_function(
            func=tool.handler,
            name=tool.name,
            description=tool.description,
            args_schema=tool.input_schema
        )
        langchain_tools.append(langchain_tool)
    
    return langchain_tools
```

### Using Multiple MCP Servers

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI

# Get tools from multiple MCP servers
playwright_tools = get_langchain_tools(playwright_mcp)
jenkins_tools = get_langchain_tools(jenkins_mcp)
git_tools = get_langchain_tools(git_mcp)

# Combine all tools
all_tools = playwright_tools + jenkins_tools + git_tools

# Create agent with all MCP tools
agent = create_openai_tools_agent(
    llm=ChatOpenAI(model="gpt-4"),
    tools=all_tools,
    prompt=prompt
)
```

---

## Verification Methods

### Method 1: Event Tracking (Primary - High Confidence)

**Events Emitted:**
- `mcp.tool.invoked` - Every MCP tool call
- `mcp.server.connected` - MCP server connected
- `mcp.agent.created` - Agent created with MCP servers
- `test.case.created` with `method: 'mcp'` - Tests created via MCP
- `test.case.fixed` with `method: 'mcp'` - Tests fixed via MCP

**Verification Query:**
```python
def verify_mcp_usage(team_id: str) -> Dict:
    """Verify team used MCPs."""
    events = get_team_events(team_id)
    
    mcp_tools_used = [
        e for e in events 
        if e['event_type'] == 'mcp.tool.invoked'
    ]
    
    return {
        'used_mcps': len(mcp_tools_used) > 0,
        'tools_invoked': len(mcp_tools_used),
        'tools_used': [e['event_data']['tool'] for e in mcp_tools_used]
    }
```

### Method 2: Code Analysis (Medium Confidence)

Check for:
- AI-generated code patterns
- Consistent formatting
- Comprehensive docstrings
- Recent file creation

### Method 3: Git History (Medium Confidence)

Check for:
- AI-related commit messages
- Bulk test creation
- Test fix patterns

### Method 4: File Patterns (Low Confidence)

Check for:
- Bulk file creation
- Timestamp patterns

### Method 5: Instructor Dashboard (Comprehensive)

Combines all methods into verification score.

**See**: [PLAYWRIGHT_MCP_INTEGRATION.md](PLAYWRIGHT_MCP_INTEGRATION.md) for detailed verification methods (this file will be merged into README.md).

---

## Best Practices

### Using Official MCPs

1. **Prefer Official**: Use official MCP servers when available
2. **Keep Updated**: Regularly update official MCP packages
3. **Follow Documentation**: Use official documentation for configuration
4. **Report Issues**: Report bugs to official repositories

### Creating Custom MCPs

1. **Follow MCP Spec**: Adhere to [MCP specification](https://modelcontextprotocol.io)
2. **Emit Events**: Integrate with event tracking system
3. **Error Handling**: Handle errors gracefully
4. **Documentation**: Document all tools clearly
5. **Testing**: Write comprehensive tests

### MCP Server Integration

1. **Standardize Tools**: Use consistent tool naming
2. **Validate Inputs**: Validate all parameters
3. **Emit Events**: Track all tool invocations
4. **Handle Errors**: Return meaningful error messages
5. **Document Usage**: Provide clear examples

---

## Troubleshooting

### MCP Server Won't Connect

**Symptoms**: Agent can't access MCP tools

**Solutions**:
1. Check MCP server is installed correctly
2. Verify configuration in MCP client settings
3. Check credentials and authentication
4. Review MCP server logs

### MCP Tools Not Available

**Symptoms**: Agent doesn't see MCP tools

**Solutions**:
1. Verify MCP server is running
2. Check MCP client connection
3. Verify tool registration
4. Review agent tool loading

### Event Tracking Not Working

**Symptoms**: MCP tool invocations not tracked

**Solutions**:
1. Check `fellowship-events` SDK is installed
2. Verify environment variables are set
3. Check event emission in MCP server code
4. Review event tracking logs

---

## References

- [Official MCP Servers Repository](https://github.com/modelcontextprotocol/servers)
- [MCP Registry](https://registry.modelcontextprotocol.io/)
- [MCP Specification](https://modelcontextprotocol.io)
- [Playwright MCP Documentation](https://playwright.dev/agents)
- [JENKINS_MCP_ANALYSIS.md](JENKINS_MCP_ANALYSIS.md) - Jenkins MCP analysis
