"""Strix Real-Time Dashboard Module.

This module provides a real-time dashboard for monitoring Strix agent activity,
including:
- Agent status and activity tracking
- Time remaining countdown
- Resource usage (tokens, cost)
- Tool execution logs
- Vulnerability findings
"""

from .dashboard import Dashboard, DashboardWidget
from .time_tracker import TimeTracker


__all__ = [
    "Dashboard",
    "DashboardWidget",
    "TimeTracker",
]
