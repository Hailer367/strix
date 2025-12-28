import os


# Default CLIProxyAPI settings
CLIPROXY_DEFAULT_BASE_URL = "http://localhost:8317/v1"
CLIPROXY_DEFAULT_MODEL = "gemini-2.5-pro"


class LLMConfig:
    """
    Configuration for LLM providers.
    
    Supports multiple providers including:
    - CLIProxyAPI (Recommended): Unified API gateway for Google/Claude/OpenAI accounts
    - OpenAI: Direct OpenAI API access
    - Anthropic: Direct Claude API access
    - Google: Direct Gemini API access
    - Local: Ollama, LMStudio, or custom endpoints
    
    CLIProxyAPI Configuration:
    - Set CLIPROXY_ENABLED=true to use CLIProxyAPI as the default provider
    - Set CLIPROXY_BASE_URL to your CLIProxyAPI server (default: http://localhost:8317/v1)
    - Set CLIPROXY_MANAGEMENT_KEY for management API access
    - No API key required - uses OAuth-connected accounts
    
    Environment Variables:
    - STRIX_LLM: Model name (e.g., "gemini-2.5-pro", "claude-sonnet-4")
    - LLM_API_KEY: API key (not needed for CLIProxyAPI)
    - LLM_API_BASE: API base URL (auto-set for CLIProxyAPI)
    - CLIPROXY_ENABLED: Enable CLIProxyAPI mode (true/false)
    - CLIPROXY_BASE_URL: CLIProxyAPI server URL
    - CLIPROXY_MANAGEMENT_KEY: Management API key
    """
    
    def __init__(
        self,
        model_name: str | None = None,
        enable_prompt_caching: bool = True,
        prompt_modules: list[str] | None = None,
        timeout: int | None = None,
        scan_mode: str = "deep",
        cliproxy_enabled: bool | None = None,
        cliproxy_base_url: str | None = None,
        cliproxy_management_key: str | None = None,
    ):
        # CLIProxyAPI configuration
        self.cliproxy_enabled = cliproxy_enabled if cliproxy_enabled is not None else \
            os.getenv("CLIPROXY_ENABLED", "true").lower() == "true"
        
        self.cliproxy_base_url = cliproxy_base_url or os.getenv(
            "CLIPROXY_BASE_URL", 
            CLIPROXY_DEFAULT_BASE_URL
        )
        
        self.cliproxy_management_key = cliproxy_management_key or os.getenv(
            "CLIPROXY_MANAGEMENT_KEY",
            ""
        )
        
        # Model configuration
        if self.cliproxy_enabled:
            # Default to CLIProxyAPI settings
            self.model_name = model_name or os.getenv("STRIX_LLM", CLIPROXY_DEFAULT_MODEL)
            # Set API base to CLIProxyAPI if not already set
            if not os.getenv("LLM_API_BASE"):
                os.environ["LLM_API_BASE"] = self.cliproxy_base_url
        else:
            self.model_name = model_name or os.getenv("STRIX_LLM", "openai/gpt-5")

        if not self.model_name:
            raise ValueError("STRIX_LLM environment variable must be set and not empty")

        self.enable_prompt_caching = enable_prompt_caching
        self.prompt_modules = prompt_modules or []

        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", "300"))

        self.scan_mode = scan_mode if scan_mode in ["quick", "standard", "deep"] else "deep"
    
    def get_api_base(self) -> str | None:
        """Get the API base URL, defaulting to CLIProxyAPI if enabled."""
        if self.cliproxy_enabled:
            return self.cliproxy_base_url
        return os.getenv("LLM_API_BASE") or os.getenv("OPENAI_API_BASE")
    
    def is_cliproxy_mode(self) -> bool:
        """Check if CLIProxyAPI mode is enabled."""
        return self.cliproxy_enabled
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "model_name": self.model_name,
            "enable_prompt_caching": self.enable_prompt_caching,
            "prompt_modules": self.prompt_modules,
            "timeout": self.timeout,
            "scan_mode": self.scan_mode,
            "cliproxy_enabled": self.cliproxy_enabled,
            "cliproxy_base_url": self.cliproxy_base_url,
        }
