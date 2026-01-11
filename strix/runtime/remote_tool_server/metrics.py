"""Metrics collection for remote tool server."""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""

    tool_name: str
    execution_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0
    recent_durations: deque = field(default_factory=lambda: deque(maxlen=100))

    def record_execution(self, duration: float, success: bool) -> None:
        """Record a tool execution."""
        self.execution_count += 1
        self.total_duration += duration
        self.recent_durations.append(duration)

        if duration < self.min_duration:
            self.min_duration = duration
        if duration > self.max_duration:
            self.max_duration = duration

        if success:
            self.success_count += 1
        else:
            self.error_count += 1

    def get_stats(self) -> dict[str, Any]:
        """Get statistics for this tool."""
        if self.execution_count == 0:
            return {
                "tool_name": self.tool_name,
                "execution_count": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
            }

        durations = list(self.recent_durations) if self.recent_durations else []
        avg_duration = self.total_duration / self.execution_count if self.execution_count > 0 else 0.0

        # Calculate percentiles
        p50 = p95 = p99 = 0.0
        if durations:
            sorted_durations = sorted(durations)
            p50 = sorted_durations[int(len(sorted_durations) * 0.50)]
            p95 = sorted_durations[int(len(sorted_durations) * 0.95)] if len(sorted_durations) > 1 else sorted_durations[-1]
            p99 = sorted_durations[int(len(sorted_durations) * 0.99)] if len(sorted_durations) > 1 else sorted_durations[-1]

        return {
            "tool_name": self.tool_name,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_count / self.execution_count if self.execution_count > 0 else 0.0,
            "avg_duration": avg_duration,
            "min_duration": self.min_duration if self.min_duration != float("inf") else 0.0,
            "max_duration": self.max_duration,
            "p50_duration": p50,
            "p95_duration": p95,
            "p99_duration": p99,
        }


class ServerMetrics:
    """Metrics collector for the remote tool server."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._tool_metrics: dict[str, ToolMetrics] = {}
        self._request_count = 0
        self._error_count = 0
        self._start_time = time.time()
        self._lock = threading.Lock()
        self._recent_requests: deque = deque(maxlen=1000)  # Last 1000 requests

    def record_tool_execution(
        self, tool_name: str, duration: float, success: bool, error_type: str | None = None
    ) -> None:
        """Record a tool execution."""
        with self._lock:
            if tool_name not in self._tool_metrics:
                self._tool_metrics[tool_name] = ToolMetrics(tool_name=tool_name)

            self._tool_metrics[tool_name].record_execution(duration, success)
            self._request_count += 1

            if not success:
                self._error_count += 1

            # Record recent request
            self._recent_requests.append({
                "tool_name": tool_name,
                "duration": duration,
                "success": success,
                "error_type": error_type,
                "timestamp": time.time(),
            })

    def get_tool_metrics(self, tool_name: str | None = None) -> dict[str, Any]:
        """Get metrics for a specific tool or all tools."""
        with self._lock:
            if tool_name:
                if tool_name in self._tool_metrics:
                    return self._tool_metrics[tool_name].get_stats()
                return {}

            return {
                tool: metrics.get_stats()
                for tool, metrics in self._tool_metrics.items()
            }

    def get_server_stats(self) -> dict[str, Any]:
        """Get overall server statistics."""
        with self._lock:
            uptime = time.time() - self._start_time
            error_rate = self._error_count / self._request_count if self._request_count > 0 else 0.0

            # Calculate request rate (requests per minute)
            recent_window = 60.0  # Last 60 seconds
            now = time.time()
            recent_requests = [
                r for r in self._recent_requests
                if (now - r["timestamp"]) <= recent_window
            ]
            request_rate = len(recent_requests)

            return {
                "uptime_seconds": int(uptime),
                "total_requests": self._request_count,
                "total_errors": self._error_count,
                "error_rate": error_rate,
                "request_rate_per_minute": request_rate,
                "tool_count": len(self._tool_metrics),
                "tools": self.get_tool_metrics(),
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._tool_metrics.clear()
            self._request_count = 0
            self._error_count = 0
            self._start_time = time.time()
            self._recent_requests.clear()


# Global metrics instance
_global_metrics: ServerMetrics | None = None
_metrics_lock = threading.Lock()


def get_metrics() -> ServerMetrics:
    """Get or create global metrics instance."""
    global _global_metrics
    with _metrics_lock:
        if _global_metrics is None:
            _global_metrics = ServerMetrics()
        return _global_metrics
