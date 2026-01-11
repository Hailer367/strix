"""Connection pool manager for gRPC channels."""

import logging
import threading
import time
from typing import Any

import grpc

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Manages a pool of gRPC channels for reuse."""

    def __init__(self, max_connections: int = 5, idle_timeout: int = 300) -> None:
        """Initialize connection pool.

        Args:
            max_connections: Maximum number of connections in pool
            idle_timeout: Seconds before idle connection is closed
        """
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout
        self._pool: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._active_connections: dict[str, int] = {}  # server_url -> count

    def get_channel(self, server_url: str, use_tls: bool = True) -> grpc.Channel:
        """Get or create a gRPC channel from pool.

        Args:
            server_url: Server URL (host:port)
            use_tls: Whether to use TLS (required for cloudflared)

        Returns:
            gRPC channel
        """
        with self._lock:
            # Parse server URL
            if ":" in server_url:
                host, port = server_url.split(":", 1)
                port = int(port)
            else:
                host = server_url
                port = 443 if use_tls else 80

            # Look for existing idle connection
            now = time.time()
            for conn in self._pool:
                if (
                    conn["host"] == host
                    and conn["port"] == port
                    and conn["use_tls"] == use_tls
                    and (now - conn["last_used"]) < self.idle_timeout
                ):
                    conn["last_used"] = now
                    self._active_connections[server_url] = (
                        self._active_connections.get(server_url, 0) + 1
                    )
                    logger.debug(f"Reusing connection to {host}:{port}")
                    return conn["channel"]

            # Create new connection if pool not full
            if len(self._pool) < self.max_connections:
                if use_tls:
                    credentials = grpc.ssl_channel_credentials()
                    channel = grpc.secure_channel(f"{host}:{port}", credentials)
                else:
                    channel = grpc.insecure_channel(f"{host}:{port}")

                conn = {
                    "host": host,
                    "port": port,
                    "use_tls": use_tls,
                    "channel": channel,
                    "last_used": now,
                    "created_at": now,
                }
                self._pool.append(conn)
                self._active_connections[server_url] = (
                    self._active_connections.get(server_url, 0) + 1
                )
                logger.debug(f"Created new connection to {host}:{port}")
                return channel

            # Pool full, create temporary connection
            logger.warning(
                f"Connection pool full, creating temporary connection to {host}:{port}"
            )
            if use_tls:
                credentials = grpc.ssl_channel_credentials()
                return grpc.secure_channel(f"{host}:{port}", credentials)
            return grpc.insecure_channel(f"{host}:{port}")

    def release_channel(self, server_url: str) -> None:
        """Release a channel back to pool (mark as available).

        Args:
            server_url: Server URL that was using the channel
        """
        with self._lock:
            if server_url in self._active_connections:
                self._active_connections[server_url] = max(
                    0, self._active_connections[server_url] - 1
                )

    def cleanup_idle(self) -> None:
        """Remove idle connections from pool."""
        with self._lock:
            now = time.time()
            self._pool = [
                conn
                for conn in self._pool
                if (now - conn["last_used"]) < self.idle_timeout
            ]

    def get_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        with self._lock:
            return {
                "pool_size": len(self._pool),
                "max_connections": self.max_connections,
                "active_connections": sum(self._active_connections.values()),
                "connections_by_server": self._active_connections.copy(),
            }

    def shutdown(self) -> None:
        """Close all connections in pool."""
        with self._lock:
            for conn in self._pool:
                try:
                    conn["channel"].close()
                except Exception as e:
                    logger.warning(f"Error closing channel: {e}")
            self._pool.clear()
            self._active_connections.clear()


# Global connection pool instance
_global_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def get_connection_pool() -> ConnectionPool:
    """Get or create global connection pool."""
    global _global_pool
    with _pool_lock:
        if _global_pool is None:
            _global_pool = ConnectionPool()
        return _global_pool
