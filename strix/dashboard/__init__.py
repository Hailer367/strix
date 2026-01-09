"""Strix Real-Time Dashboard Module.

This module provides a real-time dashboard for monitoring Strix agent activity,
including:
- Agent status and activity tracking
- Time remaining countdown
- Resource usage (tokens, cost)
- Tool execution logs
- Vulnerability findings
- Web-based dashboard for remote monitoring (GitHub Actions)
"""

from .dashboard import Dashboard, DashboardWidget
from .history import HistoricalDataTracker, get_historical_tracker
from .time_tracker import TimeTracker
from .web_server import (
    WebDashboardServer,
    get_web_dashboard_server,
    start_web_dashboard,
    stop_web_dashboard,
    update_dashboard_state,
    add_live_feed_entry,
    add_tool_execution,
    add_chat_message,
    add_thinking_entry,
    add_agent_created_entry,
    add_error_entry,
    get_dashboard_state,
)
from .web_integration import (
    WebDashboardIntegration,
    get_integration,
    setup_web_dashboard,
    teardown_web_dashboard,
)


__all__ = [
    "Dashboard",
    "DashboardWidget",
    "HistoricalDataTracker",
    "get_historical_tracker",
    "TimeTracker",
    # Web dashboard exports
    "WebDashboardServer",
    "get_web_dashboard_server",
    "start_web_dashboard",
    "stop_web_dashboard",
    "update_dashboard_state",
    "add_live_feed_entry",
    "add_tool_execution",
    "add_chat_message",
    "add_thinking_entry",
    "add_agent_created_entry",
    "add_error_entry",
    "get_dashboard_state",
    # Integration exports
    "WebDashboardIntegration",
    "get_integration",
    "setup_web_dashboard",
    "teardown_web_dashboard",
]