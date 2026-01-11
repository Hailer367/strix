"""Remote runtime for connecting to gRPC tool server."""

import logging
import os
from typing import Any

import grpc

from .runtime import AbstractRuntime, SandboxInfo

logger = logging.getLogger(__name__)


class RemoteRuntime(AbstractRuntime):
    """Runtime that connects to a remote gRPC tool server."""

    def __init__(self) -> None:
        """Initialize remote runtime."""
        self.server_url = self._get_server_url()
        self.auth_token = self._get_auth_token()
        self._channel: grpc.Channel | None = None
        self._stub: Any = None

    def _get_server_url(self) -> str:
        """Get server URL from CRED_TUNNEL secret or environment."""
        # First try CRED_TUNNEL secret (for GitHub Actions)
        cred_tunnel = os.getenv("CRED_TUNNEL", "")
        if cred_tunnel:
            # Remove protocol if present, gRPC uses host:port format
            cred_tunnel = cred_tunnel.replace("https://", "").replace("http://", "")
            # Extract host:port (cloudflared gives us a domain)
            # For gRPC, we need to use the domain directly
            return cred_tunnel

        # Fallback to environment variable
        server_url = os.getenv("STRIX_SERVER_URL", "")
        if server_url:
            return server_url.replace("https://", "").replace("http://", "")

        raise ValueError(
            "Remote server URL not found. Set CRED_TUNNEL or STRIX_SERVER_URL environment variable."
        )

    def _get_auth_token(self) -> str:
        """Get authentication token."""
        token = os.getenv("STRIX_SERVER_TOKEN", "")
        if not token:
            raise ValueError("STRIX_SERVER_TOKEN not set. Cannot authenticate with remote server.")
        return token

    def _get_channel(self) -> grpc.Channel:
        """Get or create gRPC channel."""
        if self._channel is None:
            # For cloudflared tunnels, we need to use TLS
            # Extract host and port from URL
            if ":" in self.server_url:
                host, port = self.server_url.split(":", 1)
                port = int(port)
            else:
                host = self.server_url
                port = 443  # Default HTTPS port for cloudflared

            # Create secure channel for cloudflared (TLS required)
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.secure_channel(f"{host}:{port}", credentials)

            logger.info(f"Connected to remote tool server at {host}:{port}")

        return self._channel

    def _get_stub(self) -> Any:
        """Get or create gRPC stub."""
        if self._stub is None:
            try:
                from strix.runtime.remote_tool_server.proto import tool_service_pb2_grpc

                channel = self._get_channel()
                self._stub = tool_service_pb2_grpc.ToolServiceStub(channel)
            except ImportError:
                raise RuntimeError(
                    "Proto files not generated. Server workflow must generate them first."
                )

        return self._stub

    async def create_sandbox(
        self,
        agent_id: str,
        existing_token: str | None = None,
        local_sources: list[dict[str, str]] | None = None,
    ) -> SandboxInfo:
        """Create a sandbox connection to remote server.

        For remote runtime, this just registers the agent with the server.
        """
        try:
            from strix.runtime.remote_tool_server.proto import tool_service_pb2

            stub = self._get_stub()
            # Register agent with server
            request = tool_service_pb2.RegisterAgentRequest(
                agent_id=agent_id,
                auth_token=self.auth_token,
            )
            response = stub.RegisterAgent(request, timeout=10)
            if not response.success:
                raise RuntimeError(f"Failed to register agent: {response.message}")

            # Return sandbox info (remote server doesn't need container_id)
            return {
                "workspace_id": f"remote-{agent_id}",
                "api_url": self.server_url,
                "auth_token": existing_token or self.auth_token,
                "tool_server_port": 0,  # Not used for remote
                "agent_id": agent_id,
            }

        except Exception as e:
            logger.exception(f"Failed to create remote sandbox: {e}")
            raise RuntimeError(f"Failed to connect to remote tool server: {e}") from e

    async def get_sandbox_url(self, container_id: str, port: int) -> str:
        """Get sandbox URL (for remote, this is the server URL)."""
        return f"grpc://{self.server_url}"

    async def destroy_sandbox(self, container_id: str) -> None:
        """Destroy sandbox (for remote, just cleanup connection)."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("Closed connection to remote tool server")
