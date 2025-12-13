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


class LLMConfig:
    def __init__(
        self,
        model_name: str | None = None,
        enable_prompt_caching: bool = True,
        prompt_modules: list[str] | None = None,
        timeout: int | None = None,
        use_roocode: bool | None = None,
    ):
        # Check if Roo Code provider is explicitly enabled
        self.use_roocode = use_roocode or os.getenv("STRIX_USE_ROOCODE", "").lower() == "true"

        # Get model name with Roo Code support
        raw_model_name = model_name or os.getenv("STRIX_LLM", "openai/gpt-5")

        # Handle Roo Code model aliases
        if raw_model_name in ROOCODE_MODEL_ALIASES:
            raw_model_name = ROOCODE_MODEL_ALIASES[raw_model_name]

        # Auto-detect Roo Code usage from model name
        if raw_model_name.startswith("roocode/"):
            self.use_roocode = True

        self.model_name = raw_model_name

        if not self.model_name:
            raise ValueError("STRIX_LLM environment variable must be set and not empty")

        self.enable_prompt_caching = enable_prompt_caching
        self.prompt_modules = prompt_modules or []

        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", "300"))

        # Store original model name for Roo Code processing
        self._original_model_name = raw_model_name

    def is_roocode_model(self) -> bool:
        """Check if the configured model is a Roo Code model."""
        return self.use_roocode or self.model_name.startswith("roocode/")

    def get_roocode_model_name(self) -> str:
        """Get the clean Roo Code model name (without prefix)."""
        if self.model_name.startswith("roocode/"):
            return self.model_name.replace("roocode/", "")
        return self.model_name
