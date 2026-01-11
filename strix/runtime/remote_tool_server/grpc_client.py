"""gRPC client wrapper for tool execution."""

import json
import logging
import time
from typing import Any

import grpc

from .circuit_breaker import get_circuit_breaker
from .connection_pool import get_connection_pool
from .metrics import get_metrics
from .result_cache import get_cache
from .retry_handler import retry_with_backoff, should_retry

logger = logging.getLogger(__name__)


class GrpcToolClient:
    """Client for executing tools via gRPC with connection pooling and retry logic."""

    def __init__(self, server_url: str, auth_token: str, timeout: float | None = None) -> None:
        """Initialize gRPC client.

        Args:
            server_url: Server URL (host:port or cloudflared domain)
            auth_token: Authentication token
            timeout: Request timeout in seconds (agent-configurable)
        """
        self.server_url = server_url
        self.auth_token = auth_token
        self.timeout = timeout or 60.0
        self._pool = get_connection_pool()
        self._circuit_breaker = get_circuit_breaker(server_url)
        self._metrics = get_metrics()
        self._cache = get_cache()
        self._stub: Any = None

    def _get_channel(self) -> grpc.Channel:
        """Get or create gRPC channel from pool."""
        return self._pool.get_channel(self.server_url, use_tls=True)

    def _get_stub(self) -> Any:
        """Get or create gRPC stub."""
        if self._stub is None:
            try:
                from .proto import tool_service_pb2_grpc

                channel = self._get_channel()
                self._stub = tool_service_pb2_grpc.ToolServiceStub(channel)
            except ImportError:
                raise RuntimeError(
                    "Proto files not generated. Please run generate_proto.py first."
                )

        return self._stub

    def execute_tool(self, agent_id: str, tool_name: str, kwargs: dict[str, Any]) -> Any:
        """Execute a single tool via gRPC with retry, circuit breaker, and caching.

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
        error_type: str | None = None

        def _execute() -> Any:
            """Inner function for retry logic."""
            from .proto import tool_service_pb2

            stub = self._get_stub()

            # Create request
            request = tool_service_pb2.ToolRequest(
                agent_id=agent_id,
                tool_name=tool_name,
                kwargs={k: json.dumps(v) for k, v in kwargs.items()},
                auth_token=self.auth_token,
            )

            # Execute tool through circuit breaker
            response = self._circuit_breaker.call(
                lambda: stub.ExecuteTool(request, timeout=self.timeout)
            )

            if not response.success:
                error_msg = response.error
                # Provide contextual error message
                error_context = self._create_error_context(tool_name, kwargs, error_msg)
                raise RuntimeError(error_context)

            if response.result:
                try:
                    return json.loads(response.result)
                except json.JSONDecodeError:
                    return response.result
            return None

        try:
            # Execute with retry logic
            result = retry_with_backoff(_execute, max_attempts=3)
            duration = time.time() - start_time
            self._metrics.record_tool_execution(tool_name, duration, True)
            # Cache result for read-only tools
            self._cache.set(tool_name, kwargs, result)
            self._pool.release_channel(self.server_url)
            return result

        except grpc.RpcError as e:
            duration = time.time() - start_time
            error_type = str(e.code())
            self._metrics.record_tool_execution(tool_name, duration, False, error_type)
            self._pool.release_channel(self.server_url)

            # Create contextual error message
            error_context = self._create_error_context(
                tool_name, kwargs, f"gRPC error: {e.code()} - {e.details()}", e
            )
            logger.exception(f"gRPC error executing tool {tool_name}: {e}")
            raise RuntimeError(error_context) from e

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            self._metrics.record_tool_execution(tool_name, duration, False, error_type)
            self._pool.release_channel(self.server_url)

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
            if isinstance(exception, grpc.RpcError):
                if exception.code() == grpc.StatusCode.UNAVAILABLE:
                    context += "\nSuggestion: Server may be unavailable. Check server status and network connectivity.\n"
                elif exception.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    context += f"\nSuggestion: Request timed out after {self.timeout}s. Consider increasing timeout or optimizing tool execution.\n"
                elif exception.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
                    context += "\nSuggestion: Server resources exhausted. Wait and retry, or reduce concurrent requests.\n"
            elif "timeout" in str(exception).lower():
                context += f"\nSuggestion: Operation timed out. The tool '{tool_name}' may need more time. Consider increasing timeout.\n"
            elif "connection" in str(exception).lower() or "network" in str(exception).lower():
                context += "\nSuggestion: Network connectivity issue. Verify server is running and accessible.\n"

        context += f"\nDocumentation: See tool documentation for {tool_name} usage and requirements."

        return context

    def execute_batch(
        self, agent_id: str, tools: list[dict[str, Any]]
    ) -> list[Any]:
        """Execute multiple tools in batch with retry and circuit breaker.

        Args:
            agent_id: Agent identifier
            tools: List of tool specifications with 'tool_name' and 'kwargs'

        Returns:
            List of execution results
        """
        start_time = time.time()

        def _execute_batch() -> list[Any]:
            """Inner function for retry logic."""
            from .proto import tool_service_pb2

            stub = self._get_stub()

            # Create batch request
            tool_specs = []
            for tool in tools:
                spec = tool_service_pb2.ToolSpec(
                    tool_name=tool["tool_name"],
                    kwargs={k: json.dumps(v) for k, v in tool.get("kwargs", {}).items()},
                )
                tool_specs.append(spec)

            request = tool_service_pb2.BatchToolRequest(
                agent_id=agent_id,
                tools=tool_specs,
                auth_token=self.auth_token,
            )

            # Use longer timeout for batches
            batch_timeout = self.timeout * 2
            response = self._circuit_breaker.call(
                lambda: stub.ExecuteBatch(request, timeout=batch_timeout)
            )

            results = []
            for i, tool_response in enumerate(response.results):
                tool_name = tools[i].get("tool_name", "unknown")
                if tool_response.success:
                    if tool_response.result:
                        try:
                            results.append(json.loads(tool_response.result))
                        except json.JSONDecodeError:
                            results.append(tool_response.result)
                    else:
                        results.append(None)
                else:
                    # Create contextual error for batch failures
                    error_context = self._create_error_context(
                        tool_name,
                        tools[i].get("kwargs", {}),
                        tool_response.error,
                    )
                    results.append({"error": error_context})

            return results

        try:
            result = retry_with_backoff(_execute_batch, max_attempts=3)
            duration = time.time() - start_time
            # Record metrics for each tool in batch
            for tool in tools:
                tool_name = tool.get("tool_name", "unknown")
                # Approximate duration per tool
                tool_duration = duration / len(tools) if tools else duration
                self._metrics.record_tool_execution(tool_name, tool_duration, True)
            self._pool.release_channel(self.server_url)
            return result

        except grpc.RpcError as e:
            duration = time.time() - start_time
            error_type = str(e.code())
            # Record failure for all tools in batch
            for tool in tools:
                tool_name = tool.get("tool_name", "unknown")
                tool_duration = duration / len(tools) if tools else duration
                self._metrics.record_tool_execution(tool_name, tool_duration, False, error_type)
            self._pool.release_channel(self.server_url)

            error_context = self._create_error_context(
                "batch_execution",
                {"tool_count": len(tools), "tools": [t.get("tool_name") for t in tools]},
                f"gRPC batch error: {e.code()} - {e.details()}",
                e,
            )
            logger.exception(f"gRPC error executing batch: {e}")
            raise RuntimeError(error_context) from e

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            for tool in tools:
                tool_name = tool.get("tool_name", "unknown")
                tool_duration = duration / len(tools) if tools else duration
                self._metrics.record_tool_execution(tool_name, tool_duration, False, error_type)
            self._pool.release_channel(self.server_url)

            error_context = self._create_error_context(
                "batch_execution",
                {"tool_count": len(tools)},
                str(e),
                e,
            )
            logger.exception(f"Error executing batch: {e}")
            raise RuntimeError(error_context) from e

    def close(self) -> None:
        """Release channel back to pool."""
        self._pool.release_channel(self.server_url)
        self._stub = None
