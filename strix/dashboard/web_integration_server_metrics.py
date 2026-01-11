"""Integration for updating dashboard with remote tool server metrics."""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def update_server_metrics(metrics: dict[str, Any]) -> None:
    """Update dashboard with remote tool server metrics.

    Args:
        metrics: Server metrics dictionary
    """
    try:
        from .web_server import update_dashboard_state

        update_dashboard_state({"server_metrics": metrics})
        logger.debug("Updated dashboard with server metrics")
    except Exception as e:
        logger.warning(f"Failed to update server metrics in dashboard: {e}")


def fetch_server_metrics_from_remote() -> dict[str, Any] | None:
    """Fetch metrics from remote tool server if available.

    Returns:
        Metrics dictionary or None if not available
    """
    try:
        import os
        import requests

        cred_tunnel = os.getenv("CRED_TUNNEL")
        server_token = os.getenv("STRIX_SERVER_TOKEN")

        if not cred_tunnel or not server_token:
            return None

        # Parse server URL
        server_url = cred_tunnel.replace("grpc://", "").replace("https://", "").replace("http://", "")
        if ":" not in server_url:
            server_url = f"{server_url}:443"

        # Try to get metrics via gRPC health check
        try:
            import grpc
            from strix.runtime.remote_tool_server.proto import tool_service_pb2, tool_service_pb2_grpc

            credentials = grpc.ssl_channel_credentials()
            channel = grpc.secure_channel(server_url, credentials)
            stub = tool_service_pb2_grpc.ToolServiceStub(channel)

            request = tool_service_pb2.HealthRequest()
            response = stub.HealthCheck(request, timeout=5)

            # Parse metrics from health response
            import json
            health_data = json.loads(response.network_status) if response.network_status else {}
            metrics = health_data.get("metrics", {})
            pool_stats = health_data.get("connection_pool", {})
            circuit_breaker = health_data.get("circuit_breaker", {})

            return {
                "uptime_seconds": metrics.get("uptime_seconds", 0),
                "request_rate_per_minute": metrics.get("request_rate", 0),
                "error_rate": metrics.get("error_rate", 0.0),
                "total_requests": metrics.get("total_requests", 0),
                "tool_count": response.tool_count,
                "connection_pool": {
                    "pool_size": pool_stats.get("pool_size", 0),
                    "active_connections": pool_stats.get("active_connections", 0),
                },
                "circuit_breaker": {
                    "state": circuit_breaker.get("state", "closed"),
                },
            }
        except Exception as e:
            logger.debug(f"Could not fetch remote server metrics: {e}")
            return None

    except Exception as e:
        logger.warning(f"Error fetching server metrics: {e}")
        return None
