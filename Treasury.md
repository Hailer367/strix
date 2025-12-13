# Strix Treasury

## Complete Tool Reference Guide

This document provides comprehensive documentation for all tools available to the Strix AI agent during penetration testing and bug bounty operations.

---

## Table of Contents

- [Terminal Tools](#terminal-tools)
- [Browser Automation Tools](#browser-automation-tools)
- [HTTP Proxy Tools](#http-proxy-tools)
- [Python Runtime Tools](#python-runtime-tools)
- [File System Tools](#file-system-tools)
- [Notes & Knowledge Tools](#notes--knowledge-tools)
- [Reporting Tools](#reporting-tools)
- [Web Search Tools](#web-search-tools)
- [Multi-Agent Tools](#multi-agent-tools)
- [Scan Control Tools](#scan-control-tools)

---

## Terminal Tools

The terminal tools provide command execution capabilities within the sandboxed Docker container. With root access enabled, these tools can execute any command including package installation and system modifications.

### `terminal_execute`

Execute commands in the terminal with full control over the execution environment.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | string | Yes | - | The command to execute |
| `is_input` | boolean | No | `false` | Whether this is input to a running command |
| `timeout` | float | No | `300` | Command timeout in seconds |
| `terminal_id` | string | No | `"default"` | Terminal session ID |
| `no_enter` | boolean | No | `false` | Don't press enter after command |
| `use_sudo` | boolean | No | `false` | Explicitly prepend sudo to the command |

#### Returns

```python
{
    "content": str,        # Command output
    "exit_code": int,      # Exit code (0 = success)
    "working_dir": str,    # Current working directory
    "terminal_id": str,    # Terminal session ID
    "status": str,         # "success" or "error"
    "root_access": {
        "root_access_enabled": bool,
        "access_level": str,
        "command_timeout": int
    }
}
```

#### Examples

```python
# Basic command execution
terminal_execute(command="ls -la /workspace")

# Install a security tool (requires root access)
terminal_execute(command="apt-get install -y nikto", use_sudo=True)

# Run nmap scan with timeout
terminal_execute(
    command="nmap -sV -sC target.com",
    timeout=600
)

# Execute in specific terminal session
terminal_execute(
    command="python3 exploit.py",
    terminal_id="exploit-session"
)

# Send input to running process
terminal_execute(
    command="y",
    is_input=True,
    terminal_id="interactive-session"
)
```

#### Use Cases

- Running security scanning tools (nmap, nikto, nuclei, etc.)
- Installing additional packages and tools
- Compiling custom exploits
- Network reconnaissance
- File manipulation and analysis
- System configuration (with root access)

---

### `terminal_get_root_status`

Get the current root access status and configuration.

#### Parameters

None

#### Returns

```python
{
    "root_access_enabled": bool,
    "access_level": str,  # "standard", "elevated", or "root"
    "command_timeout": int,
    "capabilities": {
        "can_install_packages": bool,
        "can_download_tools": bool,
        "can_modify_network": bool,
        "can_modify_system": bool,
        "can_use_sudo": bool
    },
    "available_package_managers": list[str],
    "note": str
}
```

#### Example

```python
# Check what capabilities are available
status = terminal_get_root_status()
if status["capabilities"]["can_install_packages"]:
    terminal_execute(command="pip install custom-tool")
```

---

## Browser Automation Tools

Browser automation tools provide full control over a headless browser for testing client-side vulnerabilities, authentication flows, and web application behavior.

### `browser_action`

Execute browser automation actions for web testing.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | The action to perform (see Actions table) |
| `url` | string | For `launch`, `goto` | URL to navigate to |
| `coordinate` | string | For click actions | Click coordinates (e.g., "100,200") |
| `text` | string | For `type` | Text to type |
| `tab_id` | string | No | Target tab ID |
| `js_code` | string | For `execute_js` | JavaScript code to execute |
| `duration` | float | For `wait` | Wait duration in seconds |
| `key` | string | For `press_key` | Key to press |
| `file_path` | string | For `save_pdf` | File path for PDF output |
| `clear` | boolean | No | Clear console logs after retrieval |

#### Actions

| Action | Description | Required Parameters |
|--------|-------------|---------------------|
| `launch` | Launch browser instance | `url` (optional) |
| `goto` | Navigate to URL | `url` |
| `click` | Click at coordinates | `coordinate` |
| `double_click` | Double-click at coordinates | `coordinate` |
| `hover` | Hover at coordinates | `coordinate` |
| `type` | Type text | `text` |
| `press_key` | Press keyboard key | `key` |
| `scroll_down` | Scroll page down | - |
| `scroll_up` | Scroll page up | - |
| `back` | Navigate back | - |
| `forward` | Navigate forward | - |
| `new_tab` | Open new tab | `url` (optional) |
| `switch_tab` | Switch to tab | `tab_id` |
| `close_tab` | Close tab | `tab_id` |
| `list_tabs` | List all tabs | - |
| `wait` | Wait for duration | `duration` |
| `execute_js` | Execute JavaScript | `js_code` |
| `get_console_logs` | Get browser console logs | `clear` (optional) |
| `view_source` | View page source | - |
| `save_pdf` | Save page as PDF | `file_path` |
| `close` | Close browser | - |

#### Returns

```python
{
    "tab_id": str,
    "url": str,
    "title": str,
    "screenshot": str,  # Base64 encoded screenshot
    "is_running": bool,
    "error": str | None,
    # Additional fields based on action
}
```

#### Examples

```python
# Launch browser and navigate
browser_action(action="launch", url="https://target.com")

# Fill login form
browser_action(action="type", text="admin@test.com")
browser_action(action="press_key", key="Tab")
browser_action(action="type", text="password123")

# Click login button
browser_action(action="click", coordinate="500,350")

# Execute JavaScript for XSS testing
browser_action(
    action="execute_js",
    js_code="alert(document.cookie)"
)

# Get console logs for debugging
result = browser_action(action="get_console_logs", clear=True)

# Multi-tab testing
browser_action(action="new_tab", url="https://target.com/admin")
browser_action(action="switch_tab", tab_id="tab_1")
```

#### Use Cases

- Testing XSS vulnerabilities
- Authentication flow testing
- CSRF attack validation
- Session management testing
- DOM-based vulnerability testing
- Screenshot capture for PoCs
- JavaScript injection testing

---

## HTTP Proxy Tools

HTTP proxy tools provide complete control over HTTP traffic, enabling request interception, modification, and replay attacks.

### `list_requests`

List captured HTTP requests with filtering and sorting options.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `httpql_filter` | string | No | - | HTTPQL filter query |
| `start_page` | int | No | 1 | Start page for pagination |
| `end_page` | int | No | 1 | End page for pagination |
| `page_size` | int | No | 50 | Results per page |
| `sort_by` | string | No | `"timestamp"` | Sort field |
| `sort_order` | string | No | `"desc"` | Sort order (`"asc"` or `"desc"`) |
| `scope_id` | string | No | - | Limit to specific scope |

#### Sort Fields

- `timestamp` - Request timestamp
- `host` - Target host
- `method` - HTTP method
- `path` - Request path
- `status_code` - Response status
- `response_time` - Response time
- `response_size` - Response size
- `source` - Request source

#### Returns

```python
{
    "requests": [
        {
            "id": str,
            "method": str,
            "host": str,
            "path": str,
            "status_code": int,
            "response_time": float,
            "response_size": int,
            "timestamp": str
        }
    ],
    "total_count": int,
    "page": int,
    "page_size": int
}
```

#### Examples

```python
# List all requests
list_requests()

# Filter for specific endpoints
list_requests(httpql_filter='path.cont:"/api/users"')

# Filter by status code
list_requests(httpql_filter='status_code.eq:401')

# Sort by response time to find slow endpoints
list_requests(sort_by="response_time", sort_order="desc")
```

---

### `view_request`

View detailed information about a specific HTTP request.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `request_id` | string | Yes | - | ID of the request to view |
| `part` | string | No | `"request"` | Part to view (`"request"` or `"response"`) |
| `search_pattern` | string | No | - | Pattern to highlight in response |
| `page` | int | No | 1 | Page for large responses |
| `page_size` | int | No | 50 | Lines per page |

#### Returns

```python
{
    "request_id": str,
    "part": str,
    "content": str,
    "headers": dict,
    "body": str,
    "metadata": {
        "method": str,
        "url": str,
        "status_code": int,
        "content_type": str
    }
}
```

#### Example

```python
# View full request details
view_request(request_id="req_abc123", part="request")

# Search for sensitive data in response
view_request(
    request_id="req_abc123",
    part="response",
    search_pattern="password|token|secret"
)
```

---

### `send_request`

Send a custom HTTP request.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `method` | string | Yes | - | HTTP method |
| `url` | string | Yes | - | Target URL |
| `headers` | dict | No | `{}` | Request headers |
| `body` | string | No | `""` | Request body |
| `timeout` | int | No | 30 | Request timeout |

#### Returns

```python
{
    "request_id": str,
    "status_code": int,
    "headers": dict,
    "body": str,
    "response_time": float
}
```

#### Examples

```python
# Simple GET request
send_request(method="GET", url="https://api.target.com/users")

# POST with JSON body
send_request(
    method="POST",
    url="https://api.target.com/login",
    headers={"Content-Type": "application/json"},
    body='{"username": "admin", "password": "test"}'
)

# SQLi testing
send_request(
    method="GET",
    url="https://target.com/user?id=1' OR '1'='1"
)
```

---

### `repeat_request`

Repeat a captured request with optional modifications.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `request_id` | string | Yes | - | ID of request to repeat |
| `modifications` | dict | No | `{}` | Modifications to apply |

#### Modifications Structure

```python
{
    "method": str,           # Change HTTP method
    "url": str,              # Change URL
    "headers": {
        "add": dict,         # Headers to add
        "remove": list,      # Headers to remove
        "modify": dict       # Headers to modify
    },
    "body": str,             # New request body
    "params": dict           # URL parameters
}
```

#### Example

```python
# Repeat with modified parameter (IDOR test)
repeat_request(
    request_id="req_abc123",
    modifications={
        "params": {"user_id": "2"}
    }
)

# Test with different authentication
repeat_request(
    request_id="req_abc123",
    modifications={
        "headers": {
            "modify": {"Authorization": "Bearer other_token"}
        }
    }
)
```

---

### `scope_rules`

Manage proxy scope rules for filtering traffic.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | Action: `"get"`, `"list"`, `"create"`, `"update"`, `"delete"` |
| `allowlist` | list | No | Patterns to allow |
| `denylist` | list | No | Patterns to deny |
| `scope_id` | string | No | Scope ID for specific operations |
| `scope_name` | string | No | Name for new scope |

#### Example

```python
# Create scope for target
scope_rules(
    action="create",
    scope_name="target_scope",
    allowlist=["*.target.com", "api.target.com"],
    denylist=["*.analytics.com"]
)

# List all scopes
scope_rules(action="list")
```

---

### `list_sitemap`

List sitemap entries discovered through proxy traffic.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scope_id` | string | No | - | Filter by scope |
| `parent_id` | string | No | - | Parent entry ID |
| `depth` | string | No | `"DIRECT"` | `"DIRECT"` or `"ALL"` |
| `page` | int | No | 1 | Page number |

#### Returns

```python
{
    "entries": [
        {
            "id": str,
            "url": str,
            "method": str,
            "has_params": bool,
            "request_count": int
        }
    ],
    "total_count": int
}
```

---

### `view_sitemap_entry`

View details of a specific sitemap entry.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entry_id` | string | Yes | Entry ID to view |

#### Returns

```python
{
    "id": str,
    "url": str,
    "methods": list[str],
    "parameters": list[str],
    "requests": list[dict],
    "discovered_at": str
}
```

---

## Python Runtime Tools

Python runtime tools provide a sandboxed Python environment for custom exploit development and validation.

### `python_action`

Execute Python code or manage Python sessions.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | Yes | - | Action to perform |
| `code` | string | For `execute` | - | Python code to execute |
| `timeout` | int | No | 30 | Execution timeout |
| `session_id` | string | No | - | Session ID |

#### Actions

| Action | Description | Required Parameters |
|--------|-------------|---------------------|
| `new_session` | Create new Python session | - |
| `execute` | Execute Python code | `code` |
| `close` | Close session | `session_id` |
| `list_sessions` | List active sessions | - |

#### Returns

```python
{
    "session_id": str,
    "stdout": str,
    "stderr": str,
    "is_running": bool,
    "return_value": any
}
```

#### Examples

```python
# Create session and execute code
python_action(action="new_session", session_id="exploit-dev")

python_action(
    action="execute",
    session_id="exploit-dev",
    code='''
import requests

# Test for SQL injection
payload = "1' OR '1'='1"
response = requests.get(f"https://target.com/api/user?id={payload}")
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")
'''
)

# Create a custom exploit
python_action(
    action="execute",
    code='''
import base64
import json

def create_jwt_none_attack(payload):
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).decode().rstrip("=")
    
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip("=")
    
    return f"{header}.{body}."

token = create_jwt_none_attack({"user_id": 1, "role": "admin"})
print(f"Crafted JWT: {token}")
'''
)
```

#### Use Cases

- Custom exploit development
- Data parsing and analysis
- PoC automation
- Complex payload generation
- API testing scripts
- Cryptographic analysis

---

## File System Tools

File system tools provide capabilities for viewing, editing, and searching files within the workspace.

### `str_replace_editor`

View and edit files using string replacement operations.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | string | Yes | Command: `"view"`, `"create"`, `"str_replace"`, `"insert"` |
| `path` | string | Yes | File path |
| `file_text` | string | For `create` | Content for new file |
| `view_range` | list | For `view` | Line range [start, end] |
| `old_str` | string | For `str_replace` | String to replace |
| `new_str` | string | For `str_replace` | Replacement string |
| `insert_line` | int | For `insert` | Line number for insertion |

#### Examples

```python
# View file contents
str_replace_editor(command="view", path="/workspace/app/config.py")

# View specific line range
str_replace_editor(
    command="view",
    path="/workspace/app/config.py",
    view_range=[1, 50]
)

# Create a new file
str_replace_editor(
    command="create",
    path="/workspace/exploit.py",
    file_text='''#!/usr/bin/env python3
import requests

TARGET = "https://target.com"
# Exploit code here
'''
)

# Modify existing code
str_replace_editor(
    command="str_replace",
    path="/workspace/exploit.py",
    old_str='TARGET = "https://target.com"',
    new_str='TARGET = "https://api.target.com"'
)
```

---

### `list_files`

List files and directories in a path.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Directory path |
| `recursive` | boolean | No | `false` | List recursively |

#### Returns

```python
{
    "files": list[str],
    "directories": list[str],
    "total_files": int,
    "total_dirs": int,
    "path": str,
    "recursive": bool
}
```

#### Example

```python
# List workspace contents
list_files(path="/workspace")

# Recursive listing for code analysis
list_files(path="/workspace/app", recursive=True)
```

---

### `search_files`

Search for patterns in files using regular expressions.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Directory to search |
| `regex` | string | Yes | - | Regular expression pattern |
| `file_pattern` | string | No | `"*"` | File glob pattern |

#### Returns

```python
{
    "output": str,  # Matched lines with file paths and line numbers
    "error": str | None
}
```

#### Examples

```python
# Search for hardcoded credentials
search_files(
    path="/workspace",
    regex="password|secret|api_key|token",
    file_pattern="*.py"
)

# Find SQL queries
search_files(
    path="/workspace",
    regex="SELECT.*FROM|INSERT.*INTO|UPDATE.*SET",
    file_pattern="*.{py,js,php}"
)

# Find potential command injection
search_files(
    path="/workspace",
    regex="os\\.system|subprocess|exec\\(",
    file_pattern="*.py"
)
```

---

## Notes & Knowledge Tools

Note tools help organize findings, track progress, and document discoveries during security assessments.

### `create_note`

Create a new note for tracking findings and information.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | string | Yes | - | Note title |
| `content` | string | Yes | - | Note content |
| `category` | string | No | `"general"` | Category (see below) |
| `tags` | list | No | `[]` | Tags for organization |
| `priority` | string | No | `"normal"` | Priority level |

#### Categories

- `general` - General notes
- `findings` - Vulnerability findings
- `methodology` - Testing methodology
- `todo` - Tasks to complete
- `questions` - Questions to investigate
- `plan` - Attack planning

#### Priority Levels

- `low`
- `normal`
- `high`
- `urgent`

#### Example

```python
create_note(
    title="SQL Injection in /api/users",
    content='''
Found SQL injection vulnerability in the user search endpoint.

**Endpoint:** GET /api/users?search=
**Payload:** ' OR '1'='1
**Impact:** Full database access

**PoC:**
curl "https://target.com/api/users?search=' OR '1'='1"
''',
    category="findings",
    tags=["sqli", "critical", "api"],
    priority="urgent"
)
```

---

### `list_notes`

List notes with optional filtering.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `category` | string | No | - | Filter by category |
| `tags` | list | No | - | Filter by tags |
| `priority` | string | No | - | Filter by priority |
| `search` | string | No | - | Search in title/content |

#### Returns

```python
{
    "success": bool,
    "notes": list[dict],
    "total_count": int
}
```

#### Example

```python
# List all findings
list_notes(category="findings")

# Search for specific vulnerability
list_notes(search="SQL injection")

# Get urgent items
list_notes(priority="urgent")
```

---

### `update_note`

Update an existing note.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `note_id` | string | Yes | Note ID to update |
| `title` | string | No | New title |
| `content` | string | No | New content |
| `tags` | list | No | New tags |
| `priority` | string | No | New priority |

---

### `delete_note`

Delete a note.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `note_id` | string | Yes | Note ID to delete |

---

## Reporting Tools

Reporting tools create structured vulnerability reports for documentation.

### `create_vulnerability_report`

Create a formal vulnerability report.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|---------|
| `title` | string | Yes | Vulnerability title |
| `content` | string | Yes | Detailed description |
| `severity` | string | Yes | Severity level |

#### Severity Levels

- `critical` - CVSS 9.0-10.0
- `high` - CVSS 7.0-8.9
- `medium` - CVSS 4.0-6.9
- `low` - CVSS 0.1-3.9
- `info` - Informational

#### Returns

```python
{
    "success": bool,
    "message": str,
    "report_id": str,
    "severity": str
}
```

#### Example

```python
create_vulnerability_report(
    title="Remote Code Execution via Deserialization",
    content='''
## Summary
A critical deserialization vulnerability was discovered in the application's session handling mechanism.

## Affected Endpoint
POST /api/session/restore

## Technical Details
The application deserializes user-controlled data without proper validation using Python's pickle module.

## Proof of Concept
```python
import pickle
import base64
import os

class RCE:
    def __reduce__(self):
        return (os.system, ('id',))

payload = base64.b64encode(pickle.dumps(RCE())).decode()
# Send payload in session_data parameter
```

## Impact
- Remote code execution with application privileges
- Full server compromise possible
- Data exfiltration and modification

## Remediation
1. Never deserialize untrusted data
2. Use JSON or other safe serialization formats
3. Implement signature verification for serialized data

## CVSS Score
9.8 (Critical) - CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
''',
    severity="critical"
)
```

---

## Web Search Tools

Web search tools provide real-time intelligence gathering using Perplexity AI.

### `web_search`

Search the web for security-related information.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Search query |

#### Returns

```python
{
    "success": bool,
    "query": str,
    "content": str,
    "message": str
}
```

#### Example

```python
# Search for CVE information
web_search(query="CVE-2024-1234 exploit poc")

# Find security tool documentation
web_search(query="nuclei template sql injection")

# Research attack techniques
web_search(query="JWT algorithm confusion attack")

# Find default credentials
web_search(query="Apache Tomcat default credentials")
```

#### Use Cases

- CVE research and exploit finding
- Tool documentation lookup
- Attack technique research
- Default credential lookup
- Security advisory checking

---

## Multi-Agent Tools

Multi-agent tools enable creating, coordinating, and communicating with specialized sub-agents for complex assessments.

### `view_agent_graph`

View the current agent hierarchy and status.

#### Parameters

Requires `agent_state` (automatically provided)

#### Returns

```python
{
    "graph_structure": str,  # ASCII tree representation
    "summary": {
        "total_agents": int,
        "running": int,
        "waiting": int,
        "stopping": int,
        "completed": int,
        "stopped": int,
        "failed": int
    }
}
```

#### Example Output

```
=== AGENT GRAPH STRUCTURE ===
* RootAgent (agent_abc123) <- This is you
  Task: Comprehensive security assessment
  Status: running
   Children:
    * ReconAgent (agent_def456)
      Task: Subdomain enumeration
      Status: completed
    * VulnScanner (agent_ghi789)
      Task: SQL injection testing
      Status: running
```

---

### `create_agent`

Create a specialized sub-agent for delegated tasks.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task` | string | Yes | - | Task description for the agent |
| `name` | string | Yes | - | Agent name |
| `inherit_context` | boolean | No | `true` | Inherit parent's conversation context |
| `prompt_modules` | string | No | - | Comma-separated prompt modules |

#### Available Prompt Modules

**Vulnerabilities:**
- `vulnerabilities/sqli` - SQL Injection specialist
- `vulnerabilities/xss` - Cross-Site Scripting specialist
- `vulnerabilities/ssrf` - Server-Side Request Forgery
- `vulnerabilities/xxe` - XML External Entity
- `vulnerabilities/deserialization` - Insecure Deserialization

**Reconnaissance:**
- `reconnaissance/subdomain` - Subdomain enumeration
- `reconnaissance/port_scan` - Port scanning
- `reconnaissance/osint` - Open Source Intelligence

**Technologies:**
- `technologies/api` - API security testing
- `technologies/graphql` - GraphQL testing
- `technologies/websocket` - WebSocket testing

#### Returns

```python
{
    "success": bool,
    "agent_id": str,
    "message": str,
    "agent_info": {
        "id": str,
        "name": str,
        "status": str,
        "parent_id": str
    }
}
```

#### Example

```python
# Create SQL injection specialist
create_agent(
    task="Test all API endpoints for SQL injection vulnerabilities",
    name="SQLi-Specialist",
    prompt_modules="vulnerabilities/sqli"
)

# Create reconnaissance agent
create_agent(
    task="Enumerate all subdomains and identify technologies",
    name="Recon-Agent",
    prompt_modules="reconnaissance/subdomain"
)

# Create without context inheritance
create_agent(
    task="Fresh assessment of authentication endpoints",
    name="Auth-Tester",
    inherit_context=False
)
```

---

### `send_message_to_agent`

Send a message to another agent.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_agent_id` | string | Yes | - | Target agent ID |
| `message` | string | Yes | - | Message content |
| `message_type` | string | No | `"information"` | Type: `"query"`, `"instruction"`, `"information"` |
| `priority` | string | No | `"normal"` | Priority: `"low"`, `"normal"`, `"high"`, `"urgent"` |

#### Example

```python
# Share finding with parent
send_message_to_agent(
    target_agent_id="agent_parent123",
    message="Found SQL injection in /api/search endpoint",
    message_type="information",
    priority="high"
)

# Request specific action
send_message_to_agent(
    target_agent_id="agent_exploit456",
    message="Please develop PoC for the SSRF vulnerability at /proxy endpoint",
    message_type="instruction",
    priority="urgent"
)
```

---

### `wait_for_message`

Enter waiting state to receive messages from other agents.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `reason` | string | No | `"Waiting for messages..."` | Reason for waiting |

#### Example

```python
# Wait for sub-agents to complete
wait_for_message(reason="Waiting for reconnaissance results")
```

---

### `agent_finish`

Complete a sub-agent's task and report back to parent.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `result_summary` | string | Yes | - | Summary of results |
| `findings` | list | No | `[]` | List of findings |
| `success` | boolean | No | `true` | Whether task succeeded |
| `report_to_parent` | boolean | No | `true` | Send report to parent |
| `final_recommendations` | list | No | `[]` | Recommendations |

#### Example

```python
agent_finish(
    result_summary="SQL injection testing completed. Found 3 vulnerabilities.",
    findings=[
        "SQL injection in /api/users endpoint",
        "Blind SQL injection in /api/search",
        "Second-order SQL injection in profile update"
    ],
    success=True,
    final_recommendations=[
        "Use parameterized queries",
        "Implement input validation",
        "Add WAF rules for SQL injection patterns"
    ]
)
```

---

## Scan Control Tools

Scan control tools manage the overall security assessment lifecycle.

### `finish_scan`

Complete the security scan and generate final report.

**Note:** This can only be called by the root agent. Sub-agents must use `agent_finish`.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | Yes | - | Final report content |
| `success` | boolean | No | `true` | Whether scan succeeded |

#### Example

```python
finish_scan(
    content='''
# Security Assessment Report

## Executive Summary
A comprehensive security assessment was conducted against target.com. 
The assessment identified 5 critical, 8 high, 12 medium, and 20 low severity vulnerabilities.

## Critical Findings
1. Remote Code Execution via deserialization (CVE-2024-XXXX)
2. SQL Injection allowing database dump
3. Authentication bypass in admin panel
4. SSRF allowing internal network access
5. Insecure direct object reference exposing all user data

## Recommendations
1. Immediate patching of critical vulnerabilities
2. Implementation of WAF
3. Security code review of authentication modules
4. Regular penetration testing

## Detailed Findings
[See individual vulnerability reports]

## Conclusion
The application has significant security issues requiring immediate attention.
''',
    success=True
)
```

---

## Tool Chaining Examples

### Comprehensive Endpoint Testing

```python
# 1. Discover endpoints through proxy
list_requests(httpql_filter='path.cont:"/api/"')

# 2. Create note for tracking
create_note(
    title="API Endpoint Discovery",
    content="Found 15 API endpoints to test",
    category="plan"
)

# 3. Test each endpoint with Python
python_action(
    action="execute",
    code='''
import requests

endpoints = ["/api/users", "/api/orders", "/api/admin"]
for endpoint in endpoints:
    # SQL injection test
    response = requests.get(f"https://target.com{endpoint}?id=1'")
    if "error" in response.text.lower():
        print(f"Potential SQLi: {endpoint}")
'''
)

# 4. Document findings
create_vulnerability_report(
    title="SQL Injection in Multiple Endpoints",
    content="...",
    severity="high"
)
```

### Multi-Agent Reconnaissance

```python
# Root agent creates specialists
create_agent(
    task="Enumerate all subdomains for target.com",
    name="Subdomain-Enum",
    prompt_modules="reconnaissance/subdomain"
)

create_agent(
    task="Port scan discovered subdomains",
    name="Port-Scanner",
    prompt_modules="reconnaissance/port_scan"
)

# Wait for results
wait_for_message(reason="Waiting for reconnaissance completion")

# Review graph
view_agent_graph()
```

---

## Best Practices

### 1. Always Document Findings

```python
# Create notes during testing
create_note(
    title="Testing Progress",
    content="Current focus: Authentication endpoints",
    category="methodology"
)

# Create vulnerability reports immediately
create_vulnerability_report(...)
```

### 2. Use Appropriate Tool for the Job

| Task | Recommended Tool |
|------|------------------|
| Quick command execution | `terminal_execute` |
| Web interaction testing | `browser_action` |
| API testing | `send_request` / `python_action` |
| Complex exploitation | `python_action` |
| File analysis | `str_replace_editor` / `search_files` |
| Traffic analysis | `list_requests` / `view_request` |

### 3. Chain Tools Effectively

1. Use `list_requests` to understand traffic patterns
2. Use `view_request` to analyze interesting requests
3. Use `repeat_request` with modifications to test vulnerabilities
4. Use `python_action` for complex payload generation
5. Use `create_vulnerability_report` to document findings

### 4. Leverage Multi-Agent for Complex Tests

- Create specialized agents for different vulnerability types
- Use message passing for coordination
- Let agents work in parallel for faster coverage

### 5. Root Access Usage

```python
# Check capabilities first
status = terminal_get_root_status()

if status["capabilities"]["can_install_packages"]:
    # Install needed tool
    terminal_execute(command="apt-get install -y tool-name")
```

---

## Quick Reference Card

| Action | Tool | Key Parameters |
|--------|------|----------------|
| Run command | `terminal_execute` | `command` |
| Browse web | `browser_action` | `action`, `url` |
| Send HTTP | `send_request` | `method`, `url` |
| View traffic | `list_requests` | `httpql_filter` |
| Run Python | `python_action` | `action="execute"`, `code` |
| Edit file | `str_replace_editor` | `command`, `path` |
| Search code | `search_files` | `path`, `regex` |
| Take note | `create_note` | `title`, `content` |
| Report vuln | `create_vulnerability_report` | `title`, `content`, `severity` |
| Web search | `web_search` | `query` |
| Create agent | `create_agent` | `task`, `name` |
| Finish scan | `finish_scan` | `content` |

---

*This documentation is part of the Strix project. For more information, visit [usestrix.com](https://usestrix.com).*
