"""
Strix Dashboard Module

Provides a web-based configuration dashboard for autonomous bug bounty operations
through GitHub Actions.

Features:
- Configure-and-Fire: Set all parameters before starting autonomous scan
- Roo Code Authentication: OAuth login directly from the dashboard
- Qwen Code CLI Authentication: OAuth login for Qwen AI models
- Real-time Monitoring: Live progress and findings display
- Advanced Agent Configuration: Fine-tune Strix agent behavior
- Extensible Configuration: Custom instructions, focus areas, and more
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
    RooCodeConfig,
    QwenCodeConfig,
    AuthStatus,
    ScanStatus,
    ROOCODE_MODELS,
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
    "RooCodeConfig",
    "QwenCodeConfig",
    "AuthStatus",
    "ScanStatus",
    # Constants
    "ROOCODE_MODELS",
    "QWENCODE_MODELS",
    "DEFAULT_FOCUS_AREAS",
    "PLANNING_DEPTHS",
    "MEMORY_STRATEGIES",
    "SEVERITY_LEVELS",
    "OUTPUT_FORMATS",
]
