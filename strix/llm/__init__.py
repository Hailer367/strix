import litellm

from .config import LLMConfig
from .llm import LLM, LLMRequestFailedError
from .qwencode_provider import (
    QwenCodeCredentials,
    QwenCodeProvider,
    configure_qwencode_for_litellm,
    get_qwencode_provider,
    is_qwencode_model,
)
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
    "QwenCodeCredentials",
    "QwenCodeProvider",
    "RooCodeCredentials",
    "RooCodeProvider",
    "configure_qwencode_for_litellm",
    "configure_roocode_for_litellm",
    "get_qwencode_provider",
    "get_roocode_provider",
    "is_qwencode_model",
    "is_roocode_model",
]

litellm._logging._disable_debugging()
