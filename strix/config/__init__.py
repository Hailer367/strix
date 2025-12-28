"""Strix Configuration Module.

This module provides configuration management for Strix, including:
- config.json file-based configuration for CLIProxyAPI endpoints
- Environment variable overrides
- Runtime configuration updates
"""

from .config_manager import (
    ConfigManager,
    DashboardConfig,
    StrixConfig,
    TimeframeConfig,
    get_config,
    load_config,
    save_config,
)


__all__ = [
    "ConfigManager",
    "DashboardConfig",
    "StrixConfig",
    "TimeframeConfig",
    "get_config",
    "load_config",
    "save_config",
]
