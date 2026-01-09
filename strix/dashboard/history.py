"""Historical Data Tracking for Dashboard.

This module provides a rolling window of historical data for time-series charts
and analytics. Data is stored in memory with configurable retention periods.
"""

import logging
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class HistoricalDataTracker:
    """Tracks historical metrics with a rolling time window.
    
    This class maintains a circular buffer of time-series data points
    for the last N seconds (configurable). Data older than the window
    is automatically evicted.
    """
    
    def __init__(self, window_seconds: int = 7200):  # 2 hours default
        """Initialize the tracker.
        
        Args:
            window_seconds: Maximum age of data points in seconds (default: 2 hours)
        """
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        
        # Time-series data: list of (timestamp, data_dict) tuples
        self._data_points: deque[tuple[datetime, dict[str, Any]]] = deque(maxlen=10000)
        
        # Event tracking: tool executions, agent status changes, etc.
        self._events: deque[dict[str, Any]] = deque(maxlen=5000)
    
    def add_data_point(self, metrics: dict[str, Any]) -> None:
        """Add a new data point with current timestamp.
        
        Args:
            metrics: Dictionary containing metric values (tokens, cost, rate, etc.)
        """
        with self._lock:
            now = datetime.now(UTC)
            self._data_points.append((now, metrics.copy()))
            self._cleanup_old_data(now)
    
    def add_event(
        self,
        event_type: str,
        data: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> None:
        """Add an event to the history.
        
        Args:
            event_type: Type of event ('tool_execution', 'agent_status_change', etc.)
            data: Event data dictionary
            timestamp: Optional timestamp (defaults to now)
        """
        with self._lock:
            event = {
                "type": event_type,
                "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
                **data,
            }
            self._events.append(event)
    
    def _cleanup_old_data(self, current_time: datetime) -> None:
        """Remove data points older than the window."""
        cutoff = current_time - timedelta(seconds=self.window_seconds)
        
        # Remove old data points from the front
        while self._data_points and self._data_points[0][0] < cutoff:
            self._data_points.popleft()
        
        # Remove old events
        cutoff_iso = cutoff.isoformat()
        while self._events and self._events[0].get("timestamp", "") < cutoff_iso:
            self._events.popleft()
    
    def get_metrics(
        self,
        metric_name: str | None = None,
        window_seconds: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get metrics data points within a time window.
        
        Args:
            metric_name: Optional specific metric to filter by
            window_seconds: Optional custom window (defaults to instance window)
        
        Returns:
            List of data points with timestamps, filtered by window and optionally by metric
        """
        with self._lock:
            window = window_seconds or self.window_seconds
            cutoff = datetime.now(UTC) - timedelta(seconds=window)
            
            result = []
            for timestamp, metrics in self._data_points:
                if timestamp >= cutoff:
                    if metric_name:
                        if metric_name in metrics:
                            result.append({
                                "timestamp": timestamp.isoformat(),
                                "value": metrics[metric_name],
                                **metrics,
                            })
                    else:
                        result.append({
                            "timestamp": timestamp.isoformat(),
                            **metrics,
                        })
            
            return sorted(result, key=lambda x: x["timestamp"])
    
    def get_events(
        self,
        event_type: str | None = None,
        window_seconds: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get events within a time window.
        
        Args:
            event_type: Optional event type filter
            window_seconds: Optional custom window
        
        Returns:
            List of events, filtered by window and optionally by type
        """
        with self._lock:
            window = window_seconds or self.window_seconds
            cutoff_iso = (datetime.now(UTC) - timedelta(seconds=window)).isoformat()
            
            result = []
            for event in self._events:
                if event.get("timestamp", "") >= cutoff_iso:
                    if event_type is None or event.get("type") == event_type:
                        result.append(event.copy())
            
            return sorted(result, key=lambda x: x.get("timestamp", ""))
    
    def get_summary_stats(self, window_seconds: int | None = None) -> dict[str, Any]:
        """Get summary statistics for the time window.
        
        Args:
            window_seconds: Optional custom window
        
        Returns:
            Dictionary with aggregated statistics
        """
        metrics = self.get_metrics(window_seconds=window_seconds)
        
        if not metrics:
            return {
                "data_points": 0,
                "window_seconds": window_seconds or self.window_seconds,
            }
        
        # Aggregate statistics
        total_tokens = sum(m.get("tokens", {}).get("input", 0) + m.get("tokens", {}).get("output", 0) for m in metrics)
        total_cost = sum(m.get("cost", 0) for m in metrics)
        total_requests = sum(m.get("requests", 0) for m in metrics)
        
        return {
            "data_points": len(metrics),
            "window_seconds": window_seconds or self.window_seconds,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "total_requests": total_requests,
            "avg_tokens_per_minute": total_tokens / max((window_seconds or self.window_seconds) / 60, 1),
            "avg_cost_per_minute": total_cost / max((window_seconds or self.window_seconds) / 60, 1),
            "avg_requests_per_minute": total_requests / max((window_seconds or self.window_seconds) / 60, 1),
        }
    
    def clear(self) -> None:
        """Clear all historical data."""
        with self._lock:
            self._data_points.clear()
            self._events.clear()
    
    def get_size(self) -> dict[str, int]:
        """Get current size of stored data."""
        with self._lock:
            return {
                "data_points": len(self._data_points),
                "events": len(self._events),
            }


# Global instance
_global_tracker: HistoricalDataTracker | None = None
_tracker_lock = threading.Lock()


def get_historical_tracker() -> HistoricalDataTracker:
    """Get or create the global historical data tracker."""
    global _global_tracker
    with _tracker_lock:
        if _global_tracker is None:
            _global_tracker = HistoricalDataTracker()
        return _global_tracker