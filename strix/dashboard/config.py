"""
Dashboard Configuration Models

Pydantic models for dashboard configuration and scan parameters.
Enhanced with comprehensive Strix agent configuration options.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AIProvider(str, Enum):
    """Supported AI providers."""
    ROOCODE = "roocode"
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


class AuthStatus(str, Enum):
    """Authentication status for Roo Code."""
    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    FAILED = "failed"


class RooCodeConfig(BaseModel):
    """Roo Code Cloud configuration."""
    enabled: bool = True
    model: str = "grok-code-fast-1"
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: float | None = None
    user_email: str | None = None
    user_id: str | None = None
    auto_authenticate: bool = True
    auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED


class QwenCodeConfig(BaseModel):
    """Qwen Code CLI configuration."""
    enabled: bool = False
    model: str = "qwen3-coder-plus"
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: float | None = None
    user_email: str | None = None
    user_id: str | None = None
    api_endpoint: str | None = None
    auto_authenticate: bool = True
    auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED


class AIConfig(BaseModel):
    """AI provider configuration."""
    provider: AIProvider = AIProvider.ROOCODE
    model: str = "grok-code-fast-1"
    api_key: str | None = None
    api_base: str | None = None
    roocode: RooCodeConfig = Field(default_factory=RooCodeConfig)
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
    # New agent configuration options
    enable_multi_agent: bool = True
    max_sub_agents: int = 5
    enable_browser_automation: bool = True
    enable_proxy_interception: bool = True
    enable_web_search: bool = True
    aggressive_mode: bool = False
    stealth_mode: bool = False
    rate_limit_rps: int = 10


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


class ScanConfig(BaseModel):
    """Complete scan configuration."""
    ai: AIConfig = Field(default_factory=AIConfig)
    access: AccessConfig = Field(default_factory=AccessConfig)
    targets: TargetConfig
    testing: TestingConfig = Field(default_factory=TestingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    behavior: AgentBehaviorConfig = Field(default_factory=AgentBehaviorConfig)
    
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
    auth_callback_port: int = 18765
    
    # Feature flags
    enable_roocode_auth: bool = True
    enable_qwencode_auth: bool = True
    enable_root_access: bool = True
    enable_custom_tools: bool = True
    enable_advanced_config: bool = True
    
    # Limits
    max_duration_minutes: int = 480  # 8 hours
    max_targets: int = 10
    max_instructions_length: int = 10000
    
    # OAuth configuration - Roo Code
    roocode_auth_url: str = "https://app.roocode.com"
    roocode_api_url: str = "https://api.roocode.com"
    
    # OAuth configuration - Qwen Code CLI
    qwencode_auth_url: str = "https://chat.qwen.ai"
    qwencode_api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwencode_auth_callback_port: int = 18766


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
    
    # Roo Code authentication state
    roocode_user_email: str | None = None
    roocode_user_id: str | None = None
    roocode_access_token: str | None = None
    roocode_refresh_token: str | None = None
    roocode_token_expires_at: float | None = None
    
    # Qwen Code authentication state
    qwencode_auth_status: AuthStatus = AuthStatus.NOT_AUTHENTICATED
    qwencode_user_email: str | None = None
    qwencode_user_id: str | None = None
    qwencode_access_token: str | None = None
    qwencode_refresh_token: str | None = None
    qwencode_token_expires_at: float | None = None
    qwencode_api_endpoint: str | None = None
    
    # OAuth callback state
    oauth_state: str | None = None
    oauth_code_verifier: str | None = None


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


# Fallback Roo Code models - used ONLY when API is unavailable
# These models should match the official Roo Code Cloud models from:
# https://docs.roocode.com/providers/roo-code-cloud
# NOTE: The dashboard should ALWAYS fetch models dynamically from the API
# when the user is authenticated. These are fallback defaults only.
ROOCODE_MODELS: dict = {
    # Empty by default - models should be fetched from API after authentication
    # This ensures we don't show outdated/incorrect models to users
}


# Qwen Code CLI models - fallback when API is unavailable
# Reference: https://github.com/QwenLM/qwen-code
QWENCODE_MODELS: dict = {
    "qwen3-coder-plus": {
        "name": "qwen3-coder-plus",
        "display_name": "Qwen3 Coder Plus",
        "description": "Advanced Qwen3 coding model with enhanced capabilities (2,000 free requests/day)",
        "context_window": 131072,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat", "analysis"],
        "speed": "fast",
    },
    "qwen3-coder-plus-latest": {
        "name": "qwen3-coder-plus-latest",
        "display_name": "Qwen3 Coder Plus (Latest)",
        "description": "Latest version of Qwen3 coding model",
        "context_window": 131072,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat", "analysis"],
        "speed": "fast",
    },
    "qwen/qwen3-coder:free": {
        "name": "qwen/qwen3-coder:free",
        "display_name": "Qwen3 Coder (OpenRouter Free)",
        "description": "Qwen3 Coder via OpenRouter free tier (1,000 calls/day)",
        "context_window": 128000,
        "free": True,
        "provider": "openrouter",
        "capabilities": ["code", "chat"],
        "speed": "fast",
    },
}


# Qwen Code CLI models
# Reference: https://github.com/QwenLM/qwen-code
QWENCODE_MODELS: dict = {
    "qwen3-coder-plus": {
        "name": "qwen3-coder-plus",
        "display_name": "Qwen3 Coder Plus",
        "description": "High-performance coding model optimized for complex tasks",
        "context_window": 262000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat", "vision"],
        "speed": "moderate",
    },
    "qwen3-coder": {
        "name": "qwen3-coder",
        "display_name": "Qwen3 Coder",
        "description": "Balanced coding model for general development tasks",
        "context_window": 131000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat"],
        "speed": "fast",
    },
}


# Planning depth descriptions
PLANNING_DEPTHS = {
    "quick": "Fast reconnaissance with targeted vulnerability checks",
    "balanced": "Comprehensive testing with moderate depth analysis",
    "thorough": "Deep analysis with extensive validation and chained attacks",
}


# Memory strategies
MEMORY_STRATEGIES = {
    "minimal": "Minimal context retention - faster but may miss connections",
    "adaptive": "Automatically adjusts based on complexity",
    "full": "Maximum context retention - slower but most thorough",
}


# Severity levels for filtering
SEVERITY_LEVELS = ["critical", "high", "medium", "low", "info"]


# Output formats
OUTPUT_FORMATS = {
    "json": "JSON format - Machine readable",
    "markdown": "Markdown format - Human readable",
    "html": "HTML format - Interactive report",
    "sarif": "SARIF format - IDE/CI integration",
}
