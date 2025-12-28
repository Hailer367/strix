"""LLM Configuration for Strix.

This module provides configuration for LLM providers, now primarily through
config.json file-based configuration for CLIProxyAPI endpoints.

Configuration Priority:
1. config.json file (recommended)
2. Environment variables (legacy support)
3. Default values

Example config.json:
{
    "api": {
        "endpoint": "http://localhost:8317/v1",  // CLIProxyAPI endpoint
        "model": "gemini-2.5-pro"
    }
}
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from strix.config import StrixConfig


# Default settings (used when no config is available)
DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_TIMEOUT = 300


def _get_strix_config() -> "StrixConfig | None":
    """Attempt to get StrixConfig, handling import errors gracefully."""
    try:
        from strix.config import get_config
        return get_config()
    except (ImportError, Exception):
        return None


class LLMConfig:
    """Configuration for LLM providers.
    
    Now configured primarily through config.json file:
    
    1. Create config.json in your project directory:
    {
        "api": {
            "endpoint": "http://localhost:8317/v1",
            "model": "gemini-2.5-pro"
        },
        "timeframe": {
            "duration_minutes": 60,
            "warning_minutes": 5
        }
    }
    
    2. Run CLIProxyAPI and ensure it's accessible at the endpoint
    
    3. Run Strix - it will automatically read from config.json
    
    Legacy Environment Variables (still supported):
    - STRIX_LLM: Model name
    - LLM_API_KEY: API key (not needed for CLIProxyAPI OAuth mode)
    - LLM_API_BASE: API base URL
    """
    
    def __init__(
        self,
        model_name: str | None = None,
        enable_prompt_caching: bool = True,
        prompt_modules: list[str] | None = None,
        timeout: int | None = None,
        scan_mode: str = "deep",
        # Legacy CLIProxyAPI parameters (now read from config.json)
        cliproxy_enabled: bool | None = None,
        cliproxy_base_url: str | None = None,
        cliproxy_management_key: str | None = None,
    ):
        # Try to load from StrixConfig first
        strix_config = _get_strix_config()
        
        if strix_config and strix_config.api_endpoint:
            # Use config.json settings
            self.api_endpoint = strix_config.api_endpoint
            self.model_name = model_name or strix_config.model or DEFAULT_MODEL
            self.api_key = strix_config.api_key
            self.scan_mode = strix_config.scan_mode if strix_config.scan_mode else scan_mode
            
            # Set environment variables for litellm compatibility
            if self.api_endpoint and not os.getenv("LLM_API_BASE"):
                os.environ["LLM_API_BASE"] = self.api_endpoint
            if self.api_key and not os.getenv("LLM_API_KEY"):
                os.environ["LLM_API_KEY"] = self.api_key
        else:
            # Fall back to environment variables (legacy support)
            self._init_from_environment(
                model_name=model_name,
                cliproxy_enabled=cliproxy_enabled,
                cliproxy_base_url=cliproxy_base_url,
                cliproxy_management_key=cliproxy_management_key,
            )
            self.scan_mode = scan_mode if scan_mode in ["quick", "standard", "deep"] else "deep"
        
        if not self.model_name:
            raise ValueError(
                "Model name is required. Please configure it in config.json "
                "or set STRIX_LLM environment variable."
            )
        
        self.enable_prompt_caching = enable_prompt_caching
        self.prompt_modules = prompt_modules or []
        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", str(DEFAULT_TIMEOUT)))
        
        # Store timeframe config for later access
        self._strix_config = strix_config
    
    def _init_from_environment(
        self,
        model_name: str | None = None,
        cliproxy_enabled: bool | None = None,
        cliproxy_base_url: str | None = None,
        cliproxy_management_key: str | None = None,
    ) -> None:
        """Initialize from environment variables (legacy support)."""
        # Check if CLIProxyAPI mode is enabled via environment
        self._cliproxy_enabled = cliproxy_enabled if cliproxy_enabled is not None else \
            os.getenv("CLIPROXY_ENABLED", "false").lower() == "true"
        
        self._cliproxy_base_url = cliproxy_base_url or os.getenv("CLIPROXY_BASE_URL", "")
        self._cliproxy_management_key = cliproxy_management_key or os.getenv(
            "CLIPROXY_MANAGEMENT_KEY", ""
        )
        
        # Get API endpoint from various sources
        self.api_endpoint = (
            self._cliproxy_base_url
            or os.getenv("LLM_API_BASE")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("LITELLM_BASE_URL")
            or os.getenv("OLLAMA_API_BASE")
            or ""
        )
        
        # Get model name
        if self._cliproxy_enabled and not model_name:
            self.model_name = os.getenv("STRIX_LLM", DEFAULT_MODEL)
        else:
            self.model_name = model_name or os.getenv("STRIX_LLM", "openai/gpt-5")
        
        # Get API key
        self.api_key = os.getenv("LLM_API_KEY")
        
        # Set API base for litellm if we have an endpoint
        if self.api_endpoint and not os.getenv("LLM_API_BASE"):
            os.environ["LLM_API_BASE"] = self.api_endpoint
    
    def get_api_base(self) -> str | None:
        """Get the API base URL."""
        return self.api_endpoint if self.api_endpoint else None
    
    def is_cliproxy_mode(self) -> bool:
        """Check if using CLIProxyAPI mode (via config.json or environment)."""
        return bool(self.api_endpoint)
    
    def get_timeframe_config(self) -> "dict | None":
        """Get the timeframe configuration if available."""
        if self._strix_config:
            return self._strix_config.timeframe.to_dict()
        return None
    
    def get_time_efficiency_prompt(self) -> str:
        """Get the time efficiency prompt for the AI."""
        if self._strix_config:
            return self._strix_config.get_time_efficiency_prompt()
        return ""
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        result = {
            "model_name": self.model_name,
            "enable_prompt_caching": self.enable_prompt_caching,
            "prompt_modules": self.prompt_modules,
            "timeout": self.timeout,
            "scan_mode": self.scan_mode,
            "api_endpoint": self.api_endpoint,
        }
        
        if self._strix_config:
            result["timeframe"] = self._strix_config.timeframe.to_dict()
        
        return result


def create_example_config() -> Path:
    """Create an example config.json file in the current directory."""
    from strix.config import ConfigManager
    
    manager = ConfigManager.get_instance()
    return manager.create_default_config_file()
