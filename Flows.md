# Strix GitHub Actions Workflows

This document contains GitHub Actions workflow configurations for running Strix automatically. Copy the desired workflow to `.github/workflows/` in your repository.

---

## Table of Contents

1. [Configuration Guide](#configuration-guide) - **NEW!** Config.json and timeframe setup
2. [Full-Featured Strix Workflow](#full-featured-strix-workflow) - Complete workflow with all options
3. [Quick Scan Workflow](#quick-scan-workflow) - Simplified workflow for PR checks
4. [Scheduled Security Audit](#scheduled-security-audit) - Automated daily/weekly scans
5. [Manual Penetration Test](#manual-penetration-test) - On-demand deep scans
6. [StrixDB Sync Workflow](#strixdb-sync-workflow) - Sync artifacts to StrixDB

---

## Configuration Guide

### 📝 config.json Setup (Recommended)

Strix now uses a **config.json** file for configuration. This is the preferred method over environment variables.

**Step 1: Run CLIProxyAPI**
```bash
# Install CLIProxyAPI from https://github.com/router-for-me/CLIProxyAPI/releases
cliproxy run --port 8317
```

**Step 2: Create config.json**

Create a `config.json` file in your project root:

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
    "show_resource_usage": true
  },
  "scan_mode": "deep",
  "strixdb": {
    "enabled": false,
    "repo": "",
    "token": ""
  },
  "perplexity_api_key": ""
}
```

**Step 3: Run Strix**
```bash
strix --target ./your-app
```

### ⏱️ Timeframe Configuration

The timeframe system allows you to set session duration from **10 minutes to 12 hours** (720 minutes).

| Setting | Description | Range | Default |
|---------|-------------|-------|---------|
| `duration_minutes` | Total session time | 10 - 720 min | 60 min |
| `warning_minutes` | Time before end to warn AI | 1 - 30 min | 5 min |
| `time_awareness_enabled` | Enable time warnings | true/false | true |

**How Time Warnings Work:**

1. **Standard Warning**: When `warning_minutes` remaining, the AI receives a notice to start wrapping up
2. **Critical Warning**: At half of `warning_minutes` (e.g., 2.5 min if warning is 5 min), AI receives urgent finish notice
3. **Session End**: When time expires in non-interactive mode, session completes automatically

**Example Configurations:**

```json
// Quick scan (15 minutes)
{
  "timeframe": {
    "duration_minutes": 15,
    "warning_minutes": 2,
    "time_awareness_enabled": true
  }
}

// Standard scan (1 hour)
{
  "timeframe": {
    "duration_minutes": 60,
    "warning_minutes": 5,
    "time_awareness_enabled": true
  }
}

// Deep audit (4 hours)
{
  "timeframe": {
    "duration_minutes": 240,
    "warning_minutes": 15,
    "time_awareness_enabled": true
  }
}

// Maximum duration (12 hours)
{
  "timeframe": {
    "duration_minutes": 720,
    "warning_minutes": 30,
    "time_awareness_enabled": true
  }
}
```

### 📊 Dashboard Configuration

The real-time dashboard shows:
- ⏱️ Time remaining with progress bar
- 🤖 Active agents and their status
- 📊 Resource usage (tokens, cost)
- 🐞 Vulnerabilities found
- 🔧 Recent tool executions

```json
{
  "dashboard": {
    "enabled": true,
    "refresh_interval": 1.0,
    "show_time_remaining": true,
    "show_agent_details": true,
    "show_tool_logs": true,
    "show_resource_usage": true
  }
}
```

---

## Required Secrets

Before using these workflows, add the following secrets to your repository:

| Secret | Required | Description |
|--------|----------|-------------|
| `CLIPROXY_ENDPOINT` | Yes | CLIProxyAPI endpoint (e.g., `http://localhost:8317/v1`) |
| `STRIX_MODEL` | Yes | Model name (e.g., `gemini-2.5-pro`, `claude-sonnet-4`) |
| `LLM_API_KEY` | Optional | API key (not needed for CLIProxyAPI OAuth mode) |
| `STRIXDB_TOKEN` | Optional | GitHub token for StrixDB repository access |
| `STRIXDB_REPO` | Optional | StrixDB repository (e.g., `username/StrixDB`) |
| `PERPLEXITY_API_KEY` | Optional | Perplexity API key for web search capabilities |

---

## Full-Featured Strix Workflow

This is the complete workflow with all configuration options including custom prompts, configurable timeframes (10min - 12hr), and StrixDB integration.

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
      
      - name: Install Strix
        run: |
          pip install strix-agent
          echo "Strix version: $(strix --version)"
      
      - name: Create config.json
        run: |
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          WARNING="${{ github.event.inputs.warning_minutes || env.DEFAULT_WARNING_MINUTES }}"
          SCAN_MODE="${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}"
          
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ secrets.CLIPROXY_ENDPOINT }}",
              "model": "${{ secrets.STRIX_MODEL || 'gemini-2.5-pro' }}",
              "api_key": "${{ secrets.LLM_API_KEY || '' }}"
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
              "show_resource_usage": true
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
          
          echo "Created config.json with ${TIMEFRAME}m duration, ${WARNING}m warning"
      
      - name: Prepare Custom Instructions
        id: instructions
        run: |
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          WARNING="${{ github.event.inputs.warning_minutes || env.DEFAULT_WARNING_MINUTES }}"
          
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
          
          echo "instructions=${INSTRUCTIONS}" >> $GITHUB_OUTPUT
      
      - name: Run Strix Security Scan
        id: strix
        run: |
          set +e  # Don't exit on error
          
          TARGET="${{ github.event.inputs.target || './' }}"
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          
          # Run Strix with timeout enforcement
          timeout ${TIMEFRAME}m strix \
            --target "${TARGET}" \
            --scan-mode "${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}" \
            --non-interactive \
            --instruction "${{ steps.instructions.outputs.instructions }}" \
            2>&1 | tee strix_output.log
          
          EXIT_CODE=$?
          
          # Handle exit codes
          if [ $EXIT_CODE -eq 124 ]; then
            echo "Strix scan timed out after ${TIMEFRAME} minutes"
            echo "timed_out=true" >> $GITHUB_OUTPUT
          elif [ $EXIT_CODE -eq 2 ]; then
            echo "Vulnerabilities found!"
            echo "vulnerabilities_found=true" >> $GITHUB_OUTPUT
          fi
          
          echo "exit_code=${EXIT_CODE}" >> $GITHUB_OUTPUT
      
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
      
      - name: Comment on PR
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            
            let summary = '## 🦉 Strix Security Scan Results\n\n';
            
            const timedOut = '${{ steps.strix.outputs.timed_out }}' === 'true';
            const vulnsFound = '${{ steps.strix.outputs.vulnerabilities_found }}' === 'true';
            const exitCode = '${{ steps.strix.outputs.exit_code }}';
            const timeframe = '${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}';
            
            if (timedOut) {
              summary += '⏱️ **Status:** Scan completed (time limit reached)\n\n';
              summary += `The scan ran for the full ${timeframe} minutes. Results may be partial.\n\n`;
            } else if (vulnsFound) {
              summary += '🔴 **Status:** Vulnerabilities Found\n\n';
              summary += 'Security issues were identified. Please review the detailed report in the workflow artifacts.\n\n';
            } else {
              summary += '🟢 **Status:** Scan Completed\n\n';
              summary += 'No critical vulnerabilities were found.\n\n';
            }
            
            summary += `**Scan Mode:** ${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}\n`;
            summary += `**Timeframe:** ${timeframe} minutes\n`;
            summary += `**Exit Code:** ${exitCode}\n\n`;
            
            summary += '📎 [View Full Results](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})\n';
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: summary
            });
      
      - name: Fail if Vulnerabilities Found
        if: steps.strix.outputs.vulnerabilities_found == 'true'
        run: |
          echo "Security vulnerabilities were found. Failing the workflow."
          exit 1
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
              "duration_minutes": 10,
              "warning_minutes": 2,
              "time_awareness_enabled": true
            },
            "scan_mode": "quick"
          }
          EOF
      
      - name: Run Quick Scan
        run: |
          strix -n -t ./ --scan-mode quick \
            --instruction "Focus on critical vulnerabilities only. You have limited time."
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
    timeout-minutes: 750  # 12.5 hours max (accounting for setup)
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Strix
        run: pip install strix-agent
      
      - name: Create config.json
        run: |
          # Convert hours to minutes
          HOURS="${{ github.event.inputs.duration_hours || '4' }}"
          MINUTES=$((HOURS * 60))
          WARNING=$((MINUTES / 10))  # 10% of duration as warning
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
          
          echo "Audit configured: ${HOURS} hours (${MINUTES} minutes)"
      
      - name: Run Deep Security Audit
        env:
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          strix -n -t ./ \
            --scan-mode ${{ github.event.inputs.scan_mode || 'deep' }} \
            --instruction "Perform comprehensive security audit. Save all findings and useful artifacts to StrixDB. Generate detailed compliance report."
      
      - name: Upload Audit Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: security-audit-${{ github.run_id }}
          path: strix_runs/
          retention-days: 90
      
      - name: Create Issue for Findings
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '🔴 Security Audit Found Vulnerabilities',
              body: `## Weekly Security Audit Results\n\nThe automated security audit found potential vulnerabilities.\n\n**Run:** https://github.com/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}\n\nPlease review the findings and take appropriate action.`,
              labels: ['security', 'automated']
            });
```

---

## Manual Penetration Test

On-demand deep penetration testing workflow with flexible timeframes.

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
      warning_minutes:
        description: 'Warning threshold in minutes'
        required: false
        default: '5'
        type: string
      credentials:
        description: 'Test credentials (format: user:pass) - stored securely'
        required: false
        type: string
      scope:
        description: 'Scope limitations (comma-separated paths to exclude)'
        required: false
        type: string

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
      
      - name: Install Strix
        run: pip install strix-agent
      
      - name: Create config.json
        run: |
          TIMEFRAME="${{ github.event.inputs.timeframe }}"
          WARNING="${{ github.event.inputs.warning_minutes || '5' }}"
          
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
      
      - name: Build Instructions
        id: build-instructions
        run: |
          INSTRUCTIONS="${{ github.event.inputs.prompt }}"
          
          if [ -n "${{ github.event.inputs.credentials }}" ]; then
            INSTRUCTIONS="${INSTRUCTIONS} Use these credentials for authenticated testing: ${{ github.event.inputs.credentials }}"
          fi
          
          if [ -n "${{ github.event.inputs.scope }}" ]; then
            INSTRUCTIONS="${INSTRUCTIONS} Do NOT test these paths: ${{ github.event.inputs.scope }}"
          fi
          
          INSTRUCTIONS="${INSTRUCTIONS} Save all exploits, PoCs, and useful findings to StrixDB."
          
          echo "instructions=${INSTRUCTIONS}" >> $GITHUB_OUTPUT
      
      - name: Run Penetration Test
        env:
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          strix -n \
            -t "${{ github.event.inputs.target }}" \
            --scan-mode deep \
            --instruction "${{ steps.build-instructions.outputs.instructions }}"
      
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
      category:
        description: 'Category to process (all for everything)'
        required: false
        default: 'all'
        type: string

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
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Process StrixDB
        working-directory: strixdb
        run: |
          case "${{ github.event.inputs.action }}" in
            sync)
              echo "Syncing StrixDB..."
              # Update index files
              for dir in scripts exploits knowledge libraries sources methods tools configs; do
                if [ -d "$dir" ]; then
                  echo "## ${dir^}" > "${dir}/README.md"
                  echo "" >> "${dir}/README.md"
                  echo "| Name | Description | Tags |" >> "${dir}/README.md"
                  echo "|------|-------------|------|" >> "${dir}/README.md"
                  find "$dir" -name "*.json" -exec cat {} \; | jq -r '"\(.name) | \(.description) | \(.tags | join(", "))"' >> "${dir}/README.md" 2>/dev/null || true
                fi
              done
              ;;
            cleanup)
              echo "Cleaning up old/duplicate entries..."
              # Add cleanup logic
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
          git diff --staged --quiet || git commit -m "StrixDB: ${{ github.event.inputs.action }} operation"
          git push
      
      - name: Upload Export
        if: github.event.inputs.action == 'export'
        uses: actions/upload-artifact@v4
        with:
          name: strixdb-export
          path: strixdb-export.tar.gz
```

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

## Configuration Reference

### config.json Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `api.endpoint` | string | CLIProxyAPI endpoint URL | Yes |
| `api.model` | string | Model name (e.g., `gemini-2.5-pro`) | Yes |
| `api.api_key` | string | API key (optional for OAuth) | No |
| `timeframe.duration_minutes` | int | Session duration (10-720) | No (default: 60) |
| `timeframe.warning_minutes` | int | Warning threshold (1-30) | No (default: 5) |
| `timeframe.time_awareness_enabled` | bool | Enable time warnings | No (default: true) |
| `dashboard.enabled` | bool | Enable dashboard | No (default: true) |
| `scan_mode` | string | `quick`, `standard`, or `deep` | No (default: deep) |

### Environment Variables (Legacy)

| Variable | Description |
|----------|-------------|
| `STRIX_LLM` | Model identifier |
| `LLM_API_KEY` | API key for LLM provider |
| `LLM_API_BASE` | Custom API base URL |
| `PERPLEXITY_API_KEY` | Perplexity API key for web search |
| `STRIXDB_TOKEN` | GitHub token for StrixDB |
| `STRIXDB_REPO` | StrixDB repository name |

---

## Tips for Effective Workflows

### Timeframe Best Practices

1. **Quick checks (10-15 min)**: Use for CI/CD gates on PRs
2. **Standard scans (30-60 min)**: Daily/regular security checks
3. **Deep audits (2-4 hours)**: Weekly comprehensive reviews
4. **Extended pentests (8-12 hours)**: Monthly deep assessments

### Writing Effective Prompts

Good prompts should include:

1. **Objective**: What you want to achieve
2. **Focus Areas**: Specific vulnerability types to prioritize
3. **Context**: Application type, technology stack
4. **Constraints**: What NOT to test
5. **Output Requirements**: What format for findings

**Example:**
```
Focus on authentication bypass and IDOR vulnerabilities in the /api/* endpoints. 
The application uses JWT tokens. Do NOT test /api/health or /api/status endpoints.
Provide detailed PoCs for any findings and save useful bypass techniques to StrixDB.
```

### Security Best Practices

1. **Use environments** for sensitive workflows
2. **Limit permissions** to minimum required
3. **Store credentials in secrets**, never in workflow files
4. **Set reasonable timeouts** to prevent runaway costs
5. **Review artifacts** before making them public
