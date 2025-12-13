"""
Dashboard Configuration Models

Pydantic models for dashboard configuration and scan parameters.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AIProvider(str, Enum):
    """Supported AI providers."""
    ROOCODE = "roocode"
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
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RooCodeConfig(BaseModel):
    """Roo Code Cloud configuration."""
    enabled: bool = True
    model: str = "grok-code-fast-1"
    access_token: str | None = None
    auto_authenticate: bool = True


class AIConfig(BaseModel):
    """AI provider configuration."""
    provider: AIProvider = AIProvider.ROOCODE
    model: str = "grok-code-fast-1"
    api_key: str | None = None
    api_base: str | None = None
    roocode: RooCodeConfig = Field(default_factory=RooCodeConfig)
    timeout: int = 600


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


class TestingConfig(BaseModel):
    """Testing parameters configuration."""
    instructions: str = ""
    focus_areas: list[str] = Field(default_factory=list)
    credentials: dict[str, str] = Field(default_factory=dict)
    max_iterations: int = 300
    duration_minutes: int = 60


class OutputConfig(BaseModel):
    """Output and reporting configuration."""
    format: str = "markdown"  # json, markdown, html
    severity_threshold: str = "info"  # critical, high, medium, low, info
    notification_webhook: str | None = None
    save_artifacts: bool = True


class ScanConfig(BaseModel):
    """Complete scan configuration."""
    ai: AIConfig = Field(default_factory=AIConfig)
    access: AccessConfig = Field(default_factory=AccessConfig)
    targets: TargetConfig
    testing: TestingConfig = Field(default_factory=TestingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    
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
    
    # Feature flags
    enable_roocode_auth: bool = True
    enable_root_access: bool = True
    enable_custom_tools: bool = True
    
    # Limits
    max_duration_minutes: int = 480  # 8 hours
    max_targets: int = 10
    max_instructions_length: int = 10000


@dataclass
class DashboardState:
    """Runtime state for the dashboard."""
    config: ScanConfig | None = None
    status: ScanStatus = ScanStatus.PENDING
    findings: list[dict[str, Any]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    progress: int = 0
    current_action: str = "Waiting for configuration"
    connected_clients: int = 0
    start_time: datetime | None = None


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
]


# Available Roo Code models
ROOCODE_MODELS = {
    "grok-code-fast-1": {
        "name": "Grok Code Fast 1",
        "description": "Fast coding model - Best for quick scans and iterations",
        "context_window": 262000,
    },
    "roo/code-supernova": {
        "name": "Code Supernova",
        "description": "Advanced model - Best for complex reasoning and multimodal",
        "context_window": 200000,
    },
}
