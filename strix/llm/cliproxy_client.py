"""Direct CLIProxyAPI Client for Strix.

This module provides a direct HTTP client for CLIProxyAPI without using LiteLLM.
CLIProxyAPI provides an OpenAI-compatible API endpoint that handles authentication
via OAuth, so no API keys are needed.

Key Features:
- Direct HTTP requests to CLIProxyAPI (no LiteLLM overhead)
- Automatic retry with exponential backoff
- Streaming and non-streaming support
- Full compatibility with OpenAI chat completions API

Usage:
    client = CLIProxyClient(endpoint="http://localhost:8317/v1")
    response = await client.chat_completion(
        model="qwen3-coder-plus",
        messages=[{"role": "user", "content": "Hello"}]
    )
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import aiohttp


logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Represents a chat message."""
    role: str  # "system", "user", "assistant"
    content: str
    name: str | None = None


@dataclass
class Usage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class Choice:
    """A completion choice."""
    index: int
    message: ChatMessage
    finish_reason: str | None = None


@dataclass
class ChatCompletion:
    """OpenAI-compatible chat completion response."""
    id: str
    object: str = "chat.completion"
    created: int = 0
    model: str = ""
    choices: list[Choice] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class CLIProxyError(Exception):
    """Base exception for CLIProxyAPI errors."""
    def __init__(self, message: str, status_code: int | None = None, details: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class RateLimitError(CLIProxyError):
    """Rate limit exceeded."""
    pass


class AuthenticationError(CLIProxyError):
    """Authentication failed."""
    pass


class ModelNotFoundError(CLIProxyError):
    """Model not found."""
    pass


class ServerError(CLIProxyError):
    """Server error."""
    pass


class CLIProxyClient:
    """Direct HTTP client for CLIProxyAPI.
    
    This client communicates directly with CLIProxyAPI using the OpenAI-compatible
    chat completions API, without going through LiteLLM.
    
    CLIProxyAPI handles:
    - OAuth authentication (no API keys needed)
    - Load balancing across multiple accounts
    - Automatic failover when quota is exceeded
    - Model routing and aliasing
    
    Example:
        client = CLIProxyClient()
        response = await client.chat_completion(
            model="qwen3-coder-plus",
            messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello!"}
            ]
        )
        print(response.choices[0].message.content)
    """
    
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        timeout: float = 300.0,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        max_retry_delay: float = 30.0,
    ):
        """Initialize the CLIProxyAPI client.
        
        Args:
            endpoint: CLIProxyAPI base URL (default: from environment or localhost:8317)
            api_key: Optional API key (CLIProxyAPI usually doesn't need one)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial retry delay in seconds
            max_retry_delay: Maximum retry delay in seconds
        """
        self.endpoint = endpoint or self._get_endpoint()
        self.api_key = api_key or os.getenv("LLM_API_KEY", "cliproxy-oauth-mode")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay
        
        # Statistics
        self._total_requests = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        
        logger.info(f"CLIProxyClient initialized with endpoint: {self.endpoint}")
    
    def _get_endpoint(self) -> str:
        """Get the CLIProxyAPI endpoint from environment or config."""
        # Priority: config.json > environment > default
        try:
            from strix.config import get_config
            config = get_config()
            if config.api_endpoint:
                return config.api_endpoint
        except Exception:
            pass
        
        return (
            os.getenv("CLIPROXY_ENDPOINT")
            or os.getenv("LLM_API_BASE")
            or os.getenv("OPENAI_API_BASE")
            or "http://localhost:8317/v1"
        )
    
    async def _make_request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to CLIProxyAPI.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/chat/completions")
            json_data: JSON request body
            
        Returns:
            Parsed JSON response
            
        Raises:
            CLIProxyError: On API errors
        """
        url = f"{self.endpoint.rstrip('/')}{path}"
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        last_error: Exception | None = None
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.request(
                        method,
                        url,
                        headers=headers,
                        json=json_data,
                    ) as response:
                        response_text = await response.text()
                        
                        if response.status == 200:
                            try:
                                return json.loads(response_text)
                            except json.JSONDecodeError as e:
                                raise CLIProxyError(
                                    f"Invalid JSON response: {e}",
                                    status_code=response.status,
                                    details=response_text[:500],
                                ) from e
                        
                        # Handle errors
                        error_msg = f"API error: {response.status}"
                        try:
                            error_data = json.loads(response_text)
                            if "error" in error_data:
                                if isinstance(error_data["error"], dict):
                                    error_msg = error_data["error"].get("message", error_msg)
                                else:
                                    error_msg = str(error_data["error"])
                        except json.JSONDecodeError:
                            error_msg = response_text[:200] if response_text else error_msg
                        
                        if response.status == 429:
                            raise RateLimitError(
                                error_msg,
                                status_code=response.status,
                            )
                        elif response.status in (401, 403):
                            raise AuthenticationError(
                                error_msg,
                                status_code=response.status,
                            )
                        elif response.status == 404:
                            raise ModelNotFoundError(
                                error_msg,
                                status_code=response.status,
                            )
                        elif response.status >= 500:
                            raise ServerError(
                                error_msg,
                                status_code=response.status,
                            )
                        else:
                            raise CLIProxyError(
                                error_msg,
                                status_code=response.status,
                                details=response_text[:500],
                            )
                            
            except (RateLimitError, ServerError) as e:
                # Retry on rate limit and server errors
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.retry_delay * (2 ** attempt),
                        self.max_retry_delay,
                    )
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
                    
            except (AuthenticationError, ModelNotFoundError):
                # Don't retry auth or model errors
                raise
                
            except aiohttp.ClientError as e:
                last_error = CLIProxyError(f"Connection error: {e}")
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.retry_delay * (2 ** attempt),
                        self.max_retry_delay,
                    )
                    logger.warning(
                        f"Connection failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise CLIProxyError(f"Connection error after {self.max_retries} attempts: {e}") from e
                    
            except asyncio.TimeoutError as e:
                last_error = CLIProxyError(f"Request timeout after {self.timeout}s")
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.retry_delay * (2 ** attempt),
                        self.max_retry_delay,
                    )
                    logger.warning(
                        f"Timeout (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise CLIProxyError(f"Request timeout after {self.max_retries} attempts") from e
        
        if last_error:
            raise last_error
        raise CLIProxyError("Unknown error occurred")
    
    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> ChatCompletion:
        """Create a chat completion.
        
        Args:
            model: Model name (e.g., "qwen3-coder-plus", "gemini-2.5-pro")
            messages: List of chat messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            stream: Whether to stream the response
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletion object
            
        Raises:
            CLIProxyError: On API errors
        """
        request_data: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        
        if temperature is not None:
            request_data["temperature"] = temperature
        if max_tokens is not None:
            request_data["max_tokens"] = max_tokens
        if stop is not None:
            request_data["stop"] = stop
        
        # Add any extra parameters
        for key, value in kwargs.items():
            if value is not None:
                request_data[key] = value
        
        self._total_requests += 1
        start_time = time.time()
        
        response_data = await self._make_request(
            "POST",
            "/chat/completions",
            json_data=request_data,
        )
        
        elapsed = time.time() - start_time
        logger.debug(f"Chat completion completed in {elapsed:.2f}s")
        
        # Parse response
        choices = []
        for choice_data in response_data.get("choices", []):
            message_data = choice_data.get("message", {})
            message = ChatMessage(
                role=message_data.get("role", "assistant"),
                content=message_data.get("content", ""),
                name=message_data.get("name"),
            )
            choices.append(Choice(
                index=choice_data.get("index", 0),
                message=message,
                finish_reason=choice_data.get("finish_reason"),
            ))
        
        usage_data = response_data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
            cached_tokens=usage_data.get("cached_tokens", 0),
        )
        
        self._total_tokens += usage.total_tokens
        
        return ChatCompletion(
            id=response_data.get("id", ""),
            object=response_data.get("object", "chat.completion"),
            created=response_data.get("created", int(time.time())),
            model=response_data.get("model", model),
            choices=choices,
            usage=usage,
        )
    
    async def list_models(self) -> list[dict[str, Any]]:
        """List available models.
        
        Returns:
            List of model objects
        """
        response = await self._make_request("GET", "/models")
        return response.get("data", [])
    
    def get_stats(self) -> dict[str, Any]:
        """Get client statistics.
        
        Returns:
            Dictionary with total_requests, total_tokens, total_cost
        """
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
        }


# Global client instance
_global_client: CLIProxyClient | None = None


def get_global_client() -> CLIProxyClient:
    """Get the global CLIProxyAPI client instance."""
    global _global_client
    if _global_client is None:
        _global_client = CLIProxyClient()
    return _global_client


def reset_global_client() -> None:
    """Reset the global client (useful for testing)."""
    global _global_client
    _global_client = None
