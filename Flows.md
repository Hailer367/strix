# Strix GitHub Actions Workflows

This document describes the available GitHub Actions workflows for automating Strix penetration testing and bug bounty operations.

## Table of Contents

- [Overview](#overview)
- [Quick Setup](#quick-setup)
- [Workflows](#workflows)
  - [Strix Autonomous Dashboard](#1-strix-autonomous-dashboard)
  - [Strix Quick Scan](#2-strix-quick-scan)
  - [Strix Scheduled Scan](#3-strix-scheduled-scan)
  - [Strix PR Security Scan](#4-strix-pr-security-scan)
- [Configuration](#configuration)
- [Roo Code Authentication](#roo-code-authentication)
- [Troubleshooting](#troubleshooting)

---

## Overview

Strix provides four GitHub Actions workflows for different use cases:

| Workflow | Use Case | Trigger | Dashboard |
|----------|----------|---------|-----------|
| **Autonomous Dashboard** | Full-featured scans with web UI | Manual | ✅ Yes |
| **Quick Scan** | Fast, targeted scans | Manual | ❌ No |
| **Scheduled Scan** | Automated recurring scans | Schedule/Manual | ❌ No |
| **PR Security Scan** | Code review integration | Pull Request | ❌ No |

All workflows use **Roo Code Cloud** for AI-powered analysis - no API keys needed, just authenticate once!

---

## Quick Setup

### 1. Get Your Roo Code Token

```bash
# Option A: Using Strix CLI
pip install strix-agent
strix --roocode-login

# Your token is saved in ~/.strix/roocode_config.json
cat ~/.strix/roocode_config.json | jq -r '.access_token'
```

Or login through the dashboard when you run the workflow.

### 2. Add Repository Secret

1. Go to your repository's **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `ROOCODE_ACCESS_TOKEN`
4. Value: Your Roo Code access token

### 3. Copy Workflows

The workflow files are located in `.github/workflows/`:

```
.github/workflows/
├── strix-dashboard.yml      # Full dashboard experience
├── strix-quick-scan.yml     # Quick targeted scans
├── strix-scheduled-scan.yml # Automated recurring scans
└── strix-pr-scan.yml        # Pull request security checks
```

---

## Workflows

### 1. Strix Autonomous Dashboard

**File:** `.github/workflows/strix-dashboard.yml`

The flagship workflow that provides a web-based dashboard for configuring and launching autonomous bug bounty scans.

#### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Actions Runner                         │
│                                                                  │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐ │
│  │   Dashboard   │───▶│  Cloudflare   │───▶│  Your Browser    │ │
│  │   Server      │    │  Tunnel       │    │                  │ │
│  └──────────────┘    └───────────────┘    └──────────────────┘ │
│         │                                          │            │
│         │         Configure & Fire                 │            │
│         │◀─────────────────────────────────────────┘            │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ Strix Agent  │ ──▶ Autonomous Penetration Testing            │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

#### Usage

1. Go to **Actions** → **Strix Autonomous Dashboard** → **Run workflow**
2. Configure options (duration, root access, debug mode)
3. Click **Run workflow**
4. Wait for the dashboard URL to appear in the logs
5. Open the URL in your browser
6. **Login with Roo Code** - Click the login button and authenticate
7. Configure your target and scan settings
8. Click **Configure and Fire**
9. The agent runs autonomously until completion

#### Workflow Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `duration_hours` | Maximum scan duration | 2 hours |
| `enable_root_access` | Allow unrestricted terminal commands | true |
| `debug_mode` | Enable verbose logging | false |

#### Dashboard Features

- **Roo Code Login** - Browser-based OAuth authentication
- **Model Selection** - Choose between Grok Code Fast 1 and Code Supernova
- **Target Configuration** - URLs, repositories, IP addresses
- **Access Control** - Root, elevated, or standard access
- **Agent Behavior** - Planning depth, memory strategy, capabilities
- **Focus Areas** - Select vulnerability types to prioritize
- **Output Configuration** - Report format, severity threshold, webhooks

---

### 2. Strix Quick Scan

**File:** `.github/workflows/strix-quick-scan.yml`

Fast, targeted scans without the dashboard UI. Configuration is provided directly through workflow inputs.

#### Usage

1. Go to **Actions** → **Strix Quick Scan** → **Run workflow**
2. Enter your target URL or repository
3. (Optional) Add custom instructions
4. Select model and access level
5. Click **Run workflow**

#### Workflow Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `target` | Target URL, repo, or path | ✅ | - |
| `instructions` | Custom agent instructions | ❌ | - |
| `model` | AI model selection | ❌ | grok-code-fast-1 |
| `access_level` | Terminal access level | ❌ | root |
| `duration_minutes` | Max scan duration | ❌ | 60 |
| `max_iterations` | Max agent iterations | ❌ | 300 |

#### Example: Scan a Web Application

```yaml
# Trigger via GitHub UI with:
target: https://vulnerable-app.example.com
instructions: "Focus on authentication bypass and IDOR vulnerabilities"
model: grok-code-fast-1
access_level: root
duration_minutes: 120
```

---

### 3. Strix Scheduled Scan

**File:** `.github/workflows/strix-scheduled-scan.yml`

Automated recurring security scans. Configure targets through repository variables.

#### Setup

1. Add repository variables (Settings → Secrets and variables → Actions → Variables):

| Variable | Description | Example |
|----------|-------------|---------|
| `STRIX_TARGET` | Target URL(s), comma-separated | `https://app.example.com,https://api.example.com` |
| `STRIX_MODEL` | AI model to use | `grok-code-fast-1` |

2. (Optional) Add `SLACK_WEBHOOK_URL` secret for notifications

#### Default Schedule

Runs every **Sunday at 2 AM UTC**. Modify the cron expression in the workflow file to change:

```yaml
on:
  schedule:
    - cron: '0 2 * * 0'  # Sunday at 2 AM UTC
    # Examples:
    # '0 0 * * *'   - Daily at midnight
    # '0 */6 * * *' - Every 6 hours
    # '0 0 * * 1'   - Every Monday
```

#### Features

- **Multiple Targets** - Comma-separated URLs in `STRIX_TARGET`
- **Slack Notifications** - Start and completion alerts
- **Result Artifacts** - 90-day retention
- **Failure on Critical** - Blocks workflow if critical vulnerabilities found

---

### 4. Strix PR Security Scan

**File:** `.github/workflows/strix-pr-scan.yml`

Automatic security analysis for pull requests. Posts findings as PR comments.

#### How It Works

1. Developer opens/updates a pull request
2. Workflow automatically triggers
3. Strix analyzes changed files
4. Findings posted as PR comment
5. PR blocked if critical issues found

#### Features

- **Targeted Analysis** - Only scans changed files
- **PR Comments** - Inline findings with details
- **Staging Testing** - Optional deployed environment scan
- **Merge Blocking** - Prevents merge on critical findings

#### Optional: Staging Environment

Set the `STRIX_STAGING_URL` variable to enable staging environment testing:

```
Settings → Variables → STRIX_STAGING_URL → https://staging.example.com
```

#### PR Comment Example

```markdown
## 🦉 Strix Security Scan Results

⚠️ **Status:** Issues Found

| Metric | Count |
|--------|-------|
| Total Findings | 3 |
| Critical | 0 |
| High | 2 |

### Files Analyzed
- src/auth/login.py
- src/api/users.py

<details>
<summary>📄 Detailed Findings</summary>
...
</details>
```

---

## Configuration

### Required Secrets

| Secret | Description | Required For |
|--------|-------------|--------------|
| `ROOCODE_ACCESS_TOKEN` | Roo Code authentication | All workflows |
| `PERPLEXITY_API_KEY` | Web search capabilities | Optional |
| `SLACK_WEBHOOK_URL` | Slack notifications | Scheduled scans |

### Repository Variables

| Variable | Description | Used By |
|----------|-------------|---------|
| `STRIX_TARGET` | Default scan target | Scheduled |
| `STRIX_MODEL` | Default AI model | Scheduled |
| `STRIX_STAGING_URL` | Staging environment URL | PR Scan |

---

## Roo Code Authentication

### Option 1: Dashboard Login (Recommended)

When using the Dashboard workflow:
1. Click **Login with Roo Code** button
2. Authenticate via GitHub, Google, or email
3. Authorization is automatic - no token copy/paste needed!

### Option 2: CLI Token

```bash
# Install Strix
pip install strix-agent

# Login and get token
strix --roocode-login

# View token
cat ~/.strix/roocode_config.json | jq -r '.access_token'

# Add to GitHub Secrets
# Settings → Secrets → New → ROOCODE_ACCESS_TOKEN
```

### Option 3: Environment Token

For existing Roo Code users, you can use your token directly:

```bash
# Set in GitHub Secrets
ROOCODE_ACCESS_TOKEN=your-existing-token
```

### Token Refresh

Tokens are automatically refreshed. If authentication fails:
1. Re-run `strix --roocode-login`
2. Update the `ROOCODE_ACCESS_TOKEN` secret

---

## Troubleshooting

### Dashboard URL Not Appearing

**Symptom:** Workflow runs but no URL is shown

**Solutions:**
1. Check the "Setup Cloudflare Tunnel" step logs
2. Ensure the runner has internet access
3. Try re-running the workflow

### Authentication Failed

**Symptom:** "Not authenticated" error

**Solutions:**
1. Verify `ROOCODE_ACCESS_TOKEN` secret is set
2. Check token hasn't expired (re-run `strix --roocode-login`)
3. Use dashboard login as fallback

### Scan Timeout

**Symptom:** Scan terminates early

**Solutions:**
1. Increase `duration_hours` or `duration_minutes`
2. Use `max_iterations` to limit agent steps
3. Add focused instructions to narrow scope

### No Findings

**Symptom:** Scan completes but finds nothing

**Solutions:**
1. Verify target is accessible from GitHub runners
2. Check access level is appropriate for testing
3. Try enabling `aggressive_mode` for deeper analysis

### Docker Errors

**Symptom:** Container fails to start

**Solutions:**
1. Check runner has Docker installed and running
2. Verify disk space is sufficient (~2GB for image)
3. Review Docker logs in workflow output

---

## Best Practices

### Security

- Store all secrets in GitHub Secrets, never in code
- Use PR scanning for continuous security validation
- Review findings before merging to main branch

### Performance

- Start with shorter scans, increase as needed
- Use focused instructions for targeted testing
- Schedule intensive scans during off-hours

### Monitoring

- Enable Slack notifications for scheduled scans
- Review artifacts after each scan
- Track vulnerability trends over time

---

## Support

- **Documentation:** [docs.usestrix.com](https://docs.usestrix.com)
- **Issues:** [github.com/usestrix/strix/issues](https://github.com/usestrix/strix/issues)
- **Discord:** [discord.gg/YjKFvEZSdZ](https://discord.gg/YjKFvEZSdZ)

---

*Strix - AI-Powered Penetration Testing*
