"""gRPC client wrapper for tool execution."""

import json
import logging
from typing import Any

import grpc

logger = logging.getLogger(__name__)


class GrpcToolClient:
    """Client for executing tools via gRPC."""

    def __init__(self, server_url: str, auth_token: str) -> None:
        """Initialize gRPC client.

        Args:
            server_url: Server URL (host:port or cloudflared domain)
            auth_token: Authentication token
        """
        self.server_url = server_url
        self.auth_token = auth_token
        self._channel: grpc.Channel | None = None
        self._stub: Any = None

    def _get_channel(self) -> grpc.Channel:
        """Get or create gRPC channel."""
        if self._channel is None:
            # Parse server URL
            if ":" in self.server_url:
                host, port = self.server_url.split(":", 1)
                port = int(port)
            else:
                host = self.server_url
                port = 443  # Default HTTPS port for cloudflared

            # Create secure channel (required for cloudflared)
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.secure_channel(f"{host}:{port}", credentials)

        return self._channel

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
        """Execute a single tool via gRPC.

        Args:
            agent_id: Agent identifier
            tool_name: Name of tool to execute
            kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        try:
            from .proto import tool_service_pb2

            stub = self._get_stub()

            # Create request
            request = tool_service_pb2.ToolRequest(
                agent_id=agent_id,
                tool_name=tool_name,
                kwargs={k: json.dumps(v) for k, v in kwargs.items()},
                auth_token=self.auth_token,
            )

            # Execute tool
            response = stub.ExecuteTool(request, timeout=60)

            if not response.success:
                raise RuntimeError(f"Tool execution failed: {response.error}")

            if response.result:
                try:
                    return json.loads(response.result)
                except json.JSONDecodeError:
                    return response.result
            return None

        except grpc.RpcError as e:
            logger.exception(f"gRPC error executing tool {tool_name}: {e}")
            raise RuntimeError(f"gRPC error: {e.code()} - {e.details()}") from e

    def execute_batch(
        self, agent_id: str, tools: list[dict[str, Any]]
    ) -> list[Any]:
        """Execute multiple tools in batch.

        Args:
            agent_id: Agent identifier
            tools: List of tool specifications with 'tool_name' and 'kwargs'

        Returns:
            List of execution results
        """
        try:
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

            response = stub.ExecuteBatch(request, timeout=120)

            results = []
            for tool_response in response.results:
                if tool_response.success:
                    if tool_response.result:
                        try:
                            results.append(json.loads(tool_response.result))
                        except json.JSONDecodeError:
                            results.append(tool_response.result)
                    else:
                        results.append(None)
                else:
                    results.append({"error": tool_response.error})

            return results

        except grpc.RpcError as e:
            logger.exception(f"gRPC error executing batch: {e}")
            raise RuntimeError(f"gRPC batch error: {e.code()} - {e.details()}") from e

    def close(self) -> None:
        """Close gRPC channel."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None
