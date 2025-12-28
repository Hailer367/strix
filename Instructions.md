# 📚 Strix Complete Usage Instructions

This comprehensive guide covers all features of Strix, the AI-powered security testing tool. It includes setup instructions, configuration options, workflow methods, and advanced features.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation Methods](#installation-methods)
3. [Configuration](#configuration)
   - [Config.json Setup](#configjson-setup)
   - [Environment Variables](#environment-variables)
   - [GitHub Secrets Setup](#github-secrets-setup)
4. [Running Strix](#running-strix)
   - [CLI Usage](#cli-usage)
   - [GitHub Actions Workflow](#github-actions-workflow)
5. [Features Guide](#features-guide)
   - [Expandable Toolkit](#expandable-toolkit)
   - [StrixDB - Knowledge Repository](#strixdb---knowledge-repository)
   - [Web Search Capabilities](#web-search-capabilities)
   - [Root Terminal Access](#root-terminal-access)
   - [Multi-Agent System](#multi-agent-system)
   - [CVE Database Integration](#cve-database-integration)
6. [GitHub Actions Workflows](#github-actions-workflows)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# Install Strix
pip install strix-agent

# Or use pipx (recommended)
pipx install strix-agent

# Run a basic scan
strix --target ./your-app
```

---

## Installation Methods

### Method 1: pip/pipx (Recommended)

```bash
# Using pip
pip install strix-agent

# Using pipx (isolated environment)
pipx install strix-agent

# Verify installation
strix --version
```

### Method 2: Install Script

```bash
curl -sSL https://strix.ai/install | bash
```

### Method 3: From Source

```bash
git clone https://github.com/usestrix/strix.git
cd strix
pip install poetry
poetry install
poetry run strix --version
```

### Method 4: Docker (Coming Soon)

```bash
docker run -it usestrix/strix --target ./app
```

---

## Configuration

### Config.json Setup

Strix uses a `config.json` file for all configuration. Create this file in your project root:

```json
{
  "api": {
    "endpoint": "http://localhost:8317/v1",
    "model": "gemini-2.5-pro",
    "api_key": ""
  },
  "timeframe": {
    "duration_minutes": 60,
    "warning_minutes": 5,
    "time_awareness_enabled": true
  },
  "dashboard": {
    "enabled": true,
    "refresh_interval": 1.0,
    "show_time_remaining": true,
    "show_agent_details": true,
    "show_tool_logs": true,
    "show_resource_usage": true
  },
  "scan_mode": "deep",
  "strixdb": {
    "enabled": true,
    "token": ""
  }
}
```

#### Configuration Options Explained

| Field | Description | Default |
|-------|-------------|---------|
| `api.endpoint` | LLM API endpoint URL | Required |
| `api.model` | Model to use | `gemini-2.5-pro` |
| `api.api_key` | API key (if not using OAuth) | Optional |
| `timeframe.duration_minutes` | Session duration (10-720 min) | 60 |
| `timeframe.warning_minutes` | Warning before end (1-30 min) | 5 |
| `scan_mode` | Scan depth: `quick`, `standard`, `deep` | `deep` |
| `strixdb.enabled` | Enable StrixDB artifact storage | false |
| `strixdb.token` | GitHub PAT for StrixDB access | Optional |

### Environment Variables

For CLI usage without config.json:

```bash
# Required: LLM Configuration
export STRIX_LLM="openai/gpt-5"           # or gemini-2.5-pro, claude-sonnet-4
export LLM_API_KEY="your-api-key"         # Your API key
export LLM_API_BASE="https://api.openai.com/v1"  # Optional: custom endpoint

# Optional: CLIProxyAPI (recommended)
export CLIPROXY_ENABLED="true"
export CLIPROXY_BASE_URL="http://localhost:8317/v1"

# Optional: StrixDB
export STRIXDB_TOKEN="ghp_xxxxxxxxxxxx"   # GitHub PAT with repo access

# Optional: Web Search Providers (in order of preference)
export PERPLEXITY_API_KEY="pplx-xxxxxxxx"      # Best for security research
export TAVILY_API_KEY="tvly-xxxxxxxx"          # Good general search
export SERPAPI_API_KEY="serpapi-xxxxxxxx"      # Google search results
export GOOGLE_CSE_API_KEY="your-google-key"    # Google Custom Search
export GOOGLE_CSE_ID="your-cse-id"             # Custom Search Engine ID
export BRAVE_API_KEY="BSAxxxxxxxx"             # Brave Search API
# Note: DuckDuckGo is always available (free, no API key required)
```

### GitHub Secrets Setup

For GitHub Actions workflows, you need to configure repository secrets:

#### Step 1: Navigate to Repository Settings

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

#### Step 2: Add Required Secrets

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `CLIPROXY_ENDPOINT` | Yes | CLIProxyAPI endpoint (e.g., `http://localhost:8317/v1`) |
| `STRIX_MODEL` | Yes | Model name (e.g., `gemini-2.5-pro`) |
| `LLM_API_KEY` | Sometimes | API key (not needed for OAuth mode) |
| `STRIXDB_TOKEN` | For StrixDB | GitHub PAT with `repo` scope |
| `PERPLEXITY_API_KEY` | Optional | Perplexity API key for best search |
| `TAVILY_API_KEY` | Optional | Tavily API key for search |
| `SERPAPI_API_KEY` | Optional | SerpAPI key for Google results |
| `BRAVE_API_KEY` | Optional | Brave Search API key |

#### Step 3: Create GitHub Personal Access Token (PAT) for StrixDB

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click **Generate new token (classic)**
3. Select scopes:
   - ✅ `repo` (Full control of private repositories)
4. Generate and copy the token
5. Add as `STRIXDB_TOKEN` secret in your repository

#### Step 4: Create StrixDB Repository

1. Create a new **private** repository named `StrixDB`
2. Initialize with a README
3. The repository structure will be created automatically by Strix

---

## Running Strix

### CLI Usage

#### Basic Commands

```bash
# Scan a local directory
strix --target ./app-directory

# Scan a GitHub repository
strix --target https://github.com/org/repo

# Scan a web application
strix --target https://your-app.com

# Scan with custom instructions
strix --target ./app --instruction "Focus on authentication bypass"

# Scan with instructions from file
strix --target ./app --instruction-file ./rules.md
```

#### Advanced Options

```bash
# Set scan mode
strix --target ./app --scan-mode deep    # deep, standard, or quick

# Non-interactive mode (for CI/CD)
strix -n --target ./app

# Multiple targets
strix -t https://github.com/org/app -t https://app.com

# Grey-box testing with credentials
strix --target https://app.com --instruction "Use credentials admin:password"
```

### GitHub Actions Workflow

#### Method 1: Manual Trigger (Full Control)

Create `.github/workflows/strix-scan.yml`:

```yaml
name: Strix Security Scan

on:
  workflow_dispatch:
    inputs:
      target:
        description: 'Target to scan'
        required: true
        default: './'
        type: string
      prompt:
        description: 'Custom instructions for AI'
        required: false
        type: string
      timeframe:
        description: 'Max runtime in minutes'
        required: false
        default: '60'
        type: choice
        options: ['10', '15', '30', '60', '120', '240', '480', '720']
      scan_mode:
        description: 'Scan mode'
        required: false
        default: 'deep'
        type: choice
        options: ['quick', 'standard', 'deep']
      enable_strixdb:
        description: 'Enable StrixDB storage'
        required: false
        default: true
        type: boolean

jobs:
  security-scan:
    runs-on: ubuntu-latest
    timeout-minutes: ${{ fromJSON(github.event.inputs.timeframe || '120') }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Strix
        run: pip install strix-agent
      
      - name: Create config.json
        run: |
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ secrets.CLIPROXY_ENDPOINT }}",
              "model": "${{ secrets.STRIX_MODEL || 'gemini-2.5-pro' }}"
            },
            "timeframe": {
              "duration_minutes": ${{ github.event.inputs.timeframe || 60 }},
              "warning_minutes": 5,
              "time_awareness_enabled": true
            },
            "scan_mode": "${{ github.event.inputs.scan_mode || 'deep' }}",
            "strixdb": {
              "enabled": ${{ github.event.inputs.enable_strixdb || false }},
              "token": "${{ secrets.STRIXDB_TOKEN }}"
            }
          }
          EOF
      
      - name: Run Strix Scan
        env:
          STRIXDB_TOKEN: ${{ secrets.STRIXDB_TOKEN }}
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          strix -n \
            --target "${{ github.event.inputs.target || './' }}" \
            --scan-mode "${{ github.event.inputs.scan_mode || 'deep' }}" \
            --instruction "${{ github.event.inputs.prompt }}"
      
      - name: Upload Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: strix-results-${{ github.run_id }}
          path: strix_runs/
          retention-days: 30
```

#### Method 2: Pull Request Trigger (CI/CD Gate)

```yaml
name: Strix PR Security Check

on:
  pull_request:
    branches: [main, master]

jobs:
  security-gate:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - run: pip install strix-agent
      
      - name: Quick Security Scan
        env:
          STRIX_LLM: ${{ secrets.STRIX_MODEL }}
          LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
        run: |
          strix -n -t ./ --scan-mode quick \
            --instruction "Quick PR review. Focus on critical vulnerabilities in changed files."
      
      - name: Upload Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: pr-security-scan
          path: strix_runs/
```

#### Method 3: Scheduled Deep Audit

```yaml
name: Weekly Security Audit

on:
  schedule:
    - cron: '0 2 * * 1'  # Every Monday at 2 AM

jobs:
  weekly-audit:
    runs-on: ubuntu-latest
    timeout-minutes: 480  # 8 hours
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - run: pip install strix-agent
      
      - name: Run Deep Security Audit
        env:
          STRIXDB_TOKEN: ${{ secrets.STRIXDB_TOKEN }}
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ secrets.CLIPROXY_ENDPOINT }}",
              "model": "gemini-2.5-pro"
            },
            "timeframe": {
              "duration_minutes": 420,
              "warning_minutes": 20,
              "time_awareness_enabled": true
            },
            "scan_mode": "deep",
            "strixdb": {
              "enabled": true,
              "token": "${{ secrets.STRIXDB_TOKEN }}"
            }
          }
          EOF
          
          strix -n -t ./ --scan-mode deep \
            --instruction "Comprehensive weekly security audit. Store all findings in StrixDB."
```

---

## Features Guide

### Expandable Toolkit

**IMPORTANT**: The AI agent has **full root/sudo access** and can install ANY tools it needs!

The pre-installed tools are just defaults. The AI can:

```bash
# Install system packages
sudo apt-get install -y nmap masscan nikto gobuster

# Install Python tools
pip install sqlmap dirsearch wfuzz jwt-tool pwntools

# Install Node.js tools
npm install -g @apidevtools/swagger-parser

# Install Go tools
go install github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest

# Compile from source
git clone https://github.com/some/tool.git && cd tool && make
```

The AI should **never say "I don't have a tool for this"** - it should install what it needs!

### StrixDB - Knowledge Repository

StrixDB is a permanent GitHub-based storage where the AI stores useful artifacts:

#### Setup

1. Create a private repository named `StrixDB` on GitHub
2. Generate a PAT with `repo` scope
3. Add as `STRIXDB_TOKEN` secret

#### Categories

| Category | Description |
|----------|-------------|
| `scripts` | Automation scripts and utilities |
| `exploits` | Working exploits and PoCs |
| `knowledge` | Security research and notes |
| `libraries` | Reusable code modules |
| `sources` | Wordlists and data sources |
| `methods` | Attack methodologies |
| `tools` | Custom security tools |
| `configs` | Configuration templates |
| `wordlists` | Custom fuzzing wordlists |
| `payloads` | Attack payloads |
| `templates` | Report templates |
| `notes` | Quick notes |

#### Creating Custom Categories

The AI can create new categories dynamically:

```python
strixdb_create_category("mobile_exploits", "Exploits for mobile applications")
```

#### Available Functions

```python
# Save an item
strixdb_save(category, name, content, description, tags)

# Search items
strixdb_search(query, category=None, tags=None)

# Get specific item
strixdb_get(category, name)

# List items
strixdb_list(category=None)

# Create new category
strixdb_create_category(name, description)

# Get all categories
strixdb_get_categories()

# Export all items
strixdb_export(category=None, format="json")
```

### Web Search Capabilities

Strix supports multiple search providers with automatic fallback:

| Provider | Quality | Cost | API Key Required |
|----------|---------|------|------------------|
| Perplexity AI | Excellent | Paid | `PERPLEXITY_API_KEY` |
| Tavily AI | Very Good | Freemium | `TAVILY_API_KEY` |
| SerpAPI | Very Good | Paid | `SERPAPI_API_KEY` |
| Google CSE | Very Good | Freemium | `GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID` |
| Brave Search | Good | Freemium | `BRAVE_API_KEY` |
| DuckDuckGo | Basic | **Free** | **None (always available)** |

**Usage:**

```python
# Auto-select best available provider
web_search("CVE-2024-1234 exploit POC")

# Use specific provider
web_search("nginx vulnerabilities", provider="perplexity")

# List available providers
list_search_providers()
```

### Root Terminal Access

The AI has full root access with multiple concurrent terminals:

```python
# Execute commands with root
root_execute("apt-get update && apt-get install -y nmap")

# Create additional terminals (up to 7)
create_root_terminal("exploit_testing")

# Install packages
install_package("nmap masscan")
install_pip_package("sqlmap pwntools")
install_npm_package("@apidevtools/swagger-parser")

# Run scripts
run_script("/path/to/exploit.py", "--target 10.0.0.1")

# Create databases
create_database("postgresql", "test_db", "admin", "password")

# Manage services
manage_service("postgresql", "start")
```

### Multi-Agent System

Strix uses a coordinated multi-agent architecture:

#### Agent Types

- **Coordinator Agent**: Orchestrates all sub-agents
- **Reconnaissance Agents**: Subdomain enum, port scanning
- **Vulnerability Agents**: SQLi, XSS, IDOR testing
- **Validation Agents**: Verify findings
- **Reporting Agents**: Document findings

#### Creating Custom Agents

```python
create_custom_agent(
    task="Test for SQL injection in /api/users",
    name="SQLi Tester",
    root_access=True,
    priority="high",
    capabilities=["root_terminal", "browser", "proxy"]
)
```

### CVE Database Integration

Query vulnerability databases directly:

```python
# Query NVD for CVEs
query_cve_database("nginx", version="1.18.0")

# Search Exploit-DB
search_exploitdb("apache struts")

# Get comprehensive vulnerability data
get_technology_vulnerabilities("wordpress", version="5.8.0")

# Get CVE details
get_cve_details("CVE-2024-1234")
```

---

## GitHub Actions Workflows

See [Flows.md](Flows.md) for complete workflow templates including:

1. **Full-Featured Workflow** - All configuration options
2. **Quick Scan Workflow** - PR security gates
3. **Scheduled Audit** - Weekly deep scans
4. **Manual Pentest** - On-demand testing
5. **StrixDB Sync** - Artifact management

---

## Troubleshooting

### Common Issues

#### "StrixDB not configured"

**Solution:** Ensure `STRIXDB_TOKEN` is set as a repository secret and passed to the workflow.

```yaml
env:
  STRIXDB_TOKEN: ${{ secrets.STRIXDB_TOKEN }}
```

#### "No search providers available"

**Solution:** DuckDuckGo should always work. If you want better results, add API keys for premium providers.

#### "LLM API request failed"

**Solution:** Check your API endpoint and key. For CLIProxyAPI:
1. Ensure CLIProxyAPI is running
2. Check the endpoint URL is correct
3. Verify OAuth is configured

#### "Scan timed out"

**Solution:** Increase the timeframe in config.json:

```json
{
  "timeframe": {
    "duration_minutes": 120
  }
}
```

#### "Tool not found"

**Solution:** Remember, the AI can install any tool! Use:
```python
install_package("tool-name")
# or
install_pip_package("python-tool")
```

### Getting Help

- **Discord**: [Join our community](https://discord.gg/YjKFvEZSdZ)
- **Issues**: [GitHub Issues](https://github.com/usestrix/strix/issues)
- **Documentation**: [usestrix.com](https://usestrix.com)

---

## Quick Reference

### Timeframe Recommendations

| Duration | Use Case |
|----------|----------|
| 10-15 min | Quick CI checks |
| 30-60 min | Standard scans |
| 2-4 hours | Deep audits |
| 8-12 hours | Extended pentests |

### Scan Modes

| Mode | Description |
|------|-------------|
| `quick` | Fast scan for critical issues only |
| `standard` | Balanced coverage and speed |
| `deep` | Comprehensive testing |

### Environment Variables Summary

```bash
# LLM (Required)
STRIX_LLM=gemini-2.5-pro
LLM_API_KEY=your-key
LLM_API_BASE=https://api.example.com/v1

# StrixDB (Optional)
STRIXDB_TOKEN=ghp_xxxxx

# Search Providers (Optional, in order of preference)
PERPLEXITY_API_KEY=pplx-xxxxx
TAVILY_API_KEY=tvly-xxxxx
SERPAPI_API_KEY=xxxxx
GOOGLE_CSE_API_KEY=xxxxx
GOOGLE_CSE_ID=xxxxx
BRAVE_API_KEY=BSAxxxxx
# DuckDuckGo: Always available, no key needed
```

---

*Last updated: December 2024*
*Version: 0.5.0 Enhanced Edition*
