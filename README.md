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
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/strix-agent?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=RED&left_text=Downloads)](https://pepy.tech/projects/strix-agent)
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
> **New!** Strix now features **Roo Code Cloud Integration** for free AI models, **Qwen Code CLI Integration** for additional free models, **Root Access Mode** for unrestricted terminal commands, and **GitHub Actions Dashboard** for autonomous bug bounty automation!

---

## Table of Contents

- [Overview](#-strix-overview)
- [Key Features](#-key-features)
- [Use Cases](#-use-cases)
- [Quick Start](#-quick-start)
- [Installation](#installation)
- [Roo Code Cloud Integration](#-roo-code-cloud-integration)
- [Qwen Code CLI Integration](#-qwen-code-cli-integration)
- [Root Access Mode](#-root-access-mode)
- [GitHub Actions & Dashboard](#-github-actions--autonomous-dashboard)
- [Configuration](#%EF%B8%8F-configuration)
- [Usage Examples](#-usage-examples)
- [Architecture](#-architecture)
- [Tools & Capabilities](#-tools--capabilities)
- [Multi-Agent System](#-multi-agent-system)
- [CI/CD Integration](#-cicd-integration)
- [Cloud Version](#%EF%B8%8F-run-strix-in-cloud)
- [Contributing](#-contributing)
- [Community](#-join-our-community)
- [Acknowledgements](#-acknowledgements)

---

## Overview

Strix is an advanced autonomous AI agent platform designed for penetration testing and bug bounty automation. Unlike traditional security scanners that rely on signatures and patterns, Strix agents think and act like real hackers - dynamically analyzing applications, discovering vulnerabilities, and validating them through actual proof-of-concepts.

### What Makes Strix Different?

| Feature | Traditional Scanners | Strix AI Agents |
|---------|---------------------|-----------------|
| **Analysis Method** | Pattern matching | Contextual understanding |
| **Validation** | Report-based | Real PoC execution |
| **False Positives** | High | Minimal (validated findings) |
| **Adaptability** | Static rules | Dynamic, learns from context |
| **Complex Vulnerabilities** | Limited | Excels (business logic, chained attacks) |
| **Tool Installation** | Fixed toolset | Dynamic (with root access) |

---

## Key Features

### Core Capabilities

- **Autonomous AI Hackers** - Intelligent agents that think, plan, and execute like professional pentesters
- **Real Vulnerability Validation** - Every finding is validated with working proof-of-concepts
- **Multi-Agent Collaboration** - Specialized agents work together on complex assessments
- **Developer-First CLI** - Beautiful terminal UI with actionable reports
- **Auto-Fix Suggestions** - Not just findings, but remediation guidance

### Advanced Features

- **Roo Code Cloud Integration** - Free AI models with zero configuration
- **Root Access Mode** - Unrestricted terminal access for advanced testing
- **GitHub Actions Dashboard** - Configure-and-fire autonomous bug bounty automation
- **Real-Time Web Search** - Live intelligence gathering with Perplexity AI
- **Full HTTP Proxy** - Complete request/response manipulation
- **Browser Automation** - Multi-tab browser for XSS, CSRF, auth flow testing

---

## Use Cases

### Application Security Testing
Detect and validate critical vulnerabilities in web applications, APIs, and microservices with comprehensive testing coverage.

### Rapid Penetration Testing
Get professional penetration tests completed in hours instead of weeks, with compliance-ready reports and detailed findings.

### Bug Bounty Automation
Automate bug bounty research with intelligent target reconnaissance, vulnerability discovery, and automated PoC generation.

### CI/CD Security Gates
Integrate security testing into your development pipeline to block vulnerabilities before they reach production.

### Continuous Security Monitoring
Set up automated security assessments to catch new vulnerabilities as your application evolves.

---

## Quick Start

### Prerequisites

- **Docker** (running)
- **Python 3.12+**
- **LLM Provider** (choose one):
  - Roo Code Cloud (free, no API keys needed)
  - OpenAI API key
  - Anthropic API key
  - Local LLM (Ollama, LMStudio)

### Installation

```bash
# Install Strix globally
pipx install strix-agent

# Or with pip
pip install strix-agent
```

### First Scan

#### Option 1: Using Roo Code Cloud (Recommended for beginners)

```bash
# Authenticate with Roo Code Cloud (one-time, opens browser)
strix --roocode-login

# Run your first scan with free AI models
strix --roocode --target https://your-app.com
```

#### Option 2: Using OpenAI/Anthropic

```bash
# Configure your AI provider
export STRIX_LLM="openai/gpt-5"
export LLM_API_KEY="your-api-key"

# Run your first scan
strix --target https://your-app.com
```

> [!NOTE]
> First run automatically pulls the sandbox Docker image (~2GB). Results are saved to `strix_runs/<run-name>`

---

## Roo Code Cloud Integration

Roo Code Cloud provides **free access to premium AI models** without requiring API keys or subscriptions. This integration allows you to run powerful penetration tests without any cost barriers.

### Features

- **Zero Configuration** - No API keys to manage or rotate
- **Free Premium Models** - Access to grok-code-fast-1 and code-supernova
- **OAuth Authentication** - Secure login via GitHub, Google, or email
- **Automatic Token Refresh** - Sessions stay active without re-authentication

### Available Models

| Model | Description | Context Window | Best For |
|-------|-------------|----------------|----------|
| `grok-code-fast-1` | Fast coding model | 262,000 tokens | Quick scans, high-speed iterations |
| `roo/code-supernova` | Advanced reasoning model | 200,000 tokens | Complex reasoning, multimodal tasks |

### VSCode Callback URL Authentication

If the browser login redirects to a `vscode://` URL instead of back to the dashboard (which can happen when Roo Code detects you're coming from an IDE context), you can manually authenticate:

1. Copy the full `vscode://RooVeterinaryInc.roo-cline/auth/clerk/callback?...` URL
2. Paste it into the "Paste vscode:// Callback URL" field in the dashboard
3. Click "Authenticate with Callback URL"

The dashboard will extract the authentication token and complete the login process.

### Usage

```bash
# First-time setup: Authenticate with Roo Code Cloud
strix --roocode-login

# Run scans with Roo Code Cloud (uses default model)
strix --roocode --target https://your-app.com

# Specify a particular model
strix --roocode-model grok-code-fast-1 --target ./my-project
strix --roocode-model roo/code-supernova --target https://api.your-app.com

# Log out when done (optional)
strix --roocode-logout
```

### Environment Variables

```bash
# Alternative: Set token manually (for CI/CD environments)
export ROOCODE_ACCESS_TOKEN="your-token-here"

# Enable Roo Code via environment
export STRIX_USE_ROOCODE="true"
export STRIX_LLM="roocode/grok-code-fast-1"
```

### How It Works

1. **Authentication**: When you run `--roocode-login`, Strix opens your browser for OAuth authentication
2. **Token Storage**: Credentials are securely stored in `~/.strix/roocode_config.json` with proper permissions
3. **API Integration**: Strix uses LiteLLM with OpenRouter-compatible endpoints to communicate with Roo Code Cloud
4. **Auto-Refresh**: Tokens are automatically refreshed before expiration

---

## Qwen Code CLI Integration

Qwen Code CLI provides **free access to Alibaba's Qwen AI models** with generous daily limits. This integration is perfect for users who want an alternative to Roo Code Cloud.

### Features

- **2,000 Free Requests/Day** - Generous daily limit for extensive testing
- **Fast Models** - Optimized for code generation and security analysis
- **Multiple Endpoints** - Support for DashScope and ModelScope APIs
- **Easy Setup** - Simple API key configuration

### Available Models

| Model | Description | Context Window | Best For |
|-------|-------------|----------------|----------|
| `qwen3-coder-plus` | High-performance coding model | 262,000 tokens | Complex tasks, multi-step analysis |
| `qwen3-coder` | Balanced coding model | 131,000 tokens | General development, quick iterations |

### Usage

```bash
# Set up Qwen Code API key
export QWENCODE_ACCESS_TOKEN="your-api-key"
export QWENCODE_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"

# Run scans with Qwen Code
strix --qwencode --target https://your-app.com

# Specify a particular model
strix --qwencode-model qwen3-coder-plus --target ./my-project
```

### Getting an API Key

1. Sign up at [Alibaba Cloud DashScope](https://dashscope.aliyun.com/)
2. Navigate to API Keys section
3. Create a new API key
4. Set it as `QWENCODE_ACCESS_TOKEN` environment variable

### Environment Variables

```bash
# Qwen Code CLI Configuration
export QWENCODE_ACCESS_TOKEN="your-api-key"
export QWENCODE_API_BASE="https://dashscope.aliyuncs.com/compatible-mode/v1"

# Alternative: ModelScope endpoint
export QWENCODE_API_BASE="https://api-inference.modelscope.cn/v1"

# Enable via environment
export STRIX_USE_QWENCODE="true"
export STRIX_LLM="qwencode/qwen3-coder-plus"
```

---

## Root Access Mode

Root Access Mode enables **unrestricted terminal access** within the sandboxed Docker container, allowing the AI agent to install tools, modify configurations, and execute privileged commands.

> [!WARNING]
> Root access is contained within the Docker sandbox. Your host system is completely isolated and protected.

### Why Root Access?

During advanced penetration testing, you may need to:
- Install specialized security tools not included in the base image
- Compile custom exploits or tools
- Modify network configurations for specific tests
- Install language-specific packages for PoC development
- Set up custom environments for testing

### Access Levels

| Level | Description | Capabilities |
|-------|-------------|--------------|
| `standard` | Normal user access | Pre-installed tools only |
| `elevated` | Sudo for specific commands | Package installation, tool download |
| `root` | Full unrestricted access | Everything including system modification |

### Usage

```bash
# Enable full root access
strix --root-access --target https://your-app.com

# Or specify access level explicitly
strix --access-level root --target https://your-app.com
strix --access-level elevated --target https://your-app.com
```

### Environment Variables

```bash
# Enable root access via environment
export STRIX_ROOT_ACCESS="true"
export STRIX_ACCESS_LEVEL="root"

# Fine-grained permissions (alternative to full root)
export STRIX_ALLOW_PACKAGE_INSTALL="true"
export STRIX_ALLOW_TOOL_DOWNLOAD="true"
export STRIX_ALLOW_NETWORK_CONFIG="true"
export STRIX_ALLOW_SYSTEM_MOD="true"

# Increase command timeout for package installations
export STRIX_COMMAND_TIMEOUT="600"
```

### What Root Access Enables

```bash
# Package Installation
apt-get install metasploit-framework
pip install custom-exploit-toolkit
npm install -g security-scanner

# Tool Compilation
git clone https://github.com/security/tool
cd tool && make && make install

# Network Configuration
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
ip route add 10.0.0.0/8 via 192.168.1.1

# System Modification
echo "custom config" > /etc/custom.conf
chmod 755 /opt/custom-tool
```

### Security Considerations

1. **Sandboxed Environment**: All commands run inside an isolated Docker container
2. **No Host Access**: The container cannot access your host system
3. **Network Isolation**: Container network is separate from host network
4. **Ephemeral**: Container is destroyed after the scan completes
5. **Audit Trail**: All commands are logged for review

---

## GitHub Actions & Autonomous Dashboard

Strix can run as a fully autonomous bug bounty agent through GitHub Actions, with a powerful web dashboard for configuration and monitoring.

### Key Features

- **Configure and Fire** - Set up once, then let it run autonomously
- **No Interruptions** - Agent runs continuously within your specified timeframe
- **Dashboard Control** - Configure everything through an intuitive web interface
- **Roo Code Integration** - Authenticate and select AI models through the dashboard
- **Real-Time Monitoring** - Watch progress and findings as they happen

### How It Works

1. **Trigger Workflow** - Start the GitHub Actions workflow manually or on schedule
2. **Access Dashboard** - Workflow provides a URL to the configuration dashboard
3. **Configure & Launch** - Set all parameters through the dashboard interface
4. **Autonomous Execution** - Agent runs independently within your timeframe
5. **Review Results** - Access findings and reports when complete

### Quick Setup

1. **Add the workflow file** to your repository (see workflow file below)
2. **Configure secrets** in your GitHub repository settings
3. **Run the workflow** and access the dashboard URL
4. **Configure and fire** - The agent handles the rest

### Required Secrets

| Secret | Description | Required |
|--------|-------------|----------|
| `ROOCODE_ACCESS_TOKEN` | Roo Code Cloud authentication token | Yes (for Roo Code) |
| `STRIX_LLM` | LLM model to use (e.g., `roocode/grok-code-fast-1`) | Yes |
| `LLM_API_KEY` | API key for non-Roo Code providers | If not using Roo Code |
| `PERPLEXITY_API_KEY` | Perplexity API key for web search | Optional |

### Dashboard Configuration Options

The dashboard allows you to configure:

#### Authentication & AI
- **Roo Code Login** - Authenticate with your Roo Code Cloud account
- **VSCode Callback URL** - Alternative authentication method for vscode:// redirects
- **Qwen Code Login** - Authenticate with your Qwen Code CLI account
- **AI Model Selection** - Choose from available Roo Code or Qwen Code models
- **Custom API Keys** - Use your own OpenAI/Anthropic keys if preferred

#### Target Configuration
- **Target URLs** - Web applications to test
- **Repositories** - GitHub repos for source code analysis
- **Local Paths** - Directory paths within the container
- **IP Addresses** - Direct IP targets for network testing

#### Execution Settings
- **Timeframe** - Maximum duration for the autonomous run (configurable in minutes/hours)
- **Root Access** - Enable/disable root access mode
- **Access Level** - standard, elevated, or root
- **Max Iterations** - Limit on agent iterations
- **Rate Limiting** - Control requests per second (1-50 RPS)

#### Agent Behavior
- **Planning Depth** - Quick, balanced, or thorough analysis
- **Memory Strategy** - Minimal, adaptive, or full context retention
- **Multi-Agent Mode** - Enable specialized sub-agents for complex testing
- **Browser Automation** - Enable/disable headless browser testing
- **Proxy Interception** - Enable/disable HTTP traffic capture
- **Attack Chaining** - Automatically chain discovered vulnerabilities
- **Auto-Pivot** - Automatically pivot on findings to discover related issues

#### Testing Parameters
- **Custom Instructions** - Specific guidance for the agent
- **Focus Areas** - Vulnerability types to prioritize
- **Exclusions** - Areas to avoid testing
- **Credentials** - Test account credentials if needed

#### Output Configuration
- **Report Format** - JSON, Markdown, or HTML
- **Severity Threshold** - Minimum severity to report
- **Notification Webhook** - URL for real-time alerts

---

## Configuration

### Environment Variables Reference

#### Core Configuration

```bash
# LLM Configuration
export STRIX_LLM="openai/gpt-5"           # Model name (litellm format)
export LLM_API_KEY="your-api-key"          # API key for LLM provider
export LLM_API_BASE="http://localhost:11434"  # Custom API base (for local models)
export LLM_TIMEOUT="600"                   # Request timeout in seconds

# Roo Code Cloud
export STRIX_USE_ROOCODE="true"            # Enable Roo Code Cloud
export ROOCODE_ACCESS_TOKEN="your-token"   # Manual token (for CI/CD)

# Root Access
export STRIX_ROOT_ACCESS="true"            # Enable full root access
export STRIX_ACCESS_LEVEL="root"           # Access level (standard/elevated/root)
export STRIX_COMMAND_TIMEOUT="300"         # Command timeout in seconds

# Fine-grained Permissions
export STRIX_ALLOW_PACKAGE_INSTALL="true"
export STRIX_ALLOW_TOOL_DOWNLOAD="true"
export STRIX_ALLOW_NETWORK_CONFIG="true"
export STRIX_ALLOW_SYSTEM_MOD="true"

# Web Search (Optional)
export PERPLEXITY_API_KEY="your-key"       # Enable real-time web search
```

### Recommended LLM Models

| Provider | Model | Performance | Cost |
|----------|-------|-------------|------|
| **Roo Code Cloud** | `roocode/grok-code-fast-1` | Excellent | Free |
| **Roo Code Cloud** | `roocode/roo/code-supernova` | Excellent | Free |
| **Qwen Code CLI** | `qwencode/qwen3-coder-plus` | Excellent | Free |
| **Qwen Code CLI** | `qwencode/qwen3-coder` | Good | Free |
| **OpenAI** | `openai/gpt-5` | Excellent | $$$ |
| **Anthropic** | `anthropic/claude-sonnet-4-5` | Excellent | $$$ |
| **Local** | `ollama/llama3:70b` | Good | Free |

---

## Usage Examples

### Basic Scans

```bash
# Web application scan
strix --target https://your-app.com

# GitHub repository analysis
strix --target https://github.com/org/repo

# Local codebase scan
strix --target ./my-project

# IP address scan
strix --target 192.168.1.100
```

### Advanced Scenarios

```bash
# Multi-target white-box testing
strix -t https://github.com/org/app -t https://staging.app.com -t https://prod.app.com

# Authenticated testing
strix --target https://app.com --instruction "Use credentials admin:password123 for authenticated testing"

# Focus on specific vulnerabilities
strix --target https://api.app.com --instruction "Focus on IDOR, authentication bypass, and API rate limiting"

# Detailed instructions from file
strix --target https://app.com --instruction-file ./pentest-scope.md

# Full autonomous mode with root access
strix --roocode --root-access --target https://app.com --instruction "Comprehensive bug bounty assessment"
```

### Headless/CI Mode

```bash
# Non-interactive mode (for CI/CD)
strix -n --target https://your-app.com

# With custom run name
strix -n --run-name "weekly-security-scan" --target https://your-app.com
```

---

## Architecture

### System Overview

```
                                    +------------------+
                                    |   Strix CLI/TUI  |
                                    +--------+---------+
                                             |
                    +------------------------+------------------------+
                    |                                                 |
            +-------v-------+                                +--------v--------+
            |  LLM Manager  |                                | Runtime Manager |
            | (LiteLLM)     |                                | (Docker)        |
            +-------+-------+                                +--------+--------+
                    |                                                 |
    +---------------+---------------+                    +------------+------------+
    |               |               |                    |                         |
+---v---+       +---v---+       +---v---+          +-----v-----+            +------v------+
|OpenAI |       |Anthrop|       |RooCode|          |  Sandbox  |            |  Tool       |
|       |       |ic     |       |Cloud  |          |  Container|            |  Server     |
+-------+       +-------+       +-------+          +-----------+            +-------------+
                                                         |
                              +----------+----------+----+----+----------+----------+
                              |          |          |         |          |          |
                          +---v---+  +---v---+  +---v---+ +---v---+  +---v---+  +---v---+
                          |Browser|  |Terminal| |Python | | Proxy |  | Notes |  |Search |
                          |Tool   |  |Tool    | |Tool   | | Tool  |  | Tool  |  |Tool   |
                          +-------+  +--------+ +-------+ +-------+  +-------+  +-------+
```

### Multi-Agent Architecture

```
                              +------------------+
                              |   Root Agent     |
                              | (Coordinator)    |
                              +--------+---------+
                                       |
          +----------------------------+----------------------------+
          |                            |                            |
+---------v----------+     +-----------v-----------+    +-----------v-----------+
|  Reconnaissance    |     |   Vulnerability       |    |   Exploitation        |
|  Agent             |     |   Scanner Agent       |    |   Agent               |
+--------------------+     +-----------------------+    +-----------------------+
          |                            |                            |
    +-----+-----+              +-------+-------+             +------+------+
    |           |              |               |             |             |
+---v---+   +---v---+      +---v---+       +---v---+     +---v---+     +---v---+
|Subdomain  |Port   |      |OWASP  |       |Custom |     |PoC    |     |Report |
|Enum Agent |Scan   |      |Check  |       |Logic  |     |Builder|     |Gen    |
+-----------+-------+      +-------+       +-------+     +-------+     +-------+
```

### Component Details

#### LLM Manager
- Handles all AI model communications
- Supports multiple providers through LiteLLM
- Manages Roo Code Cloud authentication
- Implements retry logic and error handling

#### Runtime Manager
- Creates and manages Docker sandboxes
- Handles file mounting and networking
- Provides root access when enabled
- Ensures security isolation

#### Tool Server
- Runs inside the sandbox container
- Provides API endpoints for all tools
- Manages browser instances, terminals, proxies
- Handles file operations and code execution

---

## Tools & Capabilities

For a complete reference of all available tools, see [Treasury.md](Treasury.md).

### Quick Reference

| Tool Category | Tools | Description |
|---------------|-------|-------------|
| **Terminal** | `terminal_execute`, `terminal_get_root_status` | Command execution with optional root access |
| **Browser** | `browser_action` | Multi-tab browser automation for web testing |
| **HTTP Proxy** | `list_requests`, `send_request`, `repeat_request`, `scope_rules` | Full HTTP interception and modification |
| **Python** | `python_action` | Python runtime for custom exploit development |
| **File System** | `str_replace_editor`, `list_files`, `search_files` | File viewing, editing, and searching |
| **Notes** | `create_note`, `list_notes`, `update_note` | Knowledge management during testing |
| **Reporting** | `create_vulnerability_report` | Structured vulnerability documentation |
| **Web Search** | `web_search` | Real-time intelligence with Perplexity AI |
| **Agent Graph** | `create_agent`, `view_agent_graph`, `send_message_to_agent` | Multi-agent orchestration |
| **Finish** | `finish_scan`, `agent_finish` | Proper scan completion and reporting |

---

## Multi-Agent System

### Agent Types

#### Root Agent
The main coordinator that orchestrates the entire penetration test. It:
- Analyzes targets and creates a testing strategy
- Delegates specialized tasks to sub-agents
- Monitors progress and collects findings
- Generates the final report

#### Sub-Agents
Specialized agents created for specific tasks:
- **Reconnaissance Agent**: Attack surface mapping, subdomain enumeration
- **Vulnerability Scanner**: Systematic vulnerability testing
- **Exploitation Agent**: PoC development and validation
- **Custom Agents**: User-defined specialists with specific prompt modules

### Creating Custom Agents

```python
# The root agent can create specialized sub-agents:
create_agent(
    task="Focus on SQL injection testing in the /api/* endpoints",
    name="SQL Injection Specialist",
    inherit_context=True,
    prompt_modules="vulnerabilities/sqli"
)
```

### Inter-Agent Communication

Agents can communicate and share findings:
```python
# Send findings to another agent
send_message_to_agent(
    target_agent_id="agent_123",
    message="Found SQLi in /api/users endpoint",
    message_type="information",
    priority="high"
)
```

---

## CI/CD Integration

### GitHub Actions (Basic)

```yaml
name: strix-penetration-test

on:
  pull_request:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Install Strix
        run: pipx install strix-agent

      - name: Run Strix
        env:
          STRIX_LLM: ${{ secrets.STRIX_LLM }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
        run: strix -n -t ./
```

### GitLab CI

```yaml
security_scan:
  stage: test
  image: python:3.12
  services:
    - docker:dind
  before_script:
    - pip install strix-agent
  script:
    - strix -n -t ./
  variables:
    STRIX_LLM: $STRIX_LLM
    LLM_API_KEY: $LLM_API_KEY
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    environment {
        STRIX_LLM = credentials('strix-llm')
        LLM_API_KEY = credentials('llm-api-key')
    }
    
    stages {
        stage('Security Scan') {
            steps {
                sh 'pip install strix-agent'
                sh 'strix -n -t ./'
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'strix_runs/**/*', fingerprint: true
        }
    }
}
```

---

## Run Strix in Cloud

Skip local setup entirely with the hosted cloud version at **[app.usestrix.com](https://usestrix.com)**.

### Cloud Features

- **Instant Setup** - No installation, API keys, or configuration required
- **Full Pentest Reports** - Professional reports with validated findings
- **Shareable Dashboards** - Team collaboration and fix tracking
- **GitHub Integration** - Automatic PR comments and status checks
- **Continuous Monitoring** - Scheduled scans and vulnerability alerts

[**Launch Your First Cloud Scan**](https://usestrix.com)

---

## Contributing

We welcome contributions of all kinds:

- **Code** - New features, bug fixes, optimizations
- **Documentation** - Improve guides, add examples
- **Prompt Modules** - Create specialized testing prompts
- **Tools** - Add new security testing capabilities

See our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/usestrix/strix.git
cd strix

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run linting
poetry run ruff check .
poetry run mypy strix/
```

---

## Join Our Community

- **[Discord](https://discord.gg/YjKFvEZSdZ)** - Chat with maintainers and users
- **[GitHub Discussions](https://github.com/usestrix/strix/discussions)** - Feature requests, Q&A
- **[GitHub Issues](https://github.com/usestrix/strix/issues)** - Bug reports

---

## Support the Project

Love Strix? Help us grow!

- Star the repository on GitHub
- Share with your security team
- Write about your experience
- Contribute to the codebase

---

## Acknowledgements

Strix builds on incredible open-source projects:

- [LiteLLM](https://github.com/BerriAI/litellm) - Universal LLM API
- [Caido](https://github.com/caido/caido) - HTTP proxy inspiration
- [ProjectDiscovery](https://github.com/projectdiscovery) - Security tools
- [Playwright](https://github.com/microsoft/playwright) - Browser automation
- [Textual](https://github.com/Textualize/textual) - Terminal UI framework

---

> [!WARNING]
> **Legal Notice**: Only test applications you own or have explicit written permission to test. You are solely responsible for ensuring your use of Strix complies with all applicable laws and regulations. Unauthorized testing is illegal and unethical.

---

<div align="center">

**[Website](https://usestrix.com)** | **[Documentation](https://docs.usestrix.com)** | **[Discord](https://discord.gg/YjKFvEZSdZ)** | **[Twitter](https://twitter.com/usestrix)**

</div>
