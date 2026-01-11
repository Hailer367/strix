"""Remote runtime for connecting to HTTP tool server (Cloudflared-compatible).

This replaces the gRPC-based remote runtime with HTTP-based communication
that works properly with Cloudflared tunnels.
"""

import logging
import os
from typing import Any

from .runtime import AbstractRuntime, SandboxInfo

logger = logging.getLogger(__name__)


class RemoteRuntime(AbstractRuntime):
    """Runtime that connects to a remote HTTP tool server."""

    def __init__(self) -> None:
        """Initialize remote runtime."""
        self.server_url = self._get_server_url()
        self.auth_token = self._get_auth_token()
        self._client: Any = None

    def _get_server_url(self) -> str:
        """Get server URL from CRED_TUNNEL secret or environment."""
        # First try CRED_TUNNEL secret (for GitHub Actions)
        cred_tunnel = os.getenv("CRED_TUNNEL", "")
        if cred_tunnel:
            # Remove protocol prefix and port suffix if present
            url = cred_tunnel.replace("https://", "").replace("http://", "")
            # Remove :443 suffix if present (cloudflared default)
            if url.endswith(":443"):
                url = url[:-4]
            # Return as https URL for cloudflared
            return f"https://{url}"

        # Fallback to environment variable
        server_url = os.getenv("STRIX_SERVER_URL", "")
        if server_url:
            if not server_url.startswith("http://") and not server_url.startswith("https://"):
                server_url = f"https://{server_url}"
            return server_url

        raise ValueError(
            "Remote server URL not found. Set CRED_TUNNEL or STRIX_SERVER_URL environment variable."
        )

    def _get_auth_token(self) -> str:
        """Get authentication token."""
        token = os.getenv("STRIX_SERVER_TOKEN", "")
        if not token:
            raise ValueError("STRIX_SERVER_TOKEN not set. Cannot authenticate with remote server.")
        return token

    def _get_client(self) -> Any:
        """Get or create HTTP client."""
        if self._client is None:
            from strix.runtime.remote_tool_server.http_client import HttpToolClient
            self._client = HttpToolClient(self.server_url, self.auth_token)
            logger.info(f"Connected to remote HTTP tool server at {self.server_url}")
        return self._client

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
            client = self._get_client()
            
            # Register agent with server
            response = client.register_agent(agent_id)
            
            if not response.get("success", False):
                raise RuntimeError(f"Failed to register agent: {response.get('error', 'Unknown error')}")

            logger.info(f"Agent {agent_id} registered with remote server")

            # Return sandbox info
            return {
                "workspace_id": f"remote-{agent_id}",
                "api_url": self.server_url,
                "auth_token": existing_token or self.auth_token,
                "tool_server_port": 0,  # Not used for remote HTTP
                "agent_id": agent_id,
            }

        except Exception as e:
            logger.exception(f"Failed to create remote sandbox: {e}")
            raise RuntimeError(f"Failed to connect to remote tool server: {e}") from e

    async def get_sandbox_url(self, container_id: str, port: int) -> str:
        """Get sandbox URL (for remote, this is the server URL)."""
        return self.server_url

    async def destroy_sandbox(self, container_id: str) -> None:
        """Destroy sandbox (for remote, just cleanup connection)."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Closed connection to remote HTTP tool server")
