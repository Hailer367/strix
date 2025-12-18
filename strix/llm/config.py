import os


# Roo Code model aliases for easy configuration
# Reference: https://docs.roocode.com/providers/roo-code-cloud
ROOCODE_MODEL_ALIASES = {
    "roocode/grok": "roocode/grok-code-fast-1",
    "roocode/supernova": "roocode/roo/code-supernova",
    "roocode/fast": "roocode/grok-code-fast-1",
    "roocode/advanced": "roocode/roo/code-supernova",
    # Direct model names
    "grok-code-fast-1": "roocode/grok-code-fast-1",
    "roo/code-supernova": "roocode/roo/code-supernova",
    "code-supernova": "roocode/roo/code-supernova",
}

# Qwen Code CLI model aliases for easy configuration
# Reference: https://github.com/QwenLM/qwen-code
QWENCODE_MODEL_ALIASES = {
    "qwencode/coder": "qwencode/qwen3-coder-plus",
    "qwencode/plus": "qwencode/qwen3-coder-plus",
    "qwencode/latest": "qwencode/qwen3-coder-plus-latest",
    "qwencode/free": "qwencode/qwen/qwen3-coder:free",
    # Direct model names
    "qwen3-coder-plus": "qwencode/qwen3-coder-plus",
    "qwen3-coder-plus-latest": "qwencode/qwen3-coder-plus-latest",
    "qwen/qwen3-coder:free": "qwencode/qwen/qwen3-coder:free",
    "qwen3-coder": "qwencode/qwen3-coder-plus",
}


# Qwen Code CLI model aliases for easy configuration
# Reference: https://github.com/QwenLM/qwen-code
QWENCODE_MODEL_ALIASES = {
    "qwencode/coder": "qwencode/qwen3-coder",
    "qwencode/coder-plus": "qwencode/qwen3-coder-plus",
    "qwencode/fast": "qwencode/qwen3-coder",
    "qwencode/advanced": "qwencode/qwen3-coder-plus",
    # Direct model names
    "qwen3-coder": "qwencode/qwen3-coder",
    "qwen3-coder-plus": "qwencode/qwen3-coder-plus",
    "qwen-coder": "qwencode/qwen3-coder",
    # ModelScope models
    "Qwen/Qwen3-Coder-480B-A35B-Instruct": "qwencode/Qwen/Qwen3-Coder-480B-A35B-Instruct",
    # OpenRouter models
    "qwen/qwen3-coder:free": "qwencode/qwen/qwen3-coder:free",
}


class LLMConfig:
    def __init__(
        self,
        model_name: str | None = None,
        enable_prompt_caching: bool = True,
        prompt_modules: list[str] | None = None,
        timeout: int | None = None,
        use_roocode: bool | None = None,
        use_qwencode: bool | None = None,
    ):
        # Check if Roo Code provider is explicitly enabled
        self.use_roocode = use_roocode or os.getenv("STRIX_USE_ROOCODE", "").lower() == "true"
        
        # Check if Qwen Code provider is explicitly enabled
        self.use_qwencode = use_qwencode or os.getenv("STRIX_USE_QWENCODE", "").lower() == "true"

        # Get model name with provider support
        raw_model_name = model_name or os.getenv("STRIX_LLM", "openai/gpt-5")

        # Handle Roo Code model aliases
        if raw_model_name in ROOCODE_MODEL_ALIASES:
            raw_model_name = ROOCODE_MODEL_ALIASES[raw_model_name]
            
        # Handle Qwen Code model aliases
        if raw_model_name in QWENCODE_MODEL_ALIASES:
            raw_model_name = QWENCODE_MODEL_ALIASES[raw_model_name]

        # Auto-detect Roo Code usage from model name
        if raw_model_name.startswith("roocode/"):
            self.use_roocode = True
            
        # Auto-detect Qwen Code usage from model name
        if raw_model_name.startswith("qwencode/"):
            self.use_qwencode = True

        self.model_name = raw_model_name

        if not self.model_name:
            raise ValueError("STRIX_LLM environment variable must be set and not empty")

        self.enable_prompt_caching = enable_prompt_caching
        self.prompt_modules = prompt_modules or []

        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", "300"))

        # Store original model name for provider processing
        self._original_model_name = raw_model_name

    def is_roocode_model(self) -> bool:
        """Check if the configured model is a Roo Code model."""
        return self.use_roocode or self.model_name.startswith("roocode/")

    def get_roocode_model_name(self) -> str:
        """Get the clean Roo Code model name (without prefix)."""
        if self.model_name.startswith("roocode/"):
            return self.model_name.replace("roocode/", "")
        return self.model_name
    
    def is_qwencode_model(self) -> bool:
        """Check if the configured model is a Qwen Code model."""
        return self.use_qwencode or self.model_name.startswith("qwencode/")

    def get_qwencode_model_name(self) -> str:
        """Get the clean Qwen Code model name (without prefix)."""
        if self.model_name.startswith("qwencode/"):
            return self.model_name.replace("qwencode/", "")
        return self.model_name
