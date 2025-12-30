# Strix GitHub Actions Workflows

This document contains GitHub Actions workflow configurations for running Strix automatically. Copy the desired workflow to `.github/workflows/` in your repository.

> **🆕 NEW IN THIS VERSION:**
> - **CLIProxyAPI Support**: Use `CLIPROXY_ENDPOINT` instead of API keys - no API_KEY required!
> - **Continuous Scanning**: Workflow continues finding vulnerabilities until timeframe exhausted (doesn't stop on first find)
> - **Live Dashboard**: Real-time vulnerability disclosure and API call counter
> - **Multi-Action Mode**: AI can do up to 7 actions per API call for efficiency
> - **Active Commander**: Main agent now actively participates in security testing (not just coordination)
> - **Custom Strix Install**: Installs from Hailer367/strix repository (enhanced version)

---

## Table of Contents

1. [Configuration Guide](#configuration-guide) - Config.json and CLIProxyAPI setup
2. [Required Secrets](#required-secrets) - What you need to configure
3. [Full-Featured Strix Workflow](#full-featured-strix-workflow) - Complete workflow with all options
4. [Quick Scan Workflow](#quick-scan-workflow) - Simplified workflow for PR checks
5. [Scheduled Security Audit](#scheduled-security-audit) - Automated daily/weekly scans
6. [Manual Penetration Test](#manual-penetration-test) - On-demand deep scans
7. [StrixDB Sync Workflow](#strixdb-sync-workflow) - Sync artifacts to StrixDB
8. [New Features Guide](#new-features-guide) - Multi-action, Active Commander, Live Dashboard

---

## Configuration Guide

### 🔑 CLIProxyAPI Setup (Recommended - No API Key Needed!)

Strix now supports **CLIProxyAPI** which allows you to use your existing AI subscriptions via OAuth - **no API keys required!**

**Step 1: Run CLIProxyAPI**
```bash
# Download from https://github.com/router-for-me/CLIProxyAPI/releases
cliproxy run --port 8317
```

**Step 2: Create config.json (or use secrets in workflow)**

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
    "refresh_interval": 1.0,
    "show_time_remaining": true,
    "show_agent_details": true,
    "show_tool_logs": true,
    "show_resource_usage": true,
    "show_api_calls": true,
    "show_vulnerabilities": true
  },
  "scan_mode": "deep",
  "strixdb": {
    "enabled": false,
    "repo": "",
    "token": ""
  }
}
```

**Step 3: Run Strix**
```bash
strix --target ./your-app
```

### ⏱️ Timeframe Configuration

| Setting | Description | Range | Default |
|---------|-------------|-------|---------|
| `duration_minutes` | Total session time | 10 - 720 min | 60 min |
| `warning_minutes` | Time before end to warn AI | 1 - 30 min | 5 min |
| `time_awareness_enabled` | Enable time warnings | true/false | true |

### 📊 Enhanced Dashboard Features (NEW!)

The real-time dashboard now shows:
- ⏱️ Time remaining with progress bar
- 🤖 Active agents and their status
- 📊 Resource usage (tokens, cost)
- 🔄 **Live API Call Counter** - Track API calls in real-time
- 🐞 **Live Vulnerability Disclosure** - See vulnerabilities as they're found
- 🔧 Recent tool executions

---

## Required Secrets

Before using these workflows, add the following secrets to your repository:

| Secret | Required | Description |
|--------|----------|-------------|
| `CLIPROXY_ENDPOINT` | **Yes** | CLIProxyAPI endpoint (e.g., `http://your-server:8317/v1`) |
| `STRIX_MODEL` | Yes | Model name (e.g., `gemini-2.5-pro`, `claude-sonnet-4`, `gpt-5`) |
| `LLM_API_KEY` | **No** | API key - **NOT NEEDED** for CLIProxyAPI OAuth mode! |
| `STRIXDB_TOKEN` | Optional | GitHub token for StrixDB repository access |
| `STRIXDB_REPO` | Optional | StrixDB repository (e.g., `username/StrixDB`) |
| `PERPLEXITY_API_KEY` | Optional | Perplexity API key for web search capabilities |

> **Note**: With CLIProxyAPI, you only need `CLIPROXY_ENDPOINT` and `STRIX_MODEL` - no API key required!

---

## Full-Featured Strix Workflow

This is the complete workflow with all configuration options including:
- **CLIProxyAPI Support** (no API key needed)
- **Continuous Scanning** (doesn't stop on vulnerability found)
- **Custom Strix Installation** (from Hailer367/strix)
- **Configurable Timeframes** (10min - 12hr)
- **StrixDB Integration**

**File: `.github/workflows/strix-full.yml`**

```yaml
name: Strix Security Scan

on:
  # Manual trigger with inputs
  workflow_dispatch:
    inputs:
      target:
        description: 'Target to scan (URL, path, or repository)'
        required: true
        default: './'
        type: string
      prompt:
        description: 'Custom instructions for the AI agent'
        required: false
        default: ''
        type: string
      timeframe:
        description: 'Maximum runtime in minutes (10 - 720)'
        required: false
        default: '60'
        type: choice
        options:
          - '10'
          - '15'
          - '30'
          - '60'
          - '90'
          - '120'
          - '180'
          - '240'
          - '360'
          - '480'
          - '720'
      warning_minutes:
        description: 'Minutes before end to warn AI (1 - 30)'
        required: false
        default: '5'
        type: choice
        options:
          - '1'
          - '2'
          - '3'
          - '5'
          - '10'
          - '15'
          - '20'
          - '30'
      scan_mode:
        description: 'Scan mode'
        required: false
        default: 'deep'
        type: choice
        options:
          - quick
          - standard
          - deep
      enable_strixdb:
        description: 'Enable StrixDB artifact storage'
        required: false
        default: true
        type: boolean
  
  # Trigger on pull requests
  pull_request:
    branches: [main, master, develop]
  
  # Trigger on pushes to main
  push:
    branches: [main, master]

# Cancel in-progress runs for the same PR/branch
concurrency:
  group: strix-${{ github.head_ref || github.ref }}
  cancel-in-progress: true

env:
  # Default configuration
  DEFAULT_TIMEFRAME: '60'
  DEFAULT_WARNING_MINUTES: '5'
  DEFAULT_SCAN_MODE: 'standard'

jobs:
  strix-scan:
    name: Strix Security Scan
    runs-on: ubuntu-latest
    # Allow full timeframe + setup time
    timeout-minutes: ${{ fromJSON(github.event.inputs.timeframe || '120') }}
    
    permissions:
      contents: read
      security-events: write
      pull-requests: write
    
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      # IMPORTANT: Install from Hailer367/strix (enhanced version)
      - name: Install Strix (Enhanced Version)
        run: |
          # Clone the enhanced Strix from Hailer367/strix
          git clone https://github.com/Hailer367/strix.git /tmp/strix
          cd /tmp/strix
          
          # Install dependencies
          pip install poetry
          poetry config virtualenvs.create false
          poetry install --no-interaction
          
          # Verify installation
          echo "Strix version: $(python -c 'import strix; print(strix.__version__)' 2>/dev/null || echo 'installed')"
      
      - name: Create config.json
        run: |
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          WARNING="${{ github.event.inputs.warning_minutes || env.DEFAULT_WARNING_MINUTES }}"
          SCAN_MODE="${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}"
          
          # Create config with CLIProxyAPI endpoint (NO API KEY NEEDED!)
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ secrets.CLIPROXY_ENDPOINT }}",
              "model": "${{ secrets.STRIX_MODEL || 'gemini-2.5-pro' }}"
            },
            "timeframe": {
              "duration_minutes": ${TIMEFRAME},
              "warning_minutes": ${WARNING},
              "time_awareness_enabled": true
            },
            "dashboard": {
              "enabled": true,
              "show_time_remaining": true,
              "show_agent_details": true,
              "show_resource_usage": true,
              "show_api_calls": true,
              "show_vulnerabilities": true
            },
            "scan_mode": "${SCAN_MODE}",
            "strixdb": {
              "enabled": ${{ github.event.inputs.enable_strixdb || 'false' }},
              "repo": "${{ secrets.STRIXDB_REPO || '' }}",
              "token": "${{ secrets.STRIXDB_TOKEN || '' }}"
            },
            "perplexity_api_key": "${{ secrets.PERPLEXITY_API_KEY || '' }}"
          }
          EOF
          
          echo "Created config.json with:"
          echo "  - CLIProxyAPI endpoint: ${{ secrets.CLIPROXY_ENDPOINT && '✅ Set' || '❌ Missing' }}"
          echo "  - Duration: ${TIMEFRAME}m"
          echo "  - Warning threshold: ${WARNING}m"
          echo "  - Scan mode: ${SCAN_MODE}"
      
      - name: Prepare Custom Instructions
        id: instructions
        run: |
          # Build instruction string
          INSTRUCTIONS=""
          
          # Add custom prompt if provided
          if [ -n "${{ github.event.inputs.prompt }}" ]; then
            INSTRUCTIONS="${{ github.event.inputs.prompt }}"
          fi
          
          # Add StrixDB instructions if enabled
          if [ "${{ github.event.inputs.enable_strixdb }}" == "true" ]; then
            INSTRUCTIONS="${INSTRUCTIONS} Save any useful scripts, tools, exploits, methods, or knowledge to StrixDB for future use."
          fi
          
          # Add PR context if this is a pull request
          if [ "${{ github.event_name }}" == "pull_request" ]; then
            INSTRUCTIONS="${INSTRUCTIONS} This is a pull request review. Focus on security implications of the changed files."
          fi
          
          # Add multi-action instruction
          INSTRUCTIONS="${INSTRUCTIONS} Use multi-action mode (up to 7 actions per call) for efficiency."
          
          echo "instructions=${INSTRUCTIONS}" >> $GITHUB_OUTPUT
      
      # IMPORTANT: Run Strix with CONTINUOUS SCANNING
      # Does NOT stop when vulnerabilities are found - continues until timeframe exhausted
      - name: Run Strix Security Scan (Continuous Mode)
        id: strix
        run: |
          # Don't exit on error - we want to capture all results
          set +e
          
          TARGET="${{ github.event.inputs.target || './' }}"
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          
          echo "🦉 Starting Strix Security Scan"
          echo "  Target: ${TARGET}"
          echo "  Timeframe: ${TIMEFRAME} minutes"
          echo "  Mode: CONTINUOUS (will scan until timeframe exhausted)"
          echo ""
          
          # Run Strix with timeout - DOES NOT FAIL ON VULNERABILITY FOUND
          # The AI will continue scanning until the timeframe is exhausted
          timeout ${TIMEFRAME}m python -m strix.interface.cli \
            --target "${TARGET}" \
            --scan-mode "${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}" \
            --non-interactive \
            --instruction "${{ steps.instructions.outputs.instructions }}" \
            2>&1 | tee strix_output.log
          
          EXIT_CODE=$?
          
          # Count vulnerabilities found (parse from output)
          VULN_COUNT=$(grep -c "vulnerability\|VULNERABILITY\|CVE-" strix_output.log 2>/dev/null || echo "0")
          
          # Handle exit codes
          if [ $EXIT_CODE -eq 124 ]; then
            echo "✅ Strix scan completed (timeframe exhausted: ${TIMEFRAME} minutes)"
            echo "timed_out=true" >> $GITHUB_OUTPUT
            echo "scan_completed=true" >> $GITHUB_OUTPUT
          elif [ $EXIT_CODE -eq 0 ]; then
            echo "✅ Strix scan completed successfully"
            echo "scan_completed=true" >> $GITHUB_OUTPUT
          else
            echo "⚠️ Strix scan completed with exit code: ${EXIT_CODE}"
            echo "scan_completed=true" >> $GITHUB_OUTPUT
          fi
          
          echo "vulnerabilities_found=${VULN_COUNT}" >> $GITHUB_OUTPUT
          echo "exit_code=${EXIT_CODE}" >> $GITHUB_OUTPUT
          
          # Always exit 0 - we report vulnerabilities but don't fail the workflow
          # This allows continuous scanning to work properly
          exit 0
      
      - name: Upload Scan Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: strix-results-${{ github.run_id }}
          path: |
            strix_runs/
            strix_output.log
            config.json
          retention-days: 30
      
      - name: Comment on PR with Results
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            
            let summary = '## 🦉 Strix Security Scan Results\n\n';
            
            const timedOut = '${{ steps.strix.outputs.timed_out }}' === 'true';
            const scanCompleted = '${{ steps.strix.outputs.scan_completed }}' === 'true';
            const vulnsFound = '${{ steps.strix.outputs.vulnerabilities_found }}';
            const exitCode = '${{ steps.strix.outputs.exit_code }}';
            const timeframe = '${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}';
            
            if (timedOut) {
              summary += '⏱️ **Status:** Scan completed (full timeframe used)\n\n';
              summary += `The scan ran for the full ${timeframe} minutes, thoroughly testing the target.\n\n`;
            } else if (scanCompleted) {
              summary += '✅ **Status:** Scan Completed\n\n';
            }
            
            if (parseInt(vulnsFound) > 0) {
              summary += `🔴 **Vulnerabilities Found:** ${vulnsFound}\n\n`;
              summary += 'Security issues were identified. Please review the detailed report in the workflow artifacts.\n\n';
            } else {
              summary += '🟢 **No vulnerabilities found**\n\n';
            }
            
            summary += `**Scan Mode:** ${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}\n`;
            summary += `**Timeframe:** ${timeframe} minutes\n`;
            summary += `**Exit Code:** ${exitCode}\n\n`;
            
            summary += '### 🆕 New Features Used:\n';
            summary += '- ⚡ Multi-Action Mode (up to 7 actions per API call)\n';
            summary += '- 🎖️ Active Commander (main agent actively participates)\n';
            summary += '- 📊 Live Dashboard (real-time vulnerability disclosure)\n\n';
            
            summary += '📎 [View Full Results](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})\n';
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: summary
            });
      
      # Optional: Create GitHub Security Alert for vulnerabilities
      - name: Create Security Summary
        if: always()
        run: |
          echo "## Strix Security Scan Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "- **Target:** ${{ github.event.inputs.target || './' }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Scan Mode:** ${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Duration:** ${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }} minutes" >> $GITHUB_STEP_SUMMARY
          echo "- **Vulnerabilities Found:** ${{ steps.strix.outputs.vulnerabilities_found }}" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "See workflow artifacts for detailed results." >> $GITHUB_STEP_SUMMARY
```

---

## Quick Scan Workflow

A simplified workflow for quick PR security checks (10-15 minutes).

**File: `.github/workflows/strix-quick.yml`**

```yaml
name: Strix Quick Scan

on:
  pull_request:
    branches: [main, master]

jobs:
  quick-scan:
    name: Quick Security Check
    runs-on: ubuntu-latest
    timeout-minutes: 20
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      # Install from Hailer367/strix (enhanced version)
      - name: Install Strix (Enhanced)
        run: |
          git clone https://github.com/Hailer367/strix.git /tmp/strix
          cd /tmp/strix
          pip install poetry
          poetry config virtualenvs.create false
          poetry install --no-interaction
      
      - name: Create config.json
        run: |
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ secrets.CLIPROXY_ENDPOINT }}",
              "model": "${{ secrets.STRIX_MODEL || 'gemini-2.5-pro' }}"
            },
            "timeframe": {
              "duration_minutes": 10,
              "warning_minutes": 2,
              "time_awareness_enabled": true
            },
            "scan_mode": "quick"
          }
          EOF
      
      - name: Run Quick Scan
        run: |
          set +e
          python -m strix.interface.cli -n -t ./ --scan-mode quick \
            --instruction "Focus on critical vulnerabilities only. Use multi-action mode for efficiency."
          exit 0
      
      - name: Upload Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: quick-scan-${{ github.run_id }}
          path: strix_runs/
```

---

## Scheduled Security Audit

Automated scheduled security scans with configurable duration up to 12 hours.

**File: `.github/workflows/strix-scheduled.yml`**

```yaml
name: Scheduled Security Audit

on:
  schedule:
    # Run every Monday at 2 AM UTC
    - cron: '0 2 * * 1'
  workflow_dispatch:
    inputs:
      scan_mode:
        description: 'Scan mode'
        required: false
        default: 'deep'
        type: choice
        options:
          - standard
          - deep
      duration_hours:
        description: 'Duration in hours (1-12)'
        required: false
        default: '4'
        type: choice
        options:
          - '1'
          - '2'
          - '4'
          - '6'
          - '8'
          - '12'

jobs:
  security-audit:
    name: Weekly Security Audit
    runs-on: ubuntu-latest
    timeout-minutes: 750  # 12.5 hours max
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Strix (Enhanced)
        run: |
          git clone https://github.com/Hailer367/strix.git /tmp/strix
          cd /tmp/strix
          pip install poetry
          poetry config virtualenvs.create false
          poetry install --no-interaction
      
      - name: Create config.json
        run: |
          HOURS="${{ github.event.inputs.duration_hours || '4' }}"
          MINUTES=$((HOURS * 60))
          WARNING=$((MINUTES / 10))
          if [ $WARNING -lt 5 ]; then WARNING=5; fi
          if [ $WARNING -gt 30 ]; then WARNING=30; fi
          
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ secrets.CLIPROXY_ENDPOINT }}",
              "model": "${{ secrets.STRIX_MODEL || 'gemini-2.5-pro' }}"
            },
            "timeframe": {
              "duration_minutes": ${MINUTES},
              "warning_minutes": ${WARNING},
              "time_awareness_enabled": true
            },
            "scan_mode": "${{ github.event.inputs.scan_mode || 'deep' }}",
            "strixdb": {
              "enabled": true,
              "repo": "${{ secrets.STRIXDB_REPO }}",
              "token": "${{ secrets.STRIXDB_TOKEN }}"
            }
          }
          EOF
      
      - name: Run Deep Security Audit
        env:
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          set +e
          HOURS="${{ github.event.inputs.duration_hours || '4' }}"
          MINUTES=$((HOURS * 60))
          
          timeout ${MINUTES}m python -m strix.interface.cli -n -t ./ \
            --scan-mode ${{ github.event.inputs.scan_mode || 'deep' }} \
            --instruction "Perform comprehensive security audit. Save all findings to StrixDB. Use multi-action mode."
          exit 0
      
      - name: Upload Audit Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: security-audit-${{ github.run_id }}
          path: strix_runs/
          retention-days: 90
```

---

## Manual Penetration Test

On-demand deep penetration testing workflow.

**File: `.github/workflows/strix-pentest.yml`**

```yaml
name: Manual Penetration Test

on:
  workflow_dispatch:
    inputs:
      target:
        description: 'Target to test'
        required: true
        type: string
      prompt:
        description: 'Detailed instructions for the penetration test'
        required: true
        type: string
      timeframe:
        description: 'Maximum runtime in minutes (10-720)'
        required: true
        default: '120'
        type: choice
        options:
          - '10'
          - '15'
          - '30'
          - '60'
          - '90'
          - '120'
          - '180'
          - '240'
          - '360'
          - '480'
          - '720'

jobs:
  pentest:
    name: Penetration Test
    runs-on: ubuntu-latest
    timeout-minutes: ${{ fromJSON(github.event.inputs.timeframe) }}
    environment: security-testing
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Strix (Enhanced)
        run: |
          git clone https://github.com/Hailer367/strix.git /tmp/strix
          cd /tmp/strix
          pip install poetry
          poetry config virtualenvs.create false
          poetry install --no-interaction
      
      - name: Create config.json
        run: |
          TIMEFRAME="${{ github.event.inputs.timeframe }}"
          WARNING=$((TIMEFRAME / 10))
          if [ $WARNING -lt 5 ]; then WARNING=5; fi
          
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ secrets.CLIPROXY_ENDPOINT }}",
              "model": "${{ secrets.STRIX_MODEL || 'gemini-2.5-pro' }}"
            },
            "timeframe": {
              "duration_minutes": ${TIMEFRAME},
              "warning_minutes": ${WARNING},
              "time_awareness_enabled": true
            },
            "scan_mode": "deep",
            "strixdb": {
              "enabled": true,
              "repo": "${{ secrets.STRIXDB_REPO }}",
              "token": "${{ secrets.STRIXDB_TOKEN }}"
            }
          }
          EOF
      
      - name: Run Penetration Test
        env:
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          set +e
          python -m strix.interface.cli -n \
            -t "${{ github.event.inputs.target }}" \
            --scan-mode deep \
            --instruction "${{ github.event.inputs.prompt }} Use multi-action mode for efficiency. Save exploits to StrixDB."
          exit 0
      
      - name: Upload Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: pentest-results-${{ github.run_id }}
          path: strix_runs/
          retention-days: 90
```

---

## StrixDB Sync Workflow

Workflow to sync and organize StrixDB artifacts.

**File: `.github/workflows/strixdb-sync.yml`**

```yaml
name: StrixDB Sync

on:
  workflow_dispatch:
    inputs:
      action:
        description: 'Action to perform'
        required: true
        type: choice
        options:
          - sync
          - cleanup
          - export

jobs:
  strixdb-sync:
    name: StrixDB Operations
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout StrixDB
        uses: actions/checkout@v4
        with:
          repository: ${{ secrets.STRIXDB_REPO }}
          token: ${{ secrets.STRIXDB_TOKEN }}
          path: strixdb
      
      - name: Process StrixDB
        working-directory: strixdb
        run: |
          case "${{ github.event.inputs.action }}" in
            sync)
              echo "Syncing StrixDB..."
              for dir in scripts exploits knowledge libraries sources methods tools configs; do
                if [ -d "$dir" ]; then
                  echo "## ${dir^}" > "${dir}/README.md"
                  echo "" >> "${dir}/README.md"
                  find "$dir" -name "*.json" -exec cat {} \; | jq -r '.name' >> "${dir}/README.md" 2>/dev/null || true
                fi
              done
              ;;
            cleanup)
              echo "Cleaning up old entries..."
              ;;
            export)
              echo "Exporting StrixDB..."
              tar -czvf ../strixdb-export.tar.gz .
              ;;
          esac
      
      - name: Commit Changes
        if: github.event.inputs.action != 'export'
        working-directory: strixdb
        run: |
          git config user.name "StrixDB Bot"
          git config user.email "strixdb@users.noreply.github.com"
          git add -A
          git diff --staged --quiet || git commit -m "StrixDB: ${{ github.event.inputs.action }}"
          git push
```

---

## New Features Guide

### ⚡ Multi-Action Mode (Up to 7 Actions per API Call)

The AI can now execute up to 7 tool calls in a single message for maximum efficiency:

```xml
<!-- Instead of one action per message, batch related actions -->
<function=terminal_execute>
<parameter=command>nmap -sV target.com</parameter>
</function>

<function=terminal_execute>
<parameter=command>subfinder -d target.com</parameter>
</function>

<function=web_search>
<parameter=query>target.com CVE vulnerabilities</parameter>
</function>
```

**Benefits:**
- 7x fewer API calls for batched operations
- Parallel execution for independent tools
- Faster reconnaissance
- Lower costs

### 🎖️ Active Commander Mode

The main agent is no longer just a coordinator - it actively participates:

**Before (Old):** Main agent only delegates, never does work
**After (New):** Main agent actively tests, writes scripts, and leads by example

The main agent now:
- Performs initial reconnaissance directly
- Writes custom scripts and exploits
- Tests high-priority vulnerabilities
- Works alongside sub-agents (not just supervising)

### 📊 Live Dashboard Enhancements

New dashboard features:
- **Live API Call Counter:** Track API usage in real-time
- **Live Vulnerability Disclosure:** See vulnerabilities as they're discovered
- **Severity Breakdown:** Critical/High/Medium/Low counts
- **Recent Findings List:** Last 5 vulnerabilities with details

### 🔄 Continuous Scanning

The workflow no longer stops when a vulnerability is found:
- Continues scanning until the timeframe is exhausted
- Finds more vulnerabilities in a single run
- Reports all findings at the end
- Never fails the workflow just because vulnerabilities exist

---

## Timeframe Reference

| Duration | Use Case | Recommended Warning |
|----------|----------|---------------------|
| 10 min | Quick CI check | 2 min |
| 15 min | PR security gate | 2 min |
| 30 min | Standard scan | 3 min |
| 60 min | Thorough review | 5 min |
| 120 min (2h) | Deep analysis | 10 min |
| 240 min (4h) | Full audit | 15 min |
| 480 min (8h) | Extended pentest | 20 min |
| 720 min (12h) | Maximum duration | 30 min |

---

## Tips for Effective Usage

### Writing Effective Prompts

Good prompts should include:
1. **Objective**: What you want to achieve
2. **Focus Areas**: Specific vulnerability types to prioritize
3. **Context**: Application type, technology stack
4. **Constraints**: What NOT to test

**Example:**
```
Focus on authentication bypass and IDOR vulnerabilities in the /api/* endpoints. 
The application uses JWT tokens. Do NOT test /api/health endpoints.
Use multi-action mode for efficiency. Save useful exploits to StrixDB.
```

### Security Best Practices

1. **Use CLIProxyAPI** - No API keys to manage
2. **Set reasonable timeframes** - More time = more thorough scanning
3. **Enable StrixDB** - Build a knowledge base over time
4. **Use multi-action mode** - Maximize efficiency

---

*Last updated: December 2024*
*Version: Enhanced Edition with CLIProxyAPI, Multi-Action, and Active Commander*
