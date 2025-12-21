"""
Dashboard Configuration Models

Pydantic models for dashboard configuration and scan parameters.
Enhanced with comprehensive Strix agent configuration options.

Modified: Qwen Code CLI is now the sole AI provider (Roo Code removed).

Designed for GitHub Actions CI/CD workflows with web dashboard interface.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# GitHub Actions environment detection
IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")
GITHUB_RUN_ID = os.getenv("GITHUB_RUN_ID", "")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "")


class AIProvider(str, Enum):
    """Supported AI providers - Qwen Code is the primary/default provider."""
    QWENCODE = "qwencode"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class AccessLevel(str, Enum):
    """Terminal access levels."""
    STANDARD = "standard"
    ELEVATED = "elevated"
    ROOT = "root"


class ScanStatus(str, Enum):
    """Scan execution status."""
    PENDING = "pending"
    CONFIGURING = "configuring"
    AUTHENTICATING = "authenticating"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class AuthStatus(str, Enum):
    """Authentication status for Qwen Code."""
    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    FAILED = "failed"


class ScanMode(str, Enum):
    """Scan operation modes."""
    BLACK_BOX = "black_box"  # External testing only
    WHITE_BOX = "white_box"  # Source code + external testing
    COMBINED = "combined"    # Full scope testing


class QwenCodeConfig(BaseModel):
    """Qwen Code CLI configuration - Primary AI Provider.
    
    Qwen Code offers:
    - 2,000 free requests per day (via Qwen OAuth in China)
    - 60 requests per minute rate limit
    - No token limits
    - Multiple endpoint options (DashScope, ModelScope, OpenRouter)
    
    For international users outside China:
    - Use OpenRouter for free tier (1,000 requests/day)
    - Use QwenBridge proxy solution for full 2,000 requests
    - Or configure VPN to access qwen.ai directly
    """
    enabled: bool = True
    model: str = "qwen3-coder-plus"
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: float | None = None
    user_email: str | None = None
    user_id: str | None = None
    api_endpoint: str | None = None  # DashScope, ModelScope, OpenRouter, etc.
    auto_authenticate: bool = True
    auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED
    # Provider type for different API endpoints
    api_provider: str = "qwen_oauth"  # qwen_oauth, dashscope, modelscope, openrouter


class AIConfig(BaseModel):
    """AI provider configuration - Qwen Code is the default provider."""
    provider: AIProvider = AIProvider.QWENCODE
    model: str = "qwen3-coder-plus"
    api_key: str | None = None
    api_base: str | None = None
    qwencode: QwenCodeConfig = Field(default_factory=QwenCodeConfig)
    timeout: int = 600
    max_retries: int = 3
    enable_prompt_caching: bool = True


class AccessConfig(BaseModel):
    """Access control configuration."""
    level: AccessLevel = AccessLevel.ROOT
    allow_package_install: bool = True
    allow_tool_download: bool = True
    allow_network_config: bool = True
    allow_system_modification: bool = True
    command_timeout: int = 600


class TargetConfig(BaseModel):
    """Target configuration."""
    primary: str
    additional: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    scope_includes: list[str] = Field(default_factory=list)
    scope_excludes: list[str] = Field(default_factory=list)


class TestingConfig(BaseModel):
    """Testing parameters configuration."""
    instructions: str = ""
    focus_areas: list[str] = Field(default_factory=list)
    credentials: dict[str, str] = Field(default_factory=dict)
    max_iterations: int = 300
    duration_minutes: int = 60
    # Agent configuration options
    enable_multi_agent: bool = True
    max_sub_agents: int = 5
    enable_browser_automation: bool = True
    enable_proxy_interception: bool = True
    enable_web_search: bool = True
    aggressive_mode: bool = False
    stealth_mode: bool = False
    rate_limit_rps: int = 10
    # Scan mode
    scan_mode: ScanMode = ScanMode.BLACK_BOX


class OutputConfig(BaseModel):
    """Output and reporting configuration."""
    format: str = "markdown"  # json, markdown, html
    severity_threshold: str = "info"  # critical, high, medium, low, info
    notification_webhook: str | None = None
    save_artifacts: bool = True
    include_screenshots: bool = True
    include_poc: bool = True
    export_sarif: bool = False


class AgentBehaviorConfig(BaseModel):
    """Advanced agent behavior configuration."""
    # Planning and strategy
    planning_depth: str = "thorough"  # quick, balanced, thorough
    auto_pivot: bool = True
    chain_attacks: bool = True
    
    # Tool preferences
    preferred_tools: list[str] = Field(default_factory=list)
    disabled_tools: list[str] = Field(default_factory=list)
    
    # Memory and context
    memory_strategy: str = "adaptive"  # minimal, adaptive, full
    context_window_usage: int = 80  # percentage
    
    # Interaction style
    verbosity: str = "normal"  # quiet, normal, verbose
    explain_reasoning: bool = True
    
    # Safety and limits
    max_request_size_kb: int = 1024
    max_response_wait_seconds: int = 60
    stop_on_critical: bool = False


class GitHubActionsConfig(BaseModel):
    """GitHub Actions specific configuration."""
    is_github_actions: bool = IS_GITHUB_ACTIONS
    repository: str = GITHUB_REPOSITORY
    run_id: str = GITHUB_RUN_ID
    workflow: str = GITHUB_WORKFLOW
    # Artifact upload
    upload_artifacts: bool = True
    artifact_retention_days: int = 30
    # Notification
    create_issue_on_critical: bool = False
    notify_on_completion: bool = True


class ScanConfig(BaseModel):
    """Complete scan configuration."""
    ai: AIConfig = Field(default_factory=AIConfig)
    access: AccessConfig = Field(default_factory=AccessConfig)
    targets: TargetConfig
    testing: TestingConfig = Field(default_factory=TestingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    behavior: AgentBehaviorConfig = Field(default_factory=AgentBehaviorConfig)
    github_actions: GitHubActionsConfig = Field(default_factory=GitHubActionsConfig)
    
    # Metadata
    run_id: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: ScanStatus = ScanStatus.PENDING


@dataclass
class DashboardConfig:
    """Dashboard server configuration."""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    session_token: str | None = None
    config_file: str = "/tmp/strix_scan_config.json"
    ready_file: str = "/tmp/strix_config_ready"
    auth_callback_port: int = 18766  # Qwen Code callback port
    
    # Feature flags
    enable_qwencode_auth: bool = True
    enable_root_access: bool = True
    enable_custom_tools: bool = True
    enable_advanced_config: bool = True
    
    # Limits
    max_duration_minutes: int = 480  # 8 hours
    max_targets: int = 10
    max_instructions_length: int = 10000
    
    # OAuth configuration - Qwen Code CLI
    qwencode_auth_url: str = "https://chat.qwen.ai"
    qwencode_api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwencode_intl_api_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwencode_openrouter_url: str = "https://openrouter.ai/api/v1"
    qwencode_modelscope_url: str = "https://api-inference.modelscope.cn/v1"
    
    # GitHub Actions integration
    is_github_actions: bool = IS_GITHUB_ACTIONS


@dataclass
class DashboardState:
    """Runtime state for the dashboard."""
    config: ScanConfig | None = None
    status: ScanStatus = ScanStatus.PENDING
    auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED
    findings: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    progress: int = 0
    current_action: str = "Waiting for configuration"
    connected_clients: int = 0
    start_time: datetime | None = None
    
    # Qwen Code authentication state
    qwencode_user_email: str | None = None
    qwencode_user_id: str | None = None
    qwencode_access_token: str | None = None
    qwencode_refresh_token: str | None = None
    qwencode_token_expires_at: float | None = None
    qwencode_api_endpoint: str | None = None
    qwencode_api_provider: str = "qwen_oauth"  # qwen_oauth, dashscope, modelscope, openrouter
    
    # OAuth callback state
    oauth_state: str | None = None
    oauth_code_verifier: str | None = None
    
    # GitHub Actions context
    github_run_id: str = GITHUB_RUN_ID
    github_repository: str = GITHUB_REPOSITORY
    
    # Scan metrics
    vulnerabilities_found: int = 0
    endpoints_tested: int = 0
    requests_made: int = 0
    time_elapsed_seconds: int = 0


# Default vulnerability focus areas
DEFAULT_FOCUS_AREAS = [
    "sqli",         # SQL Injection
    "xss",          # Cross-Site Scripting
    "xxe",          # XML External Entity
    "ssrf",         # Server-Side Request Forgery
    "idor",         # Insecure Direct Object Reference
    "auth_bypass",  # Authentication Bypass
    "rce",          # Remote Code Execution
    "lfi",          # Local File Inclusion
    "rfi",          # Remote File Inclusion
    "csrf",         # Cross-Site Request Forgery
    "ssti",         # Server-Side Template Injection
    "deserialization",  # Insecure Deserialization
    "business_logic",   # Business Logic Flaws
    "info_disclosure",  # Information Disclosure
    "misconfig",        # Security Misconfiguration
    "broken_access",    # Broken Access Control
    "crypto_failures",  # Cryptographic Failures
    "injection",        # Other Injection Vulnerabilities
    "security_headers", # Missing Security Headers
    "api_security",     # API Security Issues
]


# Focus area descriptions for the dashboard
FOCUS_AREA_DESCRIPTIONS = {
    "sqli": "SQL Injection - Database query manipulation",
    "xss": "Cross-Site Scripting - Script injection in browsers",
    "xxe": "XML External Entity - XML parser exploitation",
    "ssrf": "Server-Side Request Forgery - Internal network access",
    "idor": "Insecure Direct Object Reference - Authorization bypass",
    "auth_bypass": "Authentication Bypass - Login circumvention",
    "rce": "Remote Code Execution - Server-side code execution",
    "lfi": "Local File Inclusion - Server file access",
    "rfi": "Remote File Inclusion - Remote file execution",
    "csrf": "Cross-Site Request Forgery - Action hijacking",
    "ssti": "Server-Side Template Injection - Template exploitation",
    "deserialization": "Insecure Deserialization - Object injection",
    "business_logic": "Business Logic Flaws - Process manipulation",
    "info_disclosure": "Information Disclosure - Sensitive data exposure",
    "misconfig": "Security Misconfiguration - System hardening issues",
    "broken_access": "Broken Access Control - Permission bypass",
    "crypto_failures": "Cryptographic Failures - Weak encryption",
    "injection": "Other Injection - Command, LDAP, etc.",
    "security_headers": "Missing Security Headers - Browser protections",
    "api_security": "API Security Issues - REST/GraphQL vulnerabilities",
}


# Qwen Code CLI models - Primary AI models for Strix
# Reference: https://github.com/QwenLM/qwen-code
QWENCODE_MODELS: dict = {
    "qwen3-coder-plus": {
        "name": "qwen3-coder-plus",
        "display_name": "Qwen3 Coder Plus",
        "description": "High-performance coding model optimized for complex tasks - 262K context",
        "context_window": 262000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat", "vision", "analysis"],
        "speed": "fast",
        "endpoint": "dashscope",
    },
    "qwen3-coder-plus-latest": {
        "name": "qwen3-coder-plus-latest",
        "display_name": "Qwen3 Coder Plus (Latest)",
        "description": "Latest version of Qwen3 coding model with newest improvements",
        "context_window": 262000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat", "vision", "analysis"],
        "speed": "fast",
        "endpoint": "dashscope",
    },
    "qwen3-coder": {
        "name": "qwen3-coder",
        "display_name": "Qwen3 Coder",
        "description": "Balanced coding model for general development tasks - 131K context",
        "context_window": 131000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat"],
        "speed": "fast",
        "endpoint": "dashscope",
    },
    "Qwen/Qwen3-Coder-480B-A35B-Instruct": {
        "name": "Qwen/Qwen3-Coder-480B-A35B-Instruct",
        "display_name": "Qwen3 Coder 480B (ModelScope)",
        "description": "Qwen3 Coder 480B model via ModelScope - 2,000 free calls/day in China",
        "context_window": 256000,
        "free": True,
        "provider": "modelscope",
        "capabilities": ["code", "chat", "analysis", "vision"],
        "speed": "moderate",
        "endpoint": "modelscope",
    },
    "qwen/qwen3-coder:free": {
        "name": "qwen/qwen3-coder:free",
        "display_name": "Qwen3 Coder (OpenRouter Free)",
        "description": "Qwen3 Coder via OpenRouter - 1,000 free calls/day worldwide",
        "context_window": 128000,
        "free": True,
        "provider": "openrouter",
        "capabilities": ["code", "chat"],
        "speed": "fast",
        "endpoint": "openrouter",
    },
}


# Planning depth descriptions
PLANNING_DEPTHS = {
    "quick": "Fast reconnaissance with targeted vulnerability checks",
    "balanced": "Comprehensive testing with moderate depth analysis",
    "thorough": "Deep analysis with extensive validation and chained attacks",
}


# Memory strategies with detailed descriptions
MEMORY_STRATEGIES = {
    "minimal": "Minimal context retention - faster but may miss connections. Best for simple targets.",
    "adaptive": "Automatically adjusts based on complexity. Recommended for most scans.",
    "full": "Maximum context retention - slower but most thorough. Best for complex targets.",
}


# Severity levels for filtering
SEVERITY_LEVELS = ["critical", "high", "medium", "low", "info"]

# Severity level colors for dashboard
SEVERITY_COLORS = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "medium": "#d97706",
    "low": "#2563eb",
    "info": "#6b7280",
}


# Output formats
OUTPUT_FORMATS = {
    "json": "JSON format - Machine readable",
    "markdown": "Markdown format - Human readable",
    "html": "HTML format - Interactive report",
    "sarif": "SARIF format - IDE/CI integration",
}


# Scan modes with descriptions
SCAN_MODES = {
    "black_box": "Black Box - External testing only (web application)",
    "white_box": "White Box - Source code analysis + testing",
    "combined": "Combined - Full scope testing with source and live app",
}


# API Endpoint options for international users
API_ENDPOINTS = {
    "qwen_oauth": {
        "name": "Qwen OAuth (Direct)",
        "description": "Direct authentication via qwen.ai - 2,000 requests/day (requires China access)",
        "url": "https://chat.qwen.ai/api/v1",
        "free_tier": "2,000 requests/day",
        "requires_china_access": True,
    },
    "dashscope": {
        "name": "Alibaba Cloud DashScope (China)",
        "description": "Alibaba Cloud API for China users",
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "free_tier": "Pay-as-you-go with free credits",
        "requires_china_access": True,
    },
    "dashscope_intl": {
        "name": "Alibaba Cloud DashScope (International)",
        "description": "Alibaba Cloud API for international users",
        "url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "free_tier": "Pay-as-you-go with free credits",
        "requires_china_access": False,
    },
    "modelscope": {
        "name": "ModelScope (China)",
        "description": "ModelScope API - 2,000 free calls/day in China",
        "url": "https://api-inference.modelscope.cn/v1",
        "free_tier": "2,000 requests/day",
        "requires_china_access": True,
    },
    "openrouter": {
        "name": "OpenRouter (Worldwide)",
        "description": "OpenRouter API - 1,000 free calls/day worldwide",
        "url": "https://openrouter.ai/api/v1",
        "free_tier": "1,000 requests/day",
        "requires_china_access": False,
    },
}
