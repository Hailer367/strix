<p align="center">
  <a href="https://usestrix.com/">
    <img src=".github/logo.png" width="150" alt="Strix Logo">
  </a>
</p>

<h1 align="center">Strix</h1>

<h2 align="center">Open-source AI Hackers to secure your Apps</h2>

<div align="center">

[![Python](https://img.shields.io/pypi/pyversions/strix-agent?color=3776AB)](https://pypi.org/project/strix-agent/)
[![PyPI](https://img.shields.io/pypi/v/strix-agent?color=10b981)](https://pypi.org/project/strix-agent/)
![PyPI Downloads](https://static.pepy.tech/personalized-badge/strix-agent?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=RED&left_text=Downloads)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

[![GitHub Stars](https://img.shields.io/github/stars/usestrix/strix)](https://github.com/usestrix/strix)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white)](https://discord.gg/YjKFvEZSdZ)
[![Website](https://img.shields.io/badge/Website-usestrix.com-2d3748.svg)](https://usestrix.com)

<a href="https://trendshift.io/repositories/15362" target="_blank"><img src="https://trendshift.io/api/badge/repositories/15362" alt="usestrix%2Fstrix | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>


[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/usestrix/strix)

</div>

<br>

<div align="center">
  <img src=".github/screenshot.png" alt="Strix Demo" width="800" style="border-radius: 16px;">
</div>

<br>

> [!TIP]
> **New!** Strix now features **StrixDB** - a permanent GitHub-based knowledge repository where the AI agent stores scripts, tools, exploits, methods, and useful artifacts for future use!

> [!TIP]
> Strix integrates seamlessly with **GitHub Actions** and CI/CD pipelines. Run automated security scans with configurable timeframes and prompts. See [Flows.md](Flows.md) for the workflow configuration!

---

## 🦉 Strix Overview

Strix are autonomous AI agents that act just like real hackers - they run your code dynamically, find vulnerabilities, and validate them through actual proof-of-concepts. Built for developers and security teams who need fast, accurate security testing without the overhead of manual pentesting or the false positives of static analysis tools.

**Key Capabilities:**

- 🔧 **Full hacker toolkit** out of the box
- 🤝 **Teams of agents** that collaborate and scale
- ✅ **Real validation** with PoCs, not false positives
- 💻 **Developer‑first** CLI with actionable reports
- 🔄 **Auto‑fix & reporting** to accelerate remediation
- 📚 **StrixDB** - Permanent knowledge repository for agent artifacts
- ⚙️ **GitHub Actions** - Automated scans with configurable timeframes


## 🎯 Use Cases

- **Application Security Testing** - Detect and validate critical vulnerabilities in your applications
- **Rapid Penetration Testing** - Get penetration tests done in hours, not weeks, with compliance reports
- **Bug Bounty Automation** - Automate bug bounty research and generate PoCs for faster reporting
- **CI/CD Integration** - Run tests in CI/CD to block vulnerabilities before reaching production

---

## 🆕 New Features (Enhanced Edition)

This enhanced version of Strix includes significant new capabilities:

### 🗄️ StrixDB - Permanent Knowledge Repository (NEW!)

The AI agent now has access to **StrixDB**, a permanent GitHub repository where it stores and retrieves useful artifacts:

- **Scripts & Tools**: Custom scripts, automation tools, and utilities
- **Exploits & PoCs**: Working exploits and proof-of-concept code
- **Knowledge Base**: General security knowledge, methods, and techniques
- **Libraries**: Reusable code libraries and modules
- **Sources**: Useful data sources, wordlists, and references
- **Methods**: Attack methodologies and testing procedures

The agent acts as an **enthusiastic collector**, automatically storing anything useful it discovers or creates for future reference across all engagements.

```python
# Available StrixDB tools:
- strixdb_save(category, name, content, description, tags)  # Save to StrixDB
- strixdb_search(query, category, tags)                      # Search artifacts
- strixdb_get(category, name)                                # Retrieve specific item
- strixdb_list(category)                                     # List items in category
- strixdb_update(category, name, content)                    # Update existing item
- strixdb_delete(category, name)                             # Remove item
```

**Categories supported:**
- `scripts` - Automation scripts and tools
- `exploits` - Working exploits and PoCs
- `knowledge` - Security knowledge and notes
- `libraries` - Reusable code libraries
- `sources` - Wordlists, data sources, references
- `methods` - Attack methodologies
- `tools` - Custom security tools
- `configs` - Configuration files and templates

### ⚙️ GitHub Actions Integration (NEW!)

Run Strix through GitHub Actions with full configuration options:

- **Custom Prompts**: Provide detailed instructions for each scan
- **Timeframe Control**: Set maximum runtime for the AI agent
- **Target Configuration**: Specify targets via workflow inputs
- **Automated Reporting**: Results saved as workflow artifacts

See [Flows.md](Flows.md) for the complete workflow configuration!

### 🔐 Root Terminal Access

The Main AI agent now has **full root/sudo access** by default, enabling:

- **Package Installation**: Install any system packages, libraries, or tools via `apt-get`, `pip`, `npm`
- **Database Management**: Create and manage MySQL, PostgreSQL, SQLite, and MongoDB databases
- **Service Control**: Start, stop, and manage system services
- **Script Execution**: Run scripts with elevated privileges
- **Multiple Root Terminals**: Up to **7 concurrent root terminals** for parallel operations

```python
# Available tools:
- root_execute(command, timeout, terminal_id)  # Execute with root privileges
- create_root_terminal(name)                    # Create new root terminal (max 7)
- install_package(packages)                     # Install apt packages
- install_pip_package(packages)                 # Install Python packages
- install_npm_package(packages)                 # Install Node.js packages
- create_database(db_type, db_name, user, password)  # Create databases
- manage_service(service_name, action)          # Control services
```

### 🤖 Custom Sub-Agent System

Create highly customizable sub-agents with advanced configuration:

- **Root Access for Sub-Agents**: Grant root terminal access to any sub-agent
- **Custom Capabilities**: Configure specific tool access per agent
- **Priority Levels**: Set execution priority (critical, high, medium, low)
- **Custom Instructions**: Inject specialized instructions
- **Dynamic Access Control**: Grant/revoke root access at runtime

```python
# Create a root-enabled agent
create_custom_agent(
    task="Install and configure security tools",
    name="Security Setup Agent",
    root_access=True,
    priority="high",
    capabilities=["root_terminal", "terminal", "file_edit"]
)

# Or use the convenience function
create_root_enabled_agent(
    task="Set up the testing environment",
    name="Environment Agent"
)

# Grant root access dynamically
grant_root_access(target_agent_id="agent_abc123")
```

### 📚 Advanced Knowledge Management

A significantly enhanced knowledge and notes system with:

- **Hierarchical Organization**: Collections and nested folders
- **Entry Linking**: Typed relationships (related_to, depends_on, blocks, references, etc.)
- **Priority Levels**: Critical, high, medium, low
- **Full-Text Search**: Relevance-ranked search with filtering
- **Templates**: Pre-built templates for vulnerabilities, credentials, endpoints, etc.
- **Version History**: Track changes with rollback capability
- **Export/Import**: JSON and Markdown export
- **Cross-Agent Sharing**: Share knowledge between agents

```python
# Create and link entries
create_knowledge_entry(
    title="SQL Injection in Login",
    content="Found SQLi vulnerability...",
    category="findings",
    priority="critical",
    tags=["sqli", "authentication"]
)

link_entries(source_id, target_id, relationship_type="confirms")

# Advanced search
advanced_search(
    query="SQL injection",
    category=["findings"],
    priority=["critical", "high"],
    created_after="2024-01-01"
)

# Use templates
create_from_template("vulnerability", {
    "title": "XSS in Search",
    "severity": "high",
    "poc": "<script>alert(1)</script>"
})
```

### 🎭 Advanced Multi-Agent Orchestration

Significantly improved coordination capabilities:

#### Task Management
- **Priority Queue**: Tasks ordered by priority with dependency resolution
- **Task Dependencies**: Create task chains with circular dependency detection
- **Auto-Assignment**: Automatic load-balanced task distribution
- **Status Tracking**: Full lifecycle tracking (pending → assigned → in_progress → completed)

#### Workload Management
- **Capacity Control**: Set max concurrent tasks per agent (1-20)
- **Utilization Monitoring**: Track agent workload percentages
- **Load Balancing**: Automatic distribution to least busy agents

#### Team Management
- **Create Teams**: Organize agents into functional teams
- **Role Assignment**: Assign roles (member, specialist, coordinator)
- **Team Coordination**: Broadcast messages to team members

#### Advanced Coordination
- **Broadcast Messaging**: Send to all agents, specific agents, or teams
- **Coordination Requests**: Request assistance, review, approval, or handoff
- **Synchronization Points**: Create checkpoints for multi-agent sync
- **Resource Management**: Allocate and manage shared resources

#### Workflow Automation
- **Workflow Definition**: Create multi-step workflows with dependencies
- **Workflow Execution**: Execute workflows with automatic task creation
- **Pause/Resume**: Control workflow execution

```python
# Create a workflow
create_workflow(
    name="Security Assessment",
    description="Complete security assessment workflow",
    steps=[
        {"name": "Recon", "task_template": "Perform reconnaissance"},
        {"name": "Scan", "task_template": "Run vulnerability scan", "depends_on": ["Recon"]},
        {"name": "Exploit", "task_template": "Validate vulnerabilities", "depends_on": ["Scan"]},
        {"name": "Report", "task_template": "Generate report", "depends_on": ["Exploit"]}
    ]
)

# Create a team
create_agent_team(
    name="Exploitation Team",
    initial_members=["agent_abc", "agent_def"]
)

# Broadcast to team
broadcast_message(
    message="Focus on authentication endpoints",
    team_id="team_xyz",
    priority="high"
)

# Get orchestration status
get_orchestration_dashboard()
```

---

## 🚀 Quick Start

**Prerequisites:**
- Docker (running)
- An LLM provider (CLIProxyAPI recommended, or API key from OpenAI/Anthropic/Google)

### Installation & First Scan

```bash
# Install Strix
curl -sSL https://strix.ai/install | bash

# Or via pipx
pipx install strix-agent

# Run your first security assessment
strix --target ./app-directory
```

### 📝 Configuration via config.json (Recommended)

Strix uses a **config.json** file for configuration. This provides CLIProxyAPI integration and configurable timeframes.

**Step 1: Run CLIProxyAPI**
```bash
# Download from https://github.com/router-for-me/CLIProxyAPI/releases
cliproxy run --port 8317
```

**Step 2: Create config.json**
```json
{
  "api": {
    "endpoint": "http://localhost:8317/v1",
    "model": "gemini-2.5-pro"
  },
  "timeframe": {
    "duration_minutes": 60,
    "warning_minutes": 5,
    "time_awareness_enabled": true
  },
  "dashboard": {
    "enabled": true,
    "show_time_remaining": true
  }
}
```

**Step 3: Run Strix**
```bash
strix --target ./app-directory
```

**CLIProxyAPI Benefits:**
- 🔑 **No API Keys Needed** - Use your existing subscriptions via OAuth
- ⚖️ **Automatic Load Balancing** - Distributes requests across accounts
- 🔄 **Failover Support** - Auto-switches when quotas are exceeded
- 📊 **Real-time Dashboard** - Monitor agent activity and time remaining
- ⏱️ **Configurable Timeframes** - Set duration from 10 minutes to 12 hours

### ⏱️ Timeframe Configuration (NEW!)

Configure session duration from **10 minutes to 12 hours**:

| Duration | Use Case |
|----------|----------|
| 10-15 min | Quick CI checks |
| 30-60 min | Standard scans |
| 2-4 hours | Deep audits |
| 8-12 hours | Extended pentests |

The AI automatically receives time warnings to finish up before the session ends.

### Legacy: Environment Variables

If you prefer environment variables:

```bash
export STRIX_LLM="openai/gpt-5"
export LLM_API_BASE="http://localhost:8317/v1"
strix --target ./app-directory
```

> [!NOTE]
> First run automatically pulls the sandbox Docker image. Results are saved to `strix_runs/<run-name>`

---

## ⚙️ GitHub Actions Workflow

Run Strix automatically via GitHub Actions! See [Flows.md](Flows.md) for the complete workflow configuration.

**Quick Setup:**

1. Add secrets to your repository:
   - `STRIX_LLM` - Model name (e.g., `openai/gpt-5`)
   - `LLM_API_KEY` - Your API key
   - `STRIXDB_TOKEN` - GitHub token for StrixDB access

2. Copy the workflow from [Flows.md](Flows.md) to `.github/workflows/strix.yml`

3. Trigger manually or on events with custom inputs:
   - **prompt**: Custom instructions for the AI agent
   - **timeframe**: Maximum runtime in minutes (default: 60)
   - **target**: Target to scan

---

## ✨ Features

### 🛠️ Agentic Security Tools

Strix agents come equipped with a comprehensive security testing toolkit:

- **Full HTTP Proxy** - Full request/response manipulation and analysis
- **Browser Automation** - Multi-tab browser for testing of XSS, CSRF, auth flows
- **Terminal Environments** - Interactive shells for command execution and testing
- **Root Terminal Access** - Full sudo/root access for privileged operations
- **Python Runtime** - Custom exploit development and validation
- **Reconnaissance** - Automated OSINT and attack surface mapping
- **Code Analysis** - Static and dynamic analysis capabilities
- **Knowledge Management** - Structured findings with linking and search
- **StrixDB Integration** - Permanent artifact storage and retrieval (NEW!)

### 🎯 Comprehensive Vulnerability Detection

Strix can identify and validate a wide range of security vulnerabilities:

- **Access Control** - IDOR, privilege escalation, auth bypass
- **Injection Attacks** - SQL, NoSQL, command injection
- **Server-Side** - SSRF, XXE, deserialization flaws
- **Client-Side** - XSS, prototype pollution, DOM vulnerabilities
- **Business Logic** - Race conditions, workflow manipulation
- **Authentication** - JWT vulnerabilities, session management
- **Infrastructure** - Misconfigurations, exposed services

### 🕸️ Graph of Agents

Advanced multi-agent orchestration for comprehensive security testing:

- **Distributed Workflows** - Specialized agents for different attacks and assets
- **Scalable Testing** - Parallel execution for fast comprehensive coverage
- **Dynamic Coordination** - Agents collaborate and share discoveries
- **Priority-Based Scheduling** - Task prioritization with dependency resolution
- **Load Balancing** - Automatic workload distribution
- **Team Management** - Organize agents into functional teams
- **Workflow Automation** - Define and execute multi-step workflows

---

## 💻 Usage Examples

### Basic Usage

```bash
# Scan a local codebase
strix --target ./app-directory

# Security review of a GitHub repository
strix --target https://github.com/org/repo

# Black-box web application assessment
strix --target https://your-app.com
```

### Advanced Testing Scenarios

```bash
# Grey-box authenticated testing
strix --target https://your-app.com --instruction "Perform authenticated testing using credentials: user:pass"

# Multi-target testing (source code + deployed app)
strix -t https://github.com/org/app -t https://your-app.com

# Focused testing with custom instructions
strix --target api.your-app.com --instruction "Focus on business logic flaws and IDOR vulnerabilities"

# Provide detailed instructions through file (e.g., rules of engagement, scope, exclusions)
strix --target api.your-app.com --instruction-file ./instruction.md
```

### 🤖 Headless Mode

Run Strix programmatically without interactive UI using the `-n/--non-interactive` flag—perfect for servers and automated jobs. The CLI prints real-time vulnerability findings, and the final report before exiting. Exits with non-zero code when vulnerabilities are found.

```bash
strix -n --target https://your-app.com
```

### 🔄 CI/CD (GitHub Actions)

Strix can be added to your pipeline to run a security test on pull requests. See [Flows.md](Flows.md) for the complete workflow configuration with prompt and timeframe support!

Basic example:

```yaml
name: strix-penetration-test

on:
  pull_request:

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Install Strix
        run: curl -sSL https://strix.ai/install | bash

      - name: Run Strix
        env:
          STRIX_LLM: ${{ secrets.STRIX_LLM }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}

        run: strix -n -t ./ --scan-mode quick
```

### ⚙️ Configuration

#### CLIProxyAPI (Recommended)

```bash
# CLIProxyAPI is enabled by default
export CLIPROXY_ENABLED="true"
export CLIPROXY_BASE_URL="http://localhost:8317/v1"  # CLIProxyAPI server URL
export CLIPROXY_MANAGEMENT_KEY="your-management-key"  # Optional: for management API access

# Model to use (available from connected accounts)
export STRIX_LLM="gemini-2.5-pro"  # or claude-sonnet-4, gpt-5, etc.

# Optional
export PERPLEXITY_API_KEY="your-api-key"  # for search capabilities
```

#### Direct API Access

```bash
export CLIPROXY_ENABLED="false"  # Disable CLIProxyAPI mode
export STRIX_LLM="openai/gpt-5"
export LLM_API_KEY="your-api-key"

# Optional
export LLM_API_BASE="your-api-base-url"  # for local models (Ollama, LMStudio)
export PERPLEXITY_API_KEY="your-api-key"  # for search capabilities
```

#### StrixDB Configuration

```bash
# StrixDB GitHub repository settings
export STRIXDB_REPO="username/StrixDB"        # Your StrixDB repository
export STRIXDB_TOKEN="your-github-token"      # GitHub token with repo access
export STRIXDB_BRANCH="main"                  # Branch to use (default: main)
```

#### Supported Models

With **CLIProxyAPI**, you can access models from multiple providers through a single endpoint:

| Provider | Models |
|----------|--------|
| Google | gemini-2.5-pro, gemini-2.5-flash, gemini-pro |
| Anthropic | claude-sonnet-4, claude-3-5-sonnet, claude-3-opus |
| OpenAI | gpt-5, gpt-4o, o1, o3, codex |
| Qwen | qwen-max, qwen-plus |

[OpenAI's GPT-5](https://openai.com/api/) and [Anthropic's Claude Sonnet 4](https://claude.com/platform/api) are recommended for best results. We also support many [other options](https://docs.litellm.ai/docs/providers), including cloud and local models.

---

## 🤝 Contributing

We welcome contributions of code, docs, and new prompt modules - check out our [Contributing Guide](CONTRIBUTING.md) to get started or open a [pull request](https://github.com/usestrix/strix/pulls)/[issue](https://github.com/usestrix/strix/issues).

## 👥 Join Our Community

Have questions? Found a bug? Want to contribute? **[Join our Discord!](https://discord.gg/YjKFvEZSdZ)**

## 🌟 Support the Project

**Love Strix?** Give us a ⭐ on GitHub!

## 🙏 Acknowledgements

Strix builds on the incredible work of open-source projects like [LiteLLM](https://github.com/BerriAI/litellm), [Caido](https://github.com/caido/caido), [ProjectDiscovery](https://github.com/projectdiscovery), [Playwright](https://github.com/microsoft/playwright), and [Textual](https://github.com/Textualize/textual). Huge thanks to their maintainers!


> [!WARNING]
> Only test apps you own or have permission to test. You are responsible for using Strix ethically and legally.

</div>

---

## 🆕 NEW: CVE/Exploit Database Integration

### 🔍 Purpose
Help AI agents find and use known vulnerabilities for identified technologies. When the AI finds a technology like "nginx/1.18.0", it can now automatically query vulnerability databases for known CVEs and find working exploits.

### 📊 Data Sources
- **NVD (National Vulnerability Database)** - Official CVE database with CVSS scores
- **Exploit-DB** - Exploit and PoC repository
- **GitHub Security Advisories** - Package vulnerability database
- **PacketStorm** - Additional exploit/tool source

### 🛠️ New Tools

| Tool | Description |
|------|-------------|
| `query_cve_database` | Query NVD for CVEs by technology/version |
| `search_exploitdb` | Search Exploit-DB for PoCs |
| `get_cve_details` | Get detailed CVE information with exploitability |
| `search_github_advisories` | Search GitHub Security Advisories |
| `get_technology_vulnerabilities` | **Aggregate vuln data from ALL sources** |
| `search_packetstorm` | Search PacketStorm for exploits |

### 💡 Usage Example
```python
# When AI finds "nginx/1.18.0" in Server header
result = get_technology_vulnerabilities("nginx", version="1.18.0")

# Output includes:
# - CVE list with severity scores
# - Public exploit availability
# - Actionable recommendations
# - Links to PoCs and patches
```

### 🎯 Why It Helps Bug Bounty
- Automatically test for known CVEs based on detected versions
- Use pre-built PoCs instead of crafting from scratch
- Prioritize targets running vulnerable software
- Save hours of manual CVE research

---

## 🆕 NEW: Multi-Agent Collaboration Protocol

### 🎯 Purpose
Enable multiple AI agents to work together efficiently without duplicating effort or missing findings.

### ❌ Problem Solved
Without coordination:
- Agent A tests `/login` for SQLi
- Agent B also tests `/login` for SQLi (wasted effort!)
- Agent C finds SSRF but Agent D doesn't know (missed chaining!)

### ✅ Solution - Collaboration Protocol

#### 1. Claim System
```python
# Agent A claims target
claim_target(agent_state, "/login", "sqli")

# Agent B sees claim and tests different vuln instead
claim_target(agent_state, "/login", "xss")
```

#### 2. Finding Sharing (for chaining)
```python
# Agent C finds SSRF
share_finding(
    agent_state,
    title="SSRF at /api/fetch",
    vulnerability_type="ssrf",
    target="/api/fetch?url=",
    chainable=True,
    chain_suggestions=["idor", "auth_bypass"]
)

# All agents see: "SSRF found, test for chaining!"
```

#### 3. Work Queue
```python
# Add discovered endpoints to queue
add_to_work_queue(
    agent_state,
    target="/api/v2/users/{id}",
    description="New API endpoint from JS bundle",
    test_types=["idor", "auth_bypass"],
    priority="high"
)

# Agents pick from queue
work_item = get_next_work_item(agent_state)
```

#### 4. Help Requests
```python
# Agent A needs help
request_help(
    agent_state,
    help_type="decode",
    description="Found base64 encoded parameter",
    data="eyJ1c2VyIjoiYWRtaW4ifQ=="
)

# Specialized agent responds
```

### 🛠️ New Tools

| Tool | Description |
|------|-------------|
| `claim_target` | Claim endpoint/parameter for testing |
| `release_claim` | Release a claim when done |
| `list_claims` | See what's being tested |
| `share_finding` | Share vulnerabilities for chaining |
| `list_findings` | Get all shared findings |
| `get_finding_details` | Get full PoC details |
| `add_to_work_queue` | Add targets to test queue |
| `get_next_work_item` | Pick up next item to test |
| `request_help` | Ask for specialized help |
| `get_collaboration_status` | Overview of all activities |
| `broadcast_message` | Send messages to all agents |

### 🎯 Why It Helps Bug Bounty
- **More efficient testing** - No duplicate work
- **Better vulnerability chaining** - Shared findings enable creative chains
- **No missed opportunities** - Full coverage with work queue
- **Specialized assistance** - Get help when stuck

---

## 📁 All Modules and Files

### StrixDB Module (`strix/tools/strixdb/`) **NEW!**
- `__init__.py` - Module exports
- `strixdb_actions.py` - StrixDB GitHub repository operations
- `strixdb_actions_schema.xml` - XML schema for tools

### Root Terminal Module (`strix/tools/root_terminal/`)
- `__init__.py` - Module exports
- `root_terminal_actions.py` - Tool functions for root operations
- `root_terminal_actions_schema.xml` - XML schema for tools
- `root_terminal_manager.py` - Manager for multiple root terminals
- `root_terminal_session.py` - Individual terminal session handling

### Custom Agents Module (`strix/tools/custom_agents/`)
- `__init__.py` - Module exports
- `custom_agent_actions.py` - Custom agent creation and management
- `custom_agent_actions_schema.xml` - XML schema for tools

### Knowledge Module (`strix/tools/knowledge/`)
- `__init__.py` - Module exports
- `knowledge_actions.py` - Advanced knowledge management system
- `knowledge_actions_schema.xml` - XML schema for tools

### Orchestration Module (`strix/tools/orchestration/`)
- `__init__.py` - Module exports
- `orchestration_actions.py` - Multi-agent orchestration system
- `orchestration_actions_schema.xml` - XML schema for tools

### CVE Database Module (`strix/tools/cve_database/`)
- `__init__.py` - Module exports
- `cve_database_actions.py` - CVE/Exploit database integration
- `cve_database_actions_schema.xml` - XML schema for tools

### Collaboration Module (`strix/tools/collaboration/`)
- `__init__.py` - Module exports
- `collaboration_actions.py` - Multi-agent collaboration protocol
- `collaboration_actions_schema.xml` - XML schema for tools

### TUI Renderers (`strix/interface/tool_components/`)
- `cve_renderer.py` - Rich output for CVE database results
- `collaboration_renderer.py` - Rich output for collaboration status
- `strixdb_renderer.py` - Rich output for StrixDB operations (NEW!)

### Prompt Modules (`strix/prompts/`)
- `vulnerabilities/cve_hunting.jinja` - CVE hunting guidance
- `coordination/multi_agent_collaboration.jinja` - Collaboration protocol guide

### Test Suite (`tests/`)
- `test_cve_database.py` - 200+ test assertions for CVE module
- `test_collaboration.py` - 200+ test assertions for collaboration module
- `test_strixdb.py` - Tests for StrixDB module (NEW!)

### Modified Files
- `strix/tools/__init__.py` - Updated to include all new modules
- `strix/interface/tool_components/__init__.py` - Updated with new renderers
