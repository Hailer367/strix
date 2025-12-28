"""Configuration Manager for Strix.

Manages configuration through a config.json file, allowing users to configure
CLIProxyAPI endpoints and other settings without environment variables.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


# Default config file locations (in order of priority)
CONFIG_FILE_LOCATIONS = [
    Path.cwd() / "config.json",              # Current working directory
    Path.cwd() / "strix_config.json",        # Alternative name
    Path.home() / ".strix" / "config.json",  # User home directory
    Path("/etc/strix/config.json"),           # System-wide config
]


@dataclass
class TimeframeConfig:
    """Configuration for workflow timeframe settings."""
    
    # Duration in minutes (10 to 720 = 12 hours)
    duration_minutes: int = 60
    
    # Minutes before end to warn the AI to finish up
    warning_minutes: int = 5
    
    # Enable time awareness prompts
    time_awareness_enabled: bool = True
    
    def validate(self) -> None:
        """Validate timeframe configuration."""
        if not 10 <= self.duration_minutes <= 720:
            raise ValueError(
                f"duration_minutes must be between 10 and 720 (12 hours), "
                f"got {self.duration_minutes}"
            )
        if not 1 <= self.warning_minutes <= 30:
            raise ValueError(
                f"warning_minutes must be between 1 and 30, "
                f"got {self.warning_minutes}"
            )
        if self.warning_minutes >= self.duration_minutes:
            raise ValueError(
                f"warning_minutes ({self.warning_minutes}) must be less than "
                f"duration_minutes ({self.duration_minutes})"
            )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "duration_minutes": self.duration_minutes,
            "warning_minutes": self.warning_minutes,
            "time_awareness_enabled": self.time_awareness_enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeframeConfig":
        """Create from dictionary."""
        return cls(
            duration_minutes=data.get("duration_minutes", 60),
            warning_minutes=data.get("warning_minutes", 5),
            time_awareness_enabled=data.get("time_awareness_enabled", True),
        )


@dataclass
class DashboardConfig:
    """Configuration for the real-time dashboard."""
    
    # Enable the dashboard
    enabled: bool = True
    
    # Refresh interval in seconds
    refresh_interval: float = 1.0
    
    # Show detailed agent activity
    show_agent_details: bool = True
    
    # Show tool execution logs
    show_tool_logs: bool = True
    
    # Show time remaining countdown
    show_time_remaining: bool = True
    
    # Show resource usage (tokens, cost)
    show_resource_usage: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "refresh_interval": self.refresh_interval,
            "show_agent_details": self.show_agent_details,
            "show_tool_logs": self.show_tool_logs,
            "show_time_remaining": self.show_time_remaining,
            "show_resource_usage": self.show_resource_usage,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardConfig":
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            refresh_interval=data.get("refresh_interval", 1.0),
            show_agent_details=data.get("show_agent_details", True),
            show_tool_logs=data.get("show_tool_logs", True),
            show_time_remaining=data.get("show_time_remaining", True),
            show_resource_usage=data.get("show_resource_usage", True),
        )


@dataclass
class StrixConfig:
    """Main configuration for Strix.
    
    This configuration is primarily loaded from config.json file.
    CLIProxyAPI endpoints are configured here instead of through environment variables.
    
    Example config.json:
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
            "refresh_interval": 1.0
        }
    }
    """
    
    # CLIProxyAPI endpoint URL (required after running CLIProxyAPI)
    api_endpoint: str = ""
    
    # Model to use (e.g., "gemini-2.5-pro", "claude-sonnet-4", "gpt-5")
    model: str = "gemini-2.5-pro"
    
    # Optional API key (not needed for CLIProxyAPI OAuth mode)
    api_key: str | None = None
    
    # Timeframe configuration
    timeframe: TimeframeConfig = field(default_factory=TimeframeConfig)
    
    # Dashboard configuration
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    
    # Scan mode (quick, standard, deep)
    scan_mode: str = "deep"
    
    # Enable StrixDB
    strixdb_enabled: bool = False
    strixdb_repo: str = ""
    strixdb_token: str = ""
    
    # Perplexity API key for web search
    perplexity_api_key: str = ""
    
    def validate(self) -> list[str]:
        """Validate the configuration and return list of errors."""
        errors = []
        
        if not self.api_endpoint:
            errors.append(
                "api_endpoint is required. Run CLIProxyAPI and paste the endpoint URL "
                "(e.g., 'http://localhost:8317/v1') into config.json"
            )
        
        if not self.model:
            errors.append("model is required (e.g., 'gemini-2.5-pro', 'claude-sonnet-4')")
        
        if self.scan_mode not in ["quick", "standard", "deep"]:
            errors.append(f"scan_mode must be 'quick', 'standard', or 'deep', got '{self.scan_mode}'")
        
        try:
            self.timeframe.validate()
        except ValueError as e:
            errors.append(str(e))
        
        return errors
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "api": {
                "endpoint": self.api_endpoint,
                "model": self.model,
                "api_key": self.api_key or "",
            },
            "timeframe": self.timeframe.to_dict(),
            "dashboard": self.dashboard.to_dict(),
            "scan_mode": self.scan_mode,
            "strixdb": {
                "enabled": self.strixdb_enabled,
                "repo": self.strixdb_repo,
                "token": self.strixdb_token,
            },
            "perplexity_api_key": self.perplexity_api_key,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrixConfig":
        """Create from dictionary."""
        api_config = data.get("api", {})
        strixdb_config = data.get("strixdb", {})
        
        return cls(
            api_endpoint=api_config.get("endpoint", ""),
            model=api_config.get("model", "gemini-2.5-pro"),
            api_key=api_config.get("api_key") or None,
            timeframe=TimeframeConfig.from_dict(data.get("timeframe", {})),
            dashboard=DashboardConfig.from_dict(data.get("dashboard", {})),
            scan_mode=data.get("scan_mode", "deep"),
            strixdb_enabled=strixdb_config.get("enabled", False),
            strixdb_repo=strixdb_config.get("repo", ""),
            strixdb_token=strixdb_config.get("token", ""),
            perplexity_api_key=data.get("perplexity_api_key", ""),
        )
    
    def get_remaining_time_message(self, elapsed_minutes: float) -> str | None:
        """Get a time awareness message based on elapsed time.
        
        Returns None if no message is needed.
        """
        if not self.timeframe.time_awareness_enabled:
            return None
        
        remaining = self.timeframe.duration_minutes - elapsed_minutes
        
        if remaining <= self.timeframe.warning_minutes:
            return (
                f"⚠️ CRITICAL TIME WARNING: You have approximately {remaining:.1f} minutes remaining! "
                f"You MUST finish up your current task immediately. Prioritize completing any critical "
                f"findings, save your work, and prepare to call the appropriate finish tool. "
                f"Do NOT start any new investigations or long-running tasks."
            )
        elif remaining <= self.timeframe.warning_minutes * 2:
            return (
                f"⏰ TIME NOTICE: You have approximately {remaining:.1f} minutes remaining. "
                f"Start wrapping up your current investigations. Focus on documenting any findings "
                f"and prepare to finish soon."
            )
        
        return None
    
    def get_time_efficiency_prompt(self) -> str:
        """Get the time efficiency prompt for the AI."""
        if not self.timeframe.time_awareness_enabled:
            return ""
        
        return f"""
<time_management>
<session_duration>{self.timeframe.duration_minutes} minutes total</session_duration>
<warning_threshold>{self.timeframe.warning_minutes} minutes before end</warning_threshold>
<instructions>
- You have a LIMITED time budget of {self.timeframe.duration_minutes} minutes for this session
- Use your time EFFICIENTLY and THOROUGHLY - don't waste time on trivial tasks
- PRIORITIZE: Focus on the most impactful security tests first
- When you have {self.timeframe.warning_minutes} minutes remaining, you MUST wrap up:
  * Complete any in-progress tests
  * Document all findings clearly
  * Call the appropriate finish tool
- Do NOT start long-running scans when time is running low
- Be proactive in time management - check progress regularly
- Quality over quantity: Better to find and validate fewer vulnerabilities thoroughly
  than to rush through many superficially
</instructions>
</time_management>
"""


class ConfigManager:
    """Manages Strix configuration loading and saving."""
    
    _instance: "ConfigManager | None" = None
    _config: StrixConfig | None = None
    _config_path: Path | None = None
    
    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def find_config_file(self) -> Path | None:
        """Find the first existing config file."""
        for path in CONFIG_FILE_LOCATIONS:
            if path.exists() and path.is_file():
                return path
        return None
    
    def load(self, config_path: Path | None = None) -> StrixConfig:
        """Load configuration from file or create default.
        
        Priority:
        1. Explicitly specified config_path
        2. Config file in standard locations
        3. Environment variables (legacy support)
        4. Default values
        """
        if config_path and config_path.exists():
            self._config_path = config_path
        else:
            self._config_path = self.find_config_file()
        
        if self._config_path and self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    data = json.load(f)
                self._config = StrixConfig.from_dict(data)
                logger.info(f"Loaded configuration from {self._config_path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load config from {self._config_path}: {e}")
                self._config = self._load_from_env()
        else:
            self._config = self._load_from_env()
        
        return self._config
    
    def _load_from_env(self) -> StrixConfig:
        """Load configuration from environment variables (legacy support)."""
        api_endpoint = (
            os.getenv("LLM_API_BASE")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("CLIPROXY_BASE_URL")
            or ""
        )
        
        return StrixConfig(
            api_endpoint=api_endpoint,
            model=os.getenv("STRIX_LLM", "gemini-2.5-pro"),
            api_key=os.getenv("LLM_API_KEY"),
            strixdb_enabled=bool(os.getenv("STRIXDB_TOKEN")),
            strixdb_repo=os.getenv("STRIXDB_REPO", ""),
            strixdb_token=os.getenv("STRIXDB_TOKEN", ""),
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY", ""),
        )
    
    def save(self, config: StrixConfig | None = None, path: Path | None = None) -> Path:
        """Save configuration to file."""
        if config:
            self._config = config
        if path:
            self._config_path = path
        
        if self._config is None:
            self._config = StrixConfig()
        
        if self._config_path is None:
            self._config_path = Path.cwd() / "config.json"
        
        # Ensure parent directory exists
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._config.to_dict(), f, indent=2)
        
        logger.info(f"Saved configuration to {self._config_path}")
        return self._config_path
    
    def get_config(self) -> StrixConfig:
        """Get the current configuration, loading if necessary."""
        if self._config is None:
            self.load()
        return self._config or StrixConfig()
    
    def create_default_config_file(self, path: Path | None = None) -> Path:
        """Create a default config.json file with helpful comments."""
        if path is None:
            path = Path.cwd() / "config.json"
        
        default_config = StrixConfig()
        
        # Create a more helpful config with placeholder
        config_data = {
            "_comment": "Strix Configuration File - Configure your CLIProxyAPI endpoint here",
            "_instructions": [
                "1. Run CLIProxyAPI: cliproxy run --port 8317",
                "2. Copy the API endpoint URL to api.endpoint below",
                "3. Select your model (gemini-2.5-pro, claude-sonnet-4, gpt-5, etc.)",
                "4. Adjust timeframe settings as needed",
            ],
            **default_config.to_dict()
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        
        return path


# Module-level convenience functions
_manager: ConfigManager | None = None


def get_config() -> StrixConfig:
    """Get the current configuration."""
    global _manager
    if _manager is None:
        _manager = ConfigManager.get_instance()
    return _manager.get_config()


def load_config(path: Path | None = None) -> StrixConfig:
    """Load configuration from file."""
    global _manager
    if _manager is None:
        _manager = ConfigManager.get_instance()
    return _manager.load(path)


def save_config(config: StrixConfig, path: Path | None = None) -> Path:
    """Save configuration to file."""
    global _manager
    if _manager is None:
        _manager = ConfigManager.get_instance()
    return _manager.save(config, path)
