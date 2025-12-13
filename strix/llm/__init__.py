import litellm

from .config import LLMConfig
from .llm import LLM, LLMRequestFailedError
from .roocode_provider import (
    RooCodeCredentials,
    RooCodeProvider,
    configure_roocode_for_litellm,
    get_roocode_provider,
    is_roocode_model,
)


__all__ = [
    "LLM",
    "LLMConfig",
    "LLMRequestFailedError",
    "RooCodeCredentials",
    "RooCodeProvider",
    "configure_roocode_for_litellm",
    "get_roocode_provider",
    "is_roocode_model",
]

litellm._logging._disable_debugging()
