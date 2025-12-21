"""
Strix Dashboard Module

Provides a web-based configuration dashboard for autonomous bug bounty operations
through GitHub Actions.

Features:
- Configure-and-Fire: Set all parameters before starting autonomous scan
- Qwen Code CLI Authentication: OAuth login for Qwen AI models (2,000 requests/day, no limits)
- OpenRouter Support: API key authentication (1,000 free requests/day via qwen-code CLI)
- Real-time Monitoring: Live progress and findings display
- Advanced Agent Configuration: Fine-tune Strix agent behavior
- Extensible Configuration: Custom instructions, focus areas, and more

Reference: https://github.com/QwenLM/qwen-code
"""

from .server import (
    create_app,
    run_dashboard,
    add_finding,
    add_log,
    update_progress,
    broadcast_update,
)
from .config import (
    DashboardConfig,
    DashboardState,
    ScanConfig,
    AIConfig,
    AIProvider,
    AccessConfig,
    AccessLevel,
    TargetConfig,
    TestingConfig,
    OutputConfig,
    AgentBehaviorConfig,
    QwenCodeConfig,
    AuthStatus,
    ScanStatus,
    QWENCODE_MODELS,
    DEFAULT_FOCUS_AREAS,
    PLANNING_DEPTHS,
    MEMORY_STRATEGIES,
    SEVERITY_LEVELS,
    OUTPUT_FORMATS,
)

__all__ = [
    # Server
    "create_app",
    "run_dashboard",
    "add_finding",
    "add_log",
    "update_progress",
    "broadcast_update",
    # Config
    "DashboardConfig",
    "DashboardState",
    "ScanConfig",
    "AIConfig",
    "AIProvider",
    "AccessConfig",
    "AccessLevel",
    "TargetConfig",
    "TestingConfig",
    "OutputConfig",
    "AgentBehaviorConfig",
    "QwenCodeConfig",
    "AuthStatus",
    "ScanStatus",
    # Constants
    "QWENCODE_MODELS",
    "DEFAULT_FOCUS_AREAS",
    "PLANNING_DEPTHS",
    "MEMORY_STRATEGIES",
    "SEVERITY_LEVELS",
    "OUTPUT_FORMATS",
]
