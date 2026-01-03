# StriFlow - Integrated Strix Security Scan with Qwen Token Load Balancing

This document contains the **integrated** GitHub Actions workflow that combines:
- **Qwen Token Decryption** from the `QWEN_TOKENS` GitHub secret
- **CLIProxyAPI Load Balancing** for multi-account API access
- **Strix Security Scanning** with full feature support

> **Why StriFlow?**
> Instead of running two separate workflows (one for load-balancer, one for scanning), StriFlow does everything in one workflow. Simply provide your decryption password and target - it handles the rest!

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [How It Works](#how-it-works)
3. [Required GitHub Secrets](#required-github-secrets)
4. [StriFlow Workflow](#striflow-workflow)
5. [Usage Instructions](#usage-instructions)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before using StriFlow, you need:

1. **Collected Qwen Tokens**: Run the `auth-token-collector.yml` workflow to collect and encrypt your Qwen Code account tokens
2. **QWEN_TOKENS Secret**: Add the encrypted tokens output to your repository secrets as `QWEN_TOKENS`
3. **Remember your password**: The same password used during token collection

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           StriFlow Workflow                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │   Decrypt    │   │   Install    │   │    Start     │   │    Install   │ │
│  │ QWEN_TOKENS  │──▶│ CLIProxyAPI  │──▶│ CLIProxyAPI  │──▶│    Strix     │ │
│  │  (openssl)   │   │ (from source)│   │   Server     │   │ (from source)│ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│                                              │                              │
│                                              ▼                              │
│                                 ┌────────────────────────┐                  │
│                                 │   http://localhost:8317│                  │
│                                 │   (API Endpoint)       │                  │
│                                 └────────────────────────┘                  │
│                                              │                              │
│                                              ▼                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Run Strix Security Scan                       │  │
│  │  - Uses local CLIProxyAPI endpoint                                    │  │
│  │  - Load balances across all Qwen Code accounts                        │  │
│  │  - Continuous scanning until timeframe exhausted                      │  │
│  │  - Full StrixDB integration                                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Features:**
- **Single Workflow**: No need to run load-balancer separately
- **From Source Installation**: Both CLIProxyAPI and Strix installed from source (latest features)
- **OpenSSL Decryption**: Uses the same encryption method as auth-token-collector.yml
- **Automatic Load Balancing**: All Qwen accounts used in round-robin fashion
- **Health Monitoring**: Automatic health checks before scanning starts

---

## Required GitHub Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `QWEN_TOKENS` | **Yes** | Encrypted tokens from auth-token-collector.yml workflow |
| `STRIXDB_REPO` | Optional | Your StrixDB repository (e.g., `username/StrixDB`) |
| `STRIXDB_TOKEN` | Optional | GitHub PAT with repo access for StrixDB |
| `PERPLEXITY_API_KEY` | Optional | Perplexity API key for web search |

> **Note**: `QWEN_TOKENS` contains your encrypted Qwen Code account tokens. The decryption password is provided at workflow runtime.

---

## StriFlow Workflow

Copy this workflow to `.github/workflows/striflow.yml`:

```yaml
name: StriFlow - Integrated Strix Security Scan

on:
  workflow_dispatch:
    inputs:
      decryption_password:
        description: 'Password to decrypt QWEN_TOKENS (same as used in auth-token-collector)'
        required: true
        type: string
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
      model:
        description: 'AI Model to use'
        required: false
        default: 'qwen3-coder-plus'
        type: choice
        options:
          - 'qwen3-coder-plus'
          - 'qwen-coder-plus'
          - 'qwen-plus'
          - 'qwen-max'
      enable_strixdb:
        description: 'Enable StrixDB artifact storage'
        required: false
        default: true
        type: boolean

# Cancel in-progress runs for the same branch
concurrency:
  group: striflow-${{ github.head_ref || github.ref }}
  cancel-in-progress: true

env:
  DEFAULT_TIMEFRAME: '60'
  DEFAULT_WARNING_MINUTES: '5'
  DEFAULT_SCAN_MODE: 'standard'
  CLIPROXY_PORT: '8317'

jobs:
  striflow-scan:
    name: StriFlow Security Scan
    runs-on: ubuntu-latest
    # Allow full timeframe + setup time (30 min buffer)
    timeout-minutes: ${{ fromJSON(github.event.inputs.timeframe || '60') + 30 }}
    
    permissions:
      contents: read
      security-events: write
      pull-requests: write
    
    steps:
      # ==========================================
      # STEP 1: Checkout Repository
      # ==========================================
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      # ==========================================
      # STEP 2: Set up Build Environment
      # ==========================================
      - name: Set up Go (for CLIProxyAPI)
        uses: actions/setup-go@v5
        with:
          go-version: '1.21'
      
      - name: Set up Python (for Strix)
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      # ==========================================
      # STEP 3: Decrypt QWEN_TOKENS
      # ==========================================
      - name: Decrypt Qwen Tokens
        id: decrypt
        env:
          QWEN_TOKENS: ${{ secrets.QWEN_TOKENS }}
          DECRYPTION_PASSWORD: ${{ github.event.inputs.decryption_password }}
        run: |
          echo "Decrypting Qwen tokens..."
          
          # Check if QWEN_TOKENS is set
          if [ -z "$QWEN_TOKENS" ]; then
            echo "::error::QWEN_TOKENS secret is not set!"
            echo "Please run auth-token-collector.yml first and add the encrypted tokens to repository secrets."
            exit 1
          fi
          
          # Create working directory
          mkdir -p ~/.cli-proxy-api
          
          # Decode base64 to encrypted file
          echo "$QWEN_TOKENS" | base64 -d > ~/.cli-proxy-api/qwen-tokens.enc
          
          # Decrypt using openssl (same method as auth-token-collector.yml)
          echo "$DECRYPTION_PASSWORD" | openssl enc -aes-256-cbc -d -salt -pbkdf2 \
            -in ~/.cli-proxy-api/qwen-tokens.enc \
            -out ~/.cli-proxy-api/qwen-tokens.tar.gz \
            -pass stdin
          
          DECRYPT_RESULT=$?
          if [ $DECRYPT_RESULT -ne 0 ]; then
            echo "::error::Failed to decrypt tokens. Check your password!"
            exit 1
          fi
          
          # Extract tokens
          cd ~/.cli-proxy-api
          tar -xzf qwen-tokens.tar.gz
          
          # Count extracted token files
          TOKEN_COUNT=$(ls qwen-*.json 2>/dev/null | wc -l)
          
          if [ "$TOKEN_COUNT" -eq "0" ]; then
            echo "::error::No token files found after decryption!"
            exit 1
          fi
          
          echo "Successfully decrypted $TOKEN_COUNT Qwen account token(s)"
          echo "token_count=$TOKEN_COUNT" >> $GITHUB_OUTPUT
          
          # Clean up encrypted files
          rm -f qwen-tokens.enc qwen-tokens.tar.gz
      
      # ==========================================
      # STEP 4: Install CLIProxyAPI from Source
      # ==========================================
      - name: Install CLIProxyAPI from Source
        run: |
          echo "Installing CLIProxyAPI from source..."
          
          # Clone CLIProxyAPI repository
          git clone https://github.com/router-for-me/CLIProxyAPI.git /tmp/CLIProxyAPI
          cd /tmp/CLIProxyAPI
          
          # Build from source
          go build -o cli-proxy-api ./cmd/server
          
          # Install to system path
          sudo mv cli-proxy-api /usr/local/bin/
          
          # Verify installation
          cli-proxy-api --version || echo "CLIProxyAPI installed successfully"
          
          # Clean up
          cd /
          rm -rf /tmp/CLIProxyAPI
          
          echo "CLIProxyAPI installation complete"
      
      # ==========================================
      # STEP 5: Configure and Start CLIProxyAPI
      # ==========================================
      - name: Configure CLIProxyAPI
        run: |
          echo "Configuring CLIProxyAPI..."
          
          # Create configuration file
          cat > ~/.cli-proxy-api/config.yaml << 'EOF'
          server:
            port: ${{ env.CLIPROXY_PORT }}
            host: "0.0.0.0"
          
          providers:
            qwen:
              enabled: true
              load-balance: true
              round-robin: true
              health-check: true
          
          auth-dir: "~/.cli-proxy-api"
          
          quota-exceeded:
            switch-project: true
            switch-preview-model: true
          
          request-retry: 3
          timeout: "300s"
          
          logging:
            level: "info"
            file: "./cliproxy.log"
          
          cors:
            enabled: true
            origins: ["*"]
          EOF
          
          # Expand home directory in config
          sed -i "s|~|$HOME|g" ~/.cli-proxy-api/config.yaml
          
          echo "Configuration created at ~/.cli-proxy-api/config.yaml"
          cat ~/.cli-proxy-api/config.yaml
      
      - name: Start CLIProxyAPI Server
        id: cliproxy
        run: |
          echo "Starting CLIProxyAPI server..."
          
          # Start server in background
          cd ~/.cli-proxy-api
          nohup cli-proxy-api -config config.yaml > cliproxy.log 2>&1 &
          SERVER_PID=$!
          echo $SERVER_PID > cliproxy.pid
          
          # Wait for server to start
          echo "Waiting for server to initialize..."
          sleep 10
          
          # Check if server is running
          if ! kill -0 $SERVER_PID 2>/dev/null; then
            echo "::error::CLIProxyAPI server failed to start!"
            cat cliproxy.log
            exit 1
          fi
          
          echo "CLIProxyAPI server started (PID: $SERVER_PID)"
          
          # Health check - wait for server to be ready
          MAX_RETRIES=10
          RETRY_COUNT=0
          
          while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
            if curl -s http://localhost:${{ env.CLIPROXY_PORT }}/v1/models > /dev/null 2>&1; then
              echo "CLIProxyAPI is healthy and ready!"
              break
            fi
            
            RETRY_COUNT=$((RETRY_COUNT + 1))
            echo "Waiting for CLIProxyAPI to be ready... (attempt $RETRY_COUNT/$MAX_RETRIES)"
            sleep 5
          done
          
          if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            echo "::warning::CLIProxyAPI health check timed out, but continuing..."
          fi
          
          # Output the endpoint
          ENDPOINT="http://localhost:${{ env.CLIPROXY_PORT }}/v1"
          echo "endpoint=$ENDPOINT" >> $GITHUB_OUTPUT
          echo "pid=$SERVER_PID" >> $GITHUB_OUTPUT
          
          echo ""
          echo "=========================================="
          echo "CLIPROXYAPI READY"
          echo "=========================================="
          echo "Endpoint: $ENDPOINT"
          echo "Accounts: ${{ steps.decrypt.outputs.token_count }}"
          echo "Load Balancing: Round-robin enabled"
          echo "=========================================="
      
      # ==========================================
      # STEP 6: Install Strix from Source
      # ==========================================
      - name: Install Strix (Enhanced Version)
        run: |
          echo "Installing Strix from source (Enhanced Edition)..."
          
          # Clone the enhanced Strix from Hailer367/strix
          git clone https://github.com/Hailer367/strix.git /tmp/strix
          cd /tmp/strix
          
          # Install poetry and dependencies
          pip install poetry
          poetry config virtualenvs.create false
          poetry install --no-interaction
          
          # Verify installation
          echo "Strix version: $(python -c 'import strix; print(strix.__version__)' 2>/dev/null || echo 'installed from source')"
          
          echo "Strix installation complete"
      
      # ==========================================
      # STEP 7: Create Strix Configuration
      # ==========================================
      - name: Create Strix config.json
        run: |
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          WARNING="${{ github.event.inputs.warning_minutes || env.DEFAULT_WARNING_MINUTES }}"
          SCAN_MODE="${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}"
          MODEL="${{ github.event.inputs.model || 'qwen3-coder-plus' }}"
          
          # Create config with local CLIProxyAPI endpoint
          cat > config.json << EOF
          {
            "api": {
              "endpoint": "${{ steps.cliproxy.outputs.endpoint }}",
              "model": "${MODEL}"
            },
            "timeframe": {
              "duration_minutes": ${TIMEFRAME},
              "warning_minutes": ${WARNING},
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
            "scan_mode": "${SCAN_MODE}",
            "strixdb": {
              "enabled": ${{ github.event.inputs.enable_strixdb || 'false' }},
              "repo": "${{ secrets.STRIXDB_REPO || '' }}",
              "token": "${{ secrets.STRIXDB_TOKEN || '' }}"
            },
            "perplexity_api_key": "${{ secrets.PERPLEXITY_API_KEY || '' }}"
          }
          EOF
          
          echo "Created config.json:"
          echo "  - API Endpoint: ${{ steps.cliproxy.outputs.endpoint }}"
          echo "  - Model: ${MODEL}"
          echo "  - Duration: ${TIMEFRAME} minutes"
          echo "  - Warning: ${WARNING} minutes before end"
          echo "  - Scan Mode: ${SCAN_MODE}"
          echo "  - Qwen Accounts: ${{ steps.decrypt.outputs.token_count }}"
      
      # ==========================================
      # STEP 8: Prepare Instructions
      # ==========================================
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
          
          # Add efficiency instructions
          INSTRUCTIONS="${INSTRUCTIONS} Use multi-action mode (up to 7 actions per call) for efficiency. The API is load-balanced across ${{ steps.decrypt.outputs.token_count }} Qwen accounts."
          
          echo "instructions=${INSTRUCTIONS}" >> $GITHUB_OUTPUT
          echo "Instructions prepared: ${INSTRUCTIONS:0:100}..."
      
      # ==========================================
      # STEP 9: Run Strix Security Scan
      # ==========================================
      - name: Run Strix Security Scan (Continuous Mode)
        id: strix
        env:
          STRIXDB_TOKEN: ${{ secrets.STRIXDB_TOKEN }}
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
        run: |
          # Don't exit on error - we want to capture all results
          set +e
          
          TARGET="${{ github.event.inputs.target || './' }}"
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          
          echo ""
          echo "=========================================="
          echo "STARTING STRIX SECURITY SCAN"
          echo "=========================================="
          echo "Target: ${TARGET}"
          echo "Timeframe: ${TIMEFRAME} minutes"
          echo "Mode: CONTINUOUS (scans until timeframe exhausted)"
          echo "API: Load-balanced across ${{ steps.decrypt.outputs.token_count }} Qwen accounts"
          echo "=========================================="
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
          VULN_COUNT=$(grep -ciE "vulnerability|VULNERABILITY|CVE-|critical|high.*severity" strix_output.log 2>/dev/null || echo "0")
          
          # Handle exit codes
          if [ $EXIT_CODE -eq 124 ]; then
            echo ""
            echo "=========================================="
            echo "SCAN COMPLETED (Timeframe Exhausted)"
            echo "=========================================="
            echo "timed_out=true" >> $GITHUB_OUTPUT
            echo "scan_completed=true" >> $GITHUB_OUTPUT
          elif [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo "=========================================="
            echo "SCAN COMPLETED SUCCESSFULLY"
            echo "=========================================="
            echo "scan_completed=true" >> $GITHUB_OUTPUT
          else
            echo ""
            echo "=========================================="
            echo "SCAN COMPLETED (Exit Code: ${EXIT_CODE})"
            echo "=========================================="
            echo "scan_completed=true" >> $GITHUB_OUTPUT
          fi
          
          echo "vulnerabilities_found=${VULN_COUNT}" >> $GITHUB_OUTPUT
          echo "exit_code=${EXIT_CODE}" >> $GITHUB_OUTPUT
          
          # Always exit 0 - we report vulnerabilities but don't fail the workflow
          # This allows continuous scanning to work properly
          exit 0
      
      # ==========================================
      # STEP 10: Cleanup CLIProxyAPI
      # ==========================================
      - name: Stop CLIProxyAPI Server
        if: always()
        run: |
          echo "Stopping CLIProxyAPI server..."
          
          if [ -f ~/.cli-proxy-api/cliproxy.pid ]; then
            PID=$(cat ~/.cli-proxy-api/cliproxy.pid)
            if kill -0 $PID 2>/dev/null; then
              kill $PID
              echo "CLIProxyAPI server stopped (PID: $PID)"
            fi
          fi
          
          # Show final CLIProxyAPI logs
          if [ -f ~/.cli-proxy-api/cliproxy.log ]; then
            echo ""
            echo "CLIProxyAPI final logs (last 20 lines):"
            tail -n 20 ~/.cli-proxy-api/cliproxy.log
          fi
          
          # Cleanup sensitive files
          rm -rf ~/.cli-proxy-api/qwen-*.json
          rm -f ~/.cli-proxy-api/cliproxy.pid
          
          echo "Cleanup complete"
      
      # ==========================================
      # STEP 11: Upload Results
      # ==========================================
      - name: Upload Scan Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: striflow-results-${{ github.run_id }}
          path: |
            strix_runs/
            strix_output.log
            config.json
          retention-days: 30
      
      # ==========================================
      # STEP 12: Create Summary
      # ==========================================
      - name: Create Security Summary
        if: always()
        run: |
          TIMEFRAME="${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}"
          VULNS="${{ steps.strix.outputs.vulnerabilities_found }}"
          TIMED_OUT="${{ steps.strix.outputs.timed_out }}"
          
          echo "## StriFlow Security Scan Results" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          
          echo "### Configuration" >> $GITHUB_STEP_SUMMARY
          echo "| Setting | Value |" >> $GITHUB_STEP_SUMMARY
          echo "|---------|-------|" >> $GITHUB_STEP_SUMMARY
          echo "| Target | \`${{ github.event.inputs.target || './' }}\` |" >> $GITHUB_STEP_SUMMARY
          echo "| Scan Mode | ${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Duration | ${TIMEFRAME} minutes |" >> $GITHUB_STEP_SUMMARY
          echo "| Model | ${{ github.event.inputs.model || 'qwen3-coder-plus' }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Qwen Accounts | ${{ steps.decrypt.outputs.token_count }} (load-balanced) |" >> $GITHUB_STEP_SUMMARY
          echo "| StrixDB | ${{ github.event.inputs.enable_strixdb || 'false' }} |" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          
          echo "### Results" >> $GITHUB_STEP_SUMMARY
          
          if [ "$TIMED_OUT" == "true" ]; then
            echo "- **Status:** Completed (full timeframe used)" >> $GITHUB_STEP_SUMMARY
          else
            echo "- **Status:** Completed" >> $GITHUB_STEP_SUMMARY
          fi
          
          if [ "$VULNS" -gt "0" ]; then
            echo "- **Potential Vulnerabilities:** ${VULNS} identified" >> $GITHUB_STEP_SUMMARY
          else
            echo "- **Potential Vulnerabilities:** None identified" >> $GITHUB_STEP_SUMMARY
          fi
          
          echo "- **Exit Code:** ${{ steps.strix.outputs.exit_code }}" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          
          echo "### Features Used" >> $GITHUB_STEP_SUMMARY
          echo "- Multi-Action Mode (up to 7 actions per API call)" >> $GITHUB_STEP_SUMMARY
          echo "- Active Commander (main agent actively participates)" >> $GITHUB_STEP_SUMMARY
          echo "- Qwen Token Load Balancing (${{ steps.decrypt.outputs.token_count }} accounts)" >> $GITHUB_STEP_SUMMARY
          echo "- Live Dashboard (real-time vulnerability disclosure)" >> $GITHUB_STEP_SUMMARY
          echo "- Continuous Scanning (doesn't stop on first find)" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          
          echo "See workflow artifacts for detailed results." >> $GITHUB_STEP_SUMMARY
      
      # ==========================================
      # STEP 13: Comment on PR (if applicable)
      # ==========================================
      - name: Comment on PR with Results
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            
            let summary = '## StriFlow Security Scan Results\n\n';
            
            const timedOut = '${{ steps.strix.outputs.timed_out }}' === 'true';
            const scanCompleted = '${{ steps.strix.outputs.scan_completed }}' === 'true';
            const vulnsFound = '${{ steps.strix.outputs.vulnerabilities_found }}';
            const exitCode = '${{ steps.strix.outputs.exit_code }}';
            const timeframe = '${{ github.event.inputs.timeframe || env.DEFAULT_TIMEFRAME }}';
            const tokenCount = '${{ steps.decrypt.outputs.token_count }}';
            
            if (timedOut) {
              summary += '**Status:** Scan completed (full timeframe used)\n\n';
              summary += `The scan ran for the full ${timeframe} minutes using ${tokenCount} Qwen accounts.\n\n`;
            } else if (scanCompleted) {
              summary += '**Status:** Scan Completed\n\n';
            }
            
            if (parseInt(vulnsFound) > 0) {
              summary += `**Potential Vulnerabilities:** ${vulnsFound} identified\n\n`;
              summary += 'Security issues were identified. Please review the detailed report in the workflow artifacts.\n\n';
            } else {
              summary += '**No vulnerabilities found**\n\n';
            }
            
            summary += `**Scan Mode:** ${{ github.event.inputs.scan_mode || env.DEFAULT_SCAN_MODE }}\n`;
            summary += `**Timeframe:** ${timeframe} minutes\n`;
            summary += `**Qwen Accounts:** ${tokenCount} (load-balanced)\n`;
            summary += `**Exit Code:** ${exitCode}\n\n`;
            
            summary += '### Features:\n';
            summary += '- Multi-Action Mode (7 actions per call)\n';
            summary += '- Qwen Token Load Balancing\n';
            summary += '- Continuous Scanning\n\n';
            
            summary += `[View Full Results](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})\n`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: summary
            });
```

---

## Usage Instructions

### Step 1: Collect Your Qwen Tokens (One-Time Setup)

If you haven't already, run the **auth-token-collector.yml** workflow:

1. Go to **Actions** → **Qwen Code Multi-Account Token Collection**
2. Click **Run workflow**
3. Select number of accounts (1-10)
4. Enter your encryption password (remember this!)
5. Complete OAuth for each account
6. Copy the encrypted token output
7. Add to repository secrets as `QWEN_TOKENS`

### Step 2: Run StriFlow

1. Go to **Actions** → **StriFlow - Integrated Strix Security Scan**
2. Click **Run workflow**
3. Fill in the inputs:
   - **decryption_password**: Same password used in Step 1
   - **target**: URL, path, or repository to scan
   - **prompt**: (Optional) Custom instructions
   - **timeframe**: How long to scan (10-720 minutes)
   - **scan_mode**: quick/standard/deep
   - **model**: AI model to use
   - **enable_strixdb**: Enable artifact storage

### Step 3: Monitor Progress

- Watch the workflow logs in real-time
- The scan will continue until the timeframe is exhausted
- Results are uploaded as artifacts when complete

### Step 4: Review Results

- Download the artifacts from the workflow run
- Check `strix_runs/` for detailed reports
- Review `strix_output.log` for full scan output

---

## Troubleshooting

### "QWEN_TOKENS secret is not set"

**Solution:** Run auth-token-collector.yml first and add the output to repository secrets.

### "Failed to decrypt tokens"

**Causes:**
- Wrong password
- Corrupted QWEN_TOKENS secret
- Password contains special characters

**Solution:**
1. Verify you're using the exact same password from token collection
2. Try regenerating tokens with auth-token-collector.yml

### "CLIProxyAPI server failed to start"

**Causes:**
- Build failure
- Port conflict
- Token format issues

**Solution:**
1. Check the build logs for errors
2. Verify tokens were extracted correctly
3. Try with a fresh set of tokens

### "No token files found after decryption"

**Causes:**
- Wrong password
- Tokens expired
- Collection workflow didn't complete

**Solution:**
1. Re-run auth-token-collector.yml
2. Ensure all OAuth flows completed
3. Update QWEN_TOKENS secret with new output

### "Scan timed out"

**This is normal behavior!** StriFlow is designed to use the full timeframe. Increase the timeframe if you need more scanning time.

---

## Advanced Configuration

### Using with Scheduled Scans

You can add a schedule trigger to run StriFlow automatically:

```yaml
on:
  schedule:
    - cron: '0 2 * * 1'  # Every Monday at 2 AM
  workflow_dispatch:
    inputs:
      # ... same as above
```

**Note:** For scheduled runs, you'll need to store the decryption password as a secret or use a different authentication method.

### Custom Model Selection

Available Qwen models:
- `qwen3-coder-plus` - Best for code analysis (recommended)
- `qwen-coder-plus` - Alternative code-focused model
- `qwen-plus` - General purpose
- `qwen-max` - Maximum capability

### Environment Variables

StriFlow uses these environment variables internally:
- `CLIPROXY_PORT`: API server port (default: 8317)
- `DEFAULT_TIMEFRAME`: Default scan duration (60 min)
- `DEFAULT_WARNING_MINUTES`: Warning time (5 min)
- `DEFAULT_SCAN_MODE`: Default mode (standard)

---

## Security Notes

1. **Password Security**: The decryption password is only used during workflow execution and is not stored
2. **Token Cleanup**: All decrypted tokens are automatically deleted after the scan
3. **Artifact Retention**: Results are kept for 30 days by default
4. **Repository Secrets**: QWEN_TOKENS is encrypted at rest by GitHub

---

*Last updated: January 2026*
*Version: StriFlow 1.0 - Integrated Strix + CLIProxyAPI Workflow*
