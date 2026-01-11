"""HTTP client wrapper for tool execution (Cloudflared-compatible).

This replaces the gRPC client with HTTP/REST API calls that work properly
with Cloudflared tunnels.
"""

import json
import logging
import time
from typing import Any

import httpx

from .metrics import get_metrics
from .result_cache import get_cache
from .retry_handler import retry_with_backoff

logger = logging.getLogger(__name__)

import os

# Default timeouts
DEFAULT_TIMEOUT = float(os.getenv("STRIX_TOOL_TIMEOUT", "300.0"))
DEFAULT_CONNECT_TIMEOUT = 10.0


class HttpToolClient:
    """Client for executing tools via HTTP with retry logic and caching."""

    def __init__(
        self, 
        server_url: str, 
        auth_token: str, 
        timeout: float | None = None
    ) -> None:
        """Initialize HTTP client.

        Args:
            server_url: Server URL (can be cloudflared domain or host:port)
            auth_token: Authentication token
            timeout: Request timeout in seconds
        """
        # Ensure proper URL format
        if not server_url.startswith("http://") and not server_url.startswith("https://"):
            # For cloudflared domains, use HTTPS
            if "trycloudflare.com" in server_url or ":" not in server_url or server_url.endswith(":443"):
                server_url = f"https://{server_url}"
            else:
                server_url = f"http://{server_url}"
        
        # Remove trailing port if it's the default HTTPS port
        if server_url.endswith(":443"):
            server_url = server_url[:-4]
        
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout or DEFAULT_TIMEOUT
        self._metrics = get_metrics()
        self._cache = get_cache()
        
        logger.debug(f"HttpToolClient initialized with server_url={self.server_url}")

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers with authentication."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: dict[str, Any] | None = None,
        timeout: float | None = None
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint
            data: Request body data
            timeout: Request timeout

        Returns:
            Response JSON data
        """
        url = f"{self.server_url}{endpoint}"
        request_timeout = timeout or self.timeout
        
        httpx_timeout = httpx.Timeout(
            timeout=request_timeout,
            connect=DEFAULT_CONNECT_TIMEOUT,
        )
        
        def _execute_request() -> dict[str, Any]:
            with httpx.Client(timeout=httpx_timeout, verify=True) as client:
                if method.upper() == "GET":
                    response = client.get(url, headers=self._get_headers())
                else:
                    response = client.post(
                        url, 
                        headers=self._get_headers(),
                        json=data or {}
                    )
                
                response.raise_for_status()
                return response.json()
        
        return retry_with_backoff(_execute_request, max_attempts=3)

    def execute_tool(
        self, 
        agent_id: str, 
        tool_name: str, 
        kwargs: dict[str, Any],
        timeout: float | None = None
    ) -> Any:
        """Execute a single tool via HTTP with caching.

        Args:
            agent_id: Agent identifier
            tool_name: Name of tool to execute
            kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        # Check cache first for read-only tools
        cached_result = self._cache.get(tool_name, kwargs)
        if cached_result is not None:
            logger.debug(f"Returning cached result for {tool_name}")
            return cached_result

        start_time = time.time()

        try:
            response = self._make_request(
                "POST",
                "/execute",
                {
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "kwargs": kwargs,
                    "auth_token": self.auth_token,
                    "timeout": timeout,
                },
                timeout=timeout
            )
            
            duration = time.time() - start_time
            self._metrics.record_tool_execution(tool_name, duration, response.get("success", False))
            
            if not response.get("success", False):
                error_msg = response.get("error", "Unknown error")
                error_context = self._create_error_context(tool_name, kwargs, error_msg)
                raise RuntimeError(error_context)
            
            result = response.get("result")
            
            # Cache result for read-only tools
            self._cache.set(tool_name, kwargs, result)
            
            return result

        except httpx.HTTPStatusError as e:
            duration = time.time() - start_time
            error_type = f"HTTP_{e.response.status_code}"
            self._metrics.record_tool_execution(tool_name, duration, False, error_type)
            
            error_context = self._create_error_context(
                tool_name, kwargs, 
                f"HTTP error: {e.response.status_code} - {e.response.text[:200]}",
                e
            )
            logger.exception(f"HTTP error executing tool {tool_name}: {e}")
            raise RuntimeError(error_context) from e

        except httpx.RequestError as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            self._metrics.record_tool_execution(tool_name, duration, False, error_type)
            
            error_context = self._create_error_context(
                tool_name, kwargs,
                f"Request error: {str(e)}",
                e
            )
            logger.exception(f"Request error executing tool {tool_name}: {e}")
            raise RuntimeError(error_context) from e

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            self._metrics.record_tool_execution(tool_name, duration, False, error_type)
            
            error_context = self._create_error_context(tool_name, kwargs, str(e), e)
            logger.exception(f"Error executing tool {tool_name}: {e}")
            raise RuntimeError(error_context) from e

    def _create_error_context(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        error_msg: str,
        exception: Exception | None = None,
    ) -> str:
        """Create contextual error message with suggestions."""
        # Summarize arguments (truncate long values)
        args_summary = {}
        for key, value in kwargs.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            args_summary[key] = value_str

        context = f"Tool execution failed: {tool_name}\n"
        context += f"Error: {error_msg}\n"
        context += f"Arguments: {json.dumps(args_summary, indent=2)}\n"

        # Add suggestions based on error type
        if exception:
            if isinstance(exception, httpx.HTTPStatusError):
                if exception.response.status_code == 401:
                    context += "\nSuggestion: Authentication failed. Check STRIX_SERVER_TOKEN.\n"
                elif exception.response.status_code == 404:
                    context += "\nSuggestion: Endpoint not found. Server may be using different API version.\n"
                elif exception.response.status_code >= 500:
                    context += "\nSuggestion: Server error. Check server logs and try again.\n"
            elif isinstance(exception, httpx.ConnectError):
                context += "\nSuggestion: Cannot connect to server. Verify server is running and URL is correct.\n"
            elif isinstance(exception, httpx.TimeoutException):
                context += f"\nSuggestion: Request timed out after {self.timeout}s. Consider increasing timeout.\n"

        context += f"\nServer URL: {self.server_url}"
        return context

    def execute_batch(
        self, 
        agent_id: str, 
        tools: list[dict[str, Any]]
    ) -> list[Any]:
        """Execute multiple tools in batch.

        Args:
            agent_id: Agent identifier
            tools: List of tool specifications with 'tool_name' and 'kwargs'

        Returns:
            List of execution results
        """
        start_time = time.time()

        try:
            response = self._make_request(
                "POST",
                "/execute_batch",
                {
                    "agent_id": agent_id,
                    "tools": tools,
                    "auth_token": self.auth_token,
                },
                timeout=self.timeout * 2  # Longer timeout for batches
            )
            
            duration = time.time() - start_time
            
            results = []
            for i, tool_response in enumerate(response.get("results", [])):
                tool_name = tools[i].get("tool_name", "unknown") if i < len(tools) else "unknown"
                tool_duration = duration / len(tools) if tools else duration
                
                if tool_response.get("success", False):
                    results.append(tool_response.get("result"))
                    self._metrics.record_tool_execution(tool_name, tool_duration, True)
                else:
                    error_context = self._create_error_context(
                        tool_name,
                        tools[i].get("kwargs", {}) if i < len(tools) else {},
                        tool_response.get("error", "Unknown error")
                    )
                    results.append({"error": error_context})
                    self._metrics.record_tool_execution(tool_name, tool_duration, False)
            
            return results

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            
            # Record failure for all tools
            for tool in tools:
                tool_name = tool.get("tool_name", "unknown")
                tool_duration = duration / len(tools) if tools else duration
                self._metrics.record_tool_execution(tool_name, tool_duration, False, error_type)
            
            error_context = self._create_error_context(
                "batch_execution",
                {"tool_count": len(tools), "tools": [t.get("tool_name") for t in tools]},
                str(e),
                e
            )
            logger.exception(f"Error executing batch: {e}")
            raise RuntimeError(error_context) from e

    def health_check(self) -> dict[str, Any]:
        """Check server health.

        Returns:
            Health check response
        """
        try:
            response = self._make_request("GET", "/health", timeout=10.0)
            return response
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return {"healthy": False, "error": str(e)}

    def register_agent(self, agent_id: str) -> dict[str, Any]:
        """Register an agent with the server.

        Args:
            agent_id: Agent identifier

        Returns:
            Registration response
        """
        try:
            response = self._make_request(
                "POST",
                "/register_agent",
                {
                    "agent_id": agent_id,
                    "auth_token": self.auth_token,
                }
            )
            return response
        except Exception as e:
            logger.warning(f"Agent registration failed: {e}")
            return {"success": False, "error": str(e)}

    def close(self) -> None:
        """Close client (no-op for HTTP, but kept for interface compatibility)."""
        pass
