"""Web-Based Dashboard Server for Strix.

This module provides a web-based real-time dashboard server that can be accessed
through a browser during GitHub Actions workflow runs. It uses Server-Sent Events (SSE)
for real-time streaming updates of agent activity, collaboration status, and scan progress.

The dashboard is INFORMATION ONLY - it does NOT control the agent in any way.
"""

import asyncio
import csv
import io
import json
import logging
import mimetypes
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .dashboard import Dashboard, AgentStatus, ResourceUsage, VulnerabilityEntry
from .history import get_historical_tracker
from .time_tracker import TimeTracker

logger = logging.getLogger(__name__)


# Global state for sharing between threads
_web_dashboard_state: dict[str, Any] = {
    "scan_config": {},
    "agents": {},
    "tool_executions": [],
    "chat_messages": [],
    "vulnerabilities": [],
    "collaboration": {
        "claims": [],
        "findings": [],
        "work_queue": [],
        "help_requests": [],
        "messages": [],
        "stats": {},
    },
    "resources": {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_cost": 0.0,
        "request_count": 0,
        "api_calls": 0,
    },
    "rate_limiter": {
        "current_rate": 0,
        "max_rate": 60,
        "remaining_capacity": 60,
        "total_requests": 0,
        "total_wait_time": 0.0,
    },
    "time": {
        "start_time": None,
        "duration_minutes": 60,
        "warning_minutes": 5,
        "elapsed_minutes": 0,
        "remaining_minutes": 60,
        "progress_percentage": 0,
        "status": "Not started",
        "is_warning": False,
        "is_critical": False,
    },
    "current_step": {
        "agent_id": None,
        "agent_name": None,
        "action": None,
        "tool_name": None,
        "status": "idle",
        "details": {},
    },
    "live_feed": [],  # CLI-like activity feed
    "last_updated": None,
}

_sse_clients: list[Any] = []
_update_lock = threading.Lock()


def get_dashboard_state() -> dict[str, Any]:
    """Get the current dashboard state (thread-safe)."""
    with _update_lock:
        return _web_dashboard_state.copy()


def update_dashboard_state(updates: dict[str, Any]) -> None:
    """Update dashboard state and notify SSE clients (thread-safe)."""
    global _web_dashboard_state
    
    with _update_lock:
        for key, value in updates.items():
            if key in _web_dashboard_state:
                if isinstance(_web_dashboard_state[key], dict) and isinstance(value, dict):
                    _web_dashboard_state[key].update(value)
                else:
                    _web_dashboard_state[key] = value
        
        _web_dashboard_state["last_updated"] = datetime.now(UTC).isoformat()


def add_live_feed_entry(entry: dict[str, Any]) -> None:
    """Add an entry to the CLI-like live feed."""
    with _update_lock:
        # Add timestamp
        entry["timestamp"] = datetime.now(UTC).isoformat()
        
        # Add to feed (keep last 500 entries)
        _web_dashboard_state["live_feed"].append(entry)
        if len(_web_dashboard_state["live_feed"]) > 500:
            _web_dashboard_state["live_feed"] = _web_dashboard_state["live_feed"][-500:]


def add_thinking_entry(
    agent_id: str | None,
    agent_name: str | None,
    content: str,
) -> None:
    """Add a thinking/reasoning entry to the live feed.
    
    This shows the AI's internal reasoning process, similar to how
    CLI-based agents like Claude Code display their thinking.
    
    Args:
        agent_id: The agent's ID
        agent_name: The agent's name
        content: The thinking content (will be truncated if too long)
    """
    # Truncate very long thinking to keep feed readable
    max_length = 500
    if len(content) > max_length:
        content = content[:max_length] + "..."
    
    add_live_feed_entry({
        "type": "thinking",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "content": content,
    })


def add_agent_created_entry(
    agent_id: str,
    agent_name: str,
    task: str,
    parent_id: str | None = None,
) -> None:
    """Add an agent creation entry to the live feed."""
    add_live_feed_entry({
        "type": "agent_created",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "task": task[:200] if task else "",
        "parent_id": parent_id,
    })


def add_error_entry(
    agent_id: str | None,
    agent_name: str | None,
    error_message: str,
    error_type: str = "error",
) -> None:
    """Add an error entry to the live feed."""
    add_live_feed_entry({
        "type": "error",
        "agent_id": agent_id,
        "agent_name": agent_name,
        "message": error_message[:500] if error_message else "Unknown error",
        "error_type": error_type,
    })


def add_tool_execution(tool_data: dict[str, Any]) -> None:
    """Add a tool execution to the state."""
    with _update_lock:
        _web_dashboard_state["tool_executions"].append(tool_data)
        
        # Keep last 200 tool executions
        if len(_web_dashboard_state["tool_executions"]) > 200:
            _web_dashboard_state["tool_executions"] = _web_dashboard_state["tool_executions"][-200:]
        
        # Also add to live feed with enhanced information
        status = tool_data.get("status", "running")
        duration = tool_data.get("duration_seconds")
        error_msg = tool_data.get("error_message")
        
        # Format duration for display
        duration_str = ""
        if duration is not None:
            if duration < 1:
                duration_str = f" ({duration*1000:.0f}ms)"
            else:
                duration_str = f" ({duration:.2f}s)"
        
        # Create feed entry
        feed_entry = {
            "type": "tool_execution",
            "tool_name": tool_data.get("tool_name", "unknown"),
            "status": status,
            "agent_id": tool_data.get("agent_id"),
            "args_summary": _summarize_args(tool_data.get("args", {})),
            "duration": duration_str,
        }
        
        # Add error information if failed
        if status == "failed" and error_msg:
            feed_entry["error"] = error_msg[:100] + ("..." if len(error_msg) > 100 else "")
        
        add_live_feed_entry(feed_entry)


def add_chat_message(message: dict[str, Any]) -> None:
    """Add a chat message to the state."""
    with _update_lock:
        _web_dashboard_state["chat_messages"].append(message)
        
        # Keep last 200 messages
        if len(_web_dashboard_state["chat_messages"]) > 200:
            _web_dashboard_state["chat_messages"] = _web_dashboard_state["chat_messages"][-200:]
        
        # Also add to live feed
        content_preview = message.get("content", "")[:100]
        if len(message.get("content", "")) > 100:
            content_preview += "..."
        
        add_live_feed_entry({
            "type": "chat_message",
            "role": message.get("role", "unknown"),
            "agent_id": message.get("agent_id"),
            "content_preview": content_preview,
        })


def _summarize_args(args: dict[str, Any]) -> str:
    """Create a brief summary of tool arguments."""
    if not args:
        return ""
    
    # Get first key-value pair
    for key, value in list(args.items())[:1]:
        str_val = str(value)
        if len(str_val) > 50:
            str_val = str_val[:47] + "..."
        return f"{key}={str_val}"
    
    return ""


class DashboardHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard web server."""
    
    def log_message(self, format: str, *args: Any) -> None:
        """Override to use Python logging."""
        logger.debug(f"HTTP: {format % args}")
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        # API endpoints
        if path == "/api/state":
            self._serve_state_json()
        elif path == "/api/stream":
            self._serve_sse_stream()
        elif path == "/api/live-feed":
            self._serve_live_feed()
        elif path.startswith("/api/history"):
            self._serve_history(query_params)
        elif path.startswith("/api/export"):
            self._serve_export(query_params)
        elif path == "/health":
            self._serve_health()
        # Static file serving (Next.js build output)
        elif path == "/" or path == "/index.html" or not path.startswith("/api"):
            self._serve_static_file(path)
        else:
            self._send_404()
    
    def _send_response_headers(self, content_type: str, status: int = 200) -> None:
        """Send standard HTTP response headers."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
    
    def _serve_health(self) -> None:
        """Serve health check endpoint."""
        self._send_response_headers("application/json")
        self.wfile.write(json.dumps({"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}).encode())
    
    def _serve_state_json(self) -> None:
        """Serve the current dashboard state as JSON."""
        self._send_response_headers("application/json")
        state = get_dashboard_state()
        self.wfile.write(json.dumps(state, default=str).encode())
    
    def _serve_live_feed(self) -> None:
        """Serve the live feed entries."""
        self._send_response_headers("application/json")
        with _update_lock:
            feed = _web_dashboard_state.get("live_feed", [])[-100:]
        self.wfile.write(json.dumps(feed, default=str).encode())
    
    def _serve_sse_stream(self) -> None:
        """Serve Server-Sent Events stream for real-time updates."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        # Send initial state
        state = get_dashboard_state()
        self.wfile.write(f"event: state\ndata: {json.dumps(state, default=str)}\n\n".encode())
        self.wfile.flush()
        
        last_update = state.get("last_updated")
        
        try:
            while True:
                time.sleep(1)  # Poll every second
                
                current_state = get_dashboard_state()
                current_update = current_state.get("last_updated")
                
                if current_update != last_update:
                    self.wfile.write(f"event: update\ndata: {json.dumps(current_state, default=str)}\n\n".encode())
                    self.wfile.flush()
                    last_update = current_update
                else:
                    # Send keepalive
                    self.wfile.write(f": keepalive {datetime.now(UTC).isoformat()}\n\n".encode())
                    self.wfile.flush()
                    
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("SSE client disconnected")
    
    def _serve_static_file(self, path: str) -> None:
        """Serve static files from Next.js build output."""
        # Get the frontend build directory
        dashboard_dir = Path(__file__).parent
        frontend_out = dashboard_dir / "frontend" / "out"
        
        # Normalize path
        if path == "/" or path == "/index.html":
            file_path = frontend_out / "index.html"
        else:
            # Remove leading slash and resolve
            file_path = frontend_out / path.lstrip("/")
            # Security: prevent path traversal
            try:
                file_path.resolve().relative_to(frontend_out.resolve())
            except ValueError:
                self._send_404()
                return
        
        if not file_path.exists() or not file_path.is_file():
            # For client-side routing, serve index.html
            if frontend_out.exists():
                file_path = frontend_out / "index.html"
            else:
                # Fallback to old dashboard HTML if Next.js build doesn't exist
                self._serve_dashboard_html_fallback()
                return
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            if file_path.suffix == ".js":
                mime_type = "application/javascript"
            elif file_path.suffix == ".css":
                mime_type = "text/css"
            elif file_path.suffix == ".json":
                mime_type = "application/json"
            elif file_path.suffix == ".html":
                mime_type = "text/html"
            else:
                mime_type = "application/octet-stream"
        
        self._send_response_headers(mime_type)
        try:
            with file_path.open("rb") as f:
                self.wfile.write(f.read())
        except Exception as e:
            logger.error(f"Error serving static file {path}: {e}")
            self._send_404()
    
    def _serve_dashboard_html_fallback(self) -> None:
        """Fallback to old dashboard HTML if Next.js build doesn't exist."""
        try:
            from .dashboard_html import get_dashboard_html
            self._send_response_headers("text/html")
            html = get_dashboard_html()
            self.wfile.write(html.encode())
        except ImportError:
            self._send_404()
    
    def _serve_history(self, query_params: dict[str, list[str]]) -> None:
        """Serve historical data endpoint."""
        try:
            metric = query_params.get("metric", ["tokens"])[0]
            window = int(query_params.get("window", ["3600"])[0])
            
            tracker = get_historical_tracker()
            data = tracker.get_metrics(metric_name=metric, window_seconds=window)
            
            self._send_response_headers("application/json")
            self.wfile.write(json.dumps(data, default=str).encode())
        except Exception as e:
            logger.error(f"Error serving history: {e}")
            self._send_response_headers("application/json", 500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _serve_export(self, query_params: dict[str, list[str]]) -> None:
        """Serve export endpoint for JSON/CSV export."""
        try:
            export_format = query_params.get("format", ["json"])[0]
            state = get_dashboard_state()
            
            if export_format == "json":
                self._send_response_headers("application/json")
                self.wfile.write(json.dumps(state, default=str, indent=2).encode())
            elif export_format == "csv":
                # Export vulnerabilities as CSV
                self._send_response_headers("text/csv")
                output = io.StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=["id", "title", "severity", "timestamp", "target"],
                )
                writer.writeheader()
                for vuln in state.get("vulnerabilities", []):
                    writer.writerow({
                        "id": vuln.get("id", ""),
                        "title": vuln.get("title", ""),
                        "severity": vuln.get("severity", ""),
                        "timestamp": vuln.get("timestamp", ""),
                        "target": vuln.get("target", ""),
                    })
                self.wfile.write(output.getvalue().encode())
            else:
                self._send_response_headers("application/json", 400)
                self.wfile.write(json.dumps({"error": "Invalid format"}).encode())
        except Exception as e:
            logger.error(f"Error serving export: {e}")
            self._send_response_headers("application/json", 500)
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _send_404(self) -> None:
        """Send a 404 response."""
        self._send_response_headers("text/plain", 404)
        self.wfile.write(b"Not Found")


class WebDashboardServer:
    """Web-based dashboard server for Strix.
    
    This server provides a real-time web interface for monitoring Strix scans.
    It runs in a background thread and exposes:
    - HTML dashboard at /
    - JSON API at /api/state
    - SSE stream at /api/stream
    - Health check at /health
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        dashboard: Dashboard | None = None,
    ):
        self.host = host
        self.port = port
        self.dashboard = dashboard
        self.server: HTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self._running = False
        self._public_url: str | None = None
    
    def start(self) -> str:
        """Start the web dashboard server.
        
        Returns:
            The URL where the dashboard is accessible.
        """
        if self._running:
            return self.get_url()
        
        self.server = HTTPServer((self.host, self.port), DashboardHTTPHandler)
        self._running = True
        
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        logger.info(f"Web dashboard started at http://{self.host}:{self.port}")
        
        return self.get_url()
    
    def _run_server(self) -> None:
        """Run the HTTP server (called in background thread)."""
        if self.server:
            try:
                self.server.serve_forever()
            except Exception as e:
                logger.error(f"Dashboard server error: {e}")
            finally:
                self._running = False
    
    def stop(self) -> None:
        """Stop the web dashboard server."""
        if self.server:
            self.server.shutdown()
            self._running = False
            logger.info("Web dashboard stopped")
    
    def get_url(self) -> str:
        """Get the dashboard URL."""
        if self._public_url:
            return self._public_url
        return f"http://{self.host}:{self.port}"
    
    def set_public_url(self, url: str) -> None:
        """Set the public URL (used when behind a proxy/tunnel)."""
        self._public_url = url
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running
    
    def update_from_tracer(self, tracer: Any) -> None:
        """Update dashboard state from a Tracer instance."""
        updates = {}
        
        # Update scan config
        if tracer.scan_config:
            updates["scan_config"] = tracer.scan_config
        
        # Update agents
        agents_data = {}
        for agent_id, agent_data in tracer.agents.items():
            agents_data[agent_id] = {
                "id": agent_id,
                "name": agent_data.get("name", "Agent"),
                "status": agent_data.get("status", "running"),
                "task": agent_data.get("task", ""),
                "parent_id": agent_data.get("parent_id"),
                "created_at": agent_data.get("created_at"),
                "updated_at": agent_data.get("updated_at"),
                "tool_executions": len(agent_data.get("tool_executions", [])),
            }
        updates["agents"] = agents_data
        
        # Update vulnerabilities
        updates["vulnerabilities"] = tracer.vulnerability_reports
        
        # Update LLM stats
        try:
            llm_stats = tracer.get_total_llm_stats()
            if llm_stats and "total" in llm_stats:
                updates["resources"] = llm_stats["total"]
        except Exception:
            pass
        
        update_dashboard_state(updates)
    
    def update_time(
        self,
        start_time: datetime | None,
        duration_minutes: float,
        warning_minutes: float,
    ) -> None:
        """Update time tracking information."""
        if start_time is None:
            return
        
        elapsed = (datetime.now(UTC) - start_time).total_seconds() / 60.0
        remaining = max(0.0, duration_minutes - elapsed)
        progress = min(100.0, (elapsed / duration_minutes) * 100) if duration_minutes > 0 else 0
        
        is_warning = remaining <= warning_minutes
        is_critical = remaining <= (warning_minutes / 2)
        
        if remaining <= 0:
            status = "⏰ TIME EXPIRED"
        elif is_critical:
            status = f"🔴 {remaining:.1f}m remaining (CRITICAL)"
        elif is_warning:
            status = f"🟡 {remaining:.1f}m remaining (Warning)"
        else:
            status = f"🟢 {remaining:.1f}m remaining ({progress:.0f}%)"
        
        update_dashboard_state({
            "time": {
                "start_time": start_time.isoformat(),
                "duration_minutes": duration_minutes,
                "warning_minutes": warning_minutes,
                "elapsed_minutes": elapsed,
                "remaining_minutes": remaining,
                "progress_percentage": progress,
                "status": status,
                "is_warning": is_warning,
                "is_critical": is_critical,
            }
        })
    
    def update_current_step(
        self,
        agent_id: str | None,
        agent_name: str | None,
        action: str | None,
        tool_name: str | None = None,
        status: str = "running",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Update the current step/action being performed."""
        update_dashboard_state({
            "current_step": {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "action": action,
                "tool_name": tool_name,
                "status": status,
                "details": details or {},
                "updated_at": datetime.now(UTC).isoformat(),
            }
        })
    
    def update_collaboration(
        self,
        claims: list[dict[str, Any]] | None = None,
        findings: list[dict[str, Any]] | None = None,
        work_queue: list[dict[str, Any]] | None = None,
        help_requests: list[dict[str, Any]] | None = None,
        messages: list[dict[str, Any]] | None = None,
        stats: dict[str, Any] | None = None,
    ) -> None:
        """Update collaboration data."""
        collab_updates: dict[str, Any] = {}
        
        if claims is not None:
            collab_updates["claims"] = claims
        if findings is not None:
            collab_updates["findings"] = findings
        if work_queue is not None:
            collab_updates["work_queue"] = work_queue
        if help_requests is not None:
            collab_updates["help_requests"] = help_requests
        if messages is not None:
            collab_updates["messages"] = messages
        if stats is not None:
            collab_updates["stats"] = stats
        
        if collab_updates:
            with _update_lock:
                _web_dashboard_state["collaboration"].update(collab_updates)
                _web_dashboard_state["last_updated"] = datetime.now(UTC).isoformat()


# Global server instance
_web_server: WebDashboardServer | None = None


def get_web_dashboard_server() -> WebDashboardServer | None:
    """Get the global web dashboard server instance."""
    return _web_server


def start_web_dashboard(
    host: str = "0.0.0.0",
    port: int = 8080,
    dashboard: Dashboard | None = None,
) -> WebDashboardServer:
    """Start the global web dashboard server.
    
    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 8080)
        dashboard: Optional Dashboard instance to sync with
    
    Returns:
        The WebDashboardServer instance
    """
    global _web_server
    
    if _web_server is None or not _web_server.is_running():
        _web_server = WebDashboardServer(host=host, port=port, dashboard=dashboard)
        _web_server.start()
    
    return _web_server


def stop_web_dashboard() -> None:
    """Stop the global web dashboard server."""
    global _web_server
    
    if _web_server:
        _web_server.stop()
        _web_server = None


def get_dashboard_html() -> str:
    """Generate the dashboard HTML.
    
    Uses the new modern React-based dashboard from dashboard_html.py
    which provides a professional CLI-like developer interface.
    """
    try:
        from .dashboard_html import get_dashboard_html as get_modern_dashboard
        return get_modern_dashboard()
    except ImportError:
        # Fallback to legacy dashboard if import fails
        pass
    
    # Legacy dashboard (kept as fallback)
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦉 Strix Security Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --strix-green: #22c55e;
            --strix-dark: #0f172a;
            --strix-darker: #0a0f1a;
        }
        
        body {
            background: linear-gradient(135deg, var(--strix-darker) 0%, var(--strix-dark) 100%);
            min-height: 100vh;
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', 'Droid Sans Mono', 'Source Code Pro', monospace;
        }
        
        .strix-border {
            border-color: var(--strix-green);
        }
        
        .strix-text {
            color: var(--strix-green);
        }
        
        .strix-bg {
            background-color: rgba(34, 197, 94, 0.1);
        }
        
        .panel {
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(34, 197, 94, 0.3);
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }
        
        .panel-header {
            background: rgba(34, 197, 94, 0.1);
            border-bottom: 1px solid rgba(34, 197, 94, 0.3);
            padding: 12px 16px;
            font-weight: 600;
            color: var(--strix-green);
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
        }
        
        .status-running { background-color: #22c55e; animation: pulse 2s infinite; }
        .status-waiting { background-color: #fbbf24; }
        .status-completed { background-color: #3b82f6; }
        .status-failed { background-color: #ef4444; }
        .status-stopped { background-color: #6b7280; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .live-feed {
            font-family: 'SF Mono', 'Monaco', monospace;
            font-size: 12px;
            line-height: 1.6;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .feed-entry {
            padding: 4px 8px;
            border-bottom: 1px solid rgba(34, 197, 94, 0.1);
        }
        
        .feed-entry:hover {
            background: rgba(34, 197, 94, 0.05);
        }
        
        .feed-timestamp {
            color: #6b7280;
            font-size: 10px;
            margin-right: 8px;
        }
        
        .feed-tool { color: #3b82f6; }
        .feed-chat { color: #a855f7; }
        .feed-agent { color: #22c55e; }
        .feed-vuln { color: #ef4444; }
        
        .progress-bar {
            height: 8px;
            border-radius: 4px;
            background: rgba(34, 197, 94, 0.2);
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--strix-green);
            transition: width 0.3s ease;
        }
        
        .progress-fill.warning {
            background: #fbbf24;
        }
        
        .progress-fill.critical {
            background: #ef4444;
        }
        
        .severity-critical { color: #ef4444; font-weight: bold; }
        .severity-high { color: #f97316; }
        .severity-medium { color: #fbbf24; }
        .severity-low { color: #22c55e; }
        .severity-info { color: #3b82f6; }
        
        .agent-tree {
            padding-left: 16px;
            border-left: 2px solid rgba(34, 197, 94, 0.3);
        }
        
        .scrollbar-thin::-webkit-scrollbar {
            width: 6px;
        }
        
        .scrollbar-thin::-webkit-scrollbar-track {
            background: rgba(34, 197, 94, 0.1);
        }
        
        .scrollbar-thin::-webkit-scrollbar-thumb {
            background: rgba(34, 197, 94, 0.3);
            border-radius: 3px;
        }
        
        .scrollbar-thin::-webkit-scrollbar-thumb:hover {
            background: rgba(34, 197, 94, 0.5);
        }
        
        .blinking {
            animation: blink 1s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        
        .tab-button {
            padding: 8px 16px;
            background: transparent;
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: #9ca3af;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .tab-button:hover {
            background: rgba(34, 197, 94, 0.1);
            color: #fff;
        }
        
        .tab-button.active {
            background: rgba(34, 197, 94, 0.2);
            border-color: var(--strix-green);
            color: var(--strix-green);
        }
        
        .connection-status {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
        }
        
        .connection-status.connected {
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border: 1px solid #22c55e;
        }
        
        .connection-status.disconnected {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid #ef4444;
        }
    </style>
</head>
<body class="text-gray-300">
    <!-- Connection Status -->
    <div id="connectionStatus" class="connection-status disconnected">
        <i class="fas fa-circle mr-1"></i>
        <span id="connectionText">Connecting...</span>
    </div>
    
    <!-- Header -->
    <header class="p-4 border-b border-gray-800">
        <div class="container mx-auto flex items-center justify-between">
            <div class="flex items-center">
                <span class="text-3xl mr-3">🦉</span>
                <div>
                    <h1 class="text-2xl font-bold strix-text">Strix Security Dashboard</h1>
                    <p class="text-sm text-gray-500">Real-time Penetration Test Monitor</p>
                </div>
            </div>
            <div class="flex items-center space-x-4">
                <div id="lastUpdate" class="text-sm text-gray-500">
                    Last update: --
                </div>
            </div>
        </div>
    </header>
    
    <!-- Main Content -->
    <main class="container mx-auto p-4">
        <!-- Top Row: Time & Target Info -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <!-- Time Remaining Panel -->
            <div class="panel">
                <div class="panel-header">
                    <i class="fas fa-clock mr-2"></i>
                    Time Remaining
                </div>
                <div class="p-4">
                    <div id="timeStatus" class="text-2xl font-bold mb-2">--</div>
                    <div class="progress-bar mb-2">
                        <div id="timeProgress" class="progress-fill" style="width: 0%"></div>
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        <div>
                            <span class="text-gray-500">Elapsed:</span>
                            <span id="timeElapsed" class="ml-1">--</span>
                        </div>
                        <div>
                            <span class="text-gray-500">Remaining:</span>
                            <span id="timeRemaining" class="ml-1">--</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Current Step Panel -->
            <div class="panel">
                <div class="panel-header">
                    <i class="fas fa-play-circle mr-2"></i>
                    Current Action
                </div>
                <div class="p-4">
                    <div id="currentAgent" class="text-lg font-semibold strix-text mb-1">--</div>
                    <div id="currentAction" class="text-gray-400 mb-2">Waiting...</div>
                    <div id="currentTool" class="text-sm">
                        <span class="text-gray-500">Tool:</span>
                        <span class="ml-1 text-blue-400">--</span>
                    </div>
                </div>
            </div>
            
            <!-- Target Info Panel -->
            <div class="panel">
                <div class="panel-header">
                    <i class="fas fa-crosshairs mr-2"></i>
                    Target Information
                </div>
                <div class="p-4">
                    <div id="targetInfo" class="space-y-1">
                        <div class="text-gray-500">No target information available</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Middle Row: Main Content Tabs -->
        <div class="panel mb-4">
            <div class="flex border-b border-gray-800">
                <button class="tab-button active" data-tab="live-feed">
                    <i class="fas fa-terminal mr-2"></i>Live Feed
                </button>
                <button class="tab-button" data-tab="agents">
                    <i class="fas fa-robot mr-2"></i>Agents
                </button>
                <button class="tab-button" data-tab="collaboration">
                    <i class="fas fa-users mr-2"></i>Collaboration
                </button>
                <button class="tab-button" data-tab="tools">
                    <i class="fas fa-wrench mr-2"></i>Tools
                </button>
            </div>
            
            <!-- Live Feed Tab -->
            <div id="tab-live-feed" class="tab-content p-4">
                <div class="live-feed scrollbar-thin" id="liveFeed">
                    <div class="text-gray-500 text-center py-8">
                        <i class="fas fa-spinner fa-spin mr-2"></i>
                        Waiting for agent activity...
                    </div>
                </div>
            </div>
            
            <!-- Agents Tab -->
            <div id="tab-agents" class="tab-content p-4 hidden">
                <div id="agentTree" class="space-y-2">
                    <div class="text-gray-500 text-center py-8">
                        No agents running yet...
                    </div>
                </div>
            </div>
            
            <!-- Collaboration Tab -->
            <div id="tab-collaboration" class="tab-content p-4 hidden">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <h3 class="text-lg font-semibold mb-2 strix-text">
                            <i class="fas fa-flag mr-2"></i>Active Claims
                        </h3>
                        <div id="collaborationClaims" class="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
                            <div class="text-gray-500">No active claims</div>
                        </div>
                    </div>
                    <div>
                        <h3 class="text-lg font-semibold mb-2 strix-text">
                            <i class="fas fa-share-alt mr-2"></i>Shared Findings
                        </h3>
                        <div id="collaborationFindings" class="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
                            <div class="text-gray-500">No shared findings</div>
                        </div>
                    </div>
                </div>
                <div class="mt-4">
                    <h3 class="text-lg font-semibold mb-2 strix-text">
                        <i class="fas fa-chart-bar mr-2"></i>Collaboration Stats
                    </h3>
                    <div id="collaborationStats" class="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div class="text-center">
                            <div class="text-2xl font-bold strix-text" id="statClaims">0</div>
                            <div class="text-sm text-gray-500">Claims</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-blue-400" id="statFindings">0</div>
                            <div class="text-sm text-gray-500">Findings</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-purple-400" id="statWorkQueue">0</div>
                            <div class="text-sm text-gray-500">Work Queue</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-yellow-400" id="statHelpRequests">0</div>
                            <div class="text-sm text-gray-500">Help Requests</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Tools Tab -->
            <div id="tab-tools" class="tab-content p-4 hidden">
                <div id="toolExecutions" class="space-y-2 max-h-96 overflow-y-auto scrollbar-thin">
                    <div class="text-gray-500 text-center py-8">
                        No tool executions yet...
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Bottom Row: Vulnerabilities & Resources -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <!-- Vulnerabilities Panel -->
            <div class="panel">
                <div class="panel-header flex justify-between items-center">
                    <span>
                        <i class="fas fa-bug mr-2"></i>
                        Vulnerabilities Found
                    </span>
                    <span id="vulnCount" class="bg-gray-700 px-2 py-1 rounded text-sm">0</span>
                </div>
                <div class="p-4">
                    <div id="vulnBreakdown" class="grid grid-cols-5 gap-2 mb-4 text-center text-sm">
                        <div>
                            <div class="text-lg font-bold severity-critical" id="vulnCritical">0</div>
                            <div class="text-gray-500">Critical</div>
                        </div>
                        <div>
                            <div class="text-lg font-bold severity-high" id="vulnHigh">0</div>
                            <div class="text-gray-500">High</div>
                        </div>
                        <div>
                            <div class="text-lg font-bold severity-medium" id="vulnMedium">0</div>
                            <div class="text-gray-500">Medium</div>
                        </div>
                        <div>
                            <div class="text-lg font-bold severity-low" id="vulnLow">0</div>
                            <div class="text-gray-500">Low</div>
                        </div>
                        <div>
                            <div class="text-lg font-bold severity-info" id="vulnInfo">0</div>
                            <div class="text-gray-500">Info</div>
                        </div>
                    </div>
                    <div id="vulnList" class="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
                        <div class="text-gray-500 text-center py-4">No vulnerabilities discovered yet</div>
                    </div>
                </div>
            </div>
            
            <!-- Resources Panel -->
            <div class="panel">
                <div class="panel-header">
                    <i class="fas fa-chart-pie mr-2"></i>
                    Resource Usage & Rate Limiter
                </div>
                <div class="p-4">
                    <!-- Rate Limiter Stats (Prominent) -->
                    <div class="mb-4 p-3 rounded" style="background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3);">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-sm font-semibold strix-text">
                                <i class="fas fa-tachometer-alt mr-2"></i>Rate Limiter (60 req/min max)
                            </span>
                            <span id="rateStatus" class="text-xs px-2 py-1 rounded bg-green-900 text-green-300">OK</span>
                        </div>
                        <div class="progress-bar mb-2">
                            <div id="rateProgress" class="progress-fill" style="width: 0%"></div>
                        </div>
                        <div class="grid grid-cols-3 gap-2 text-xs">
                            <div class="text-center">
                                <div class="text-lg font-bold strix-text" id="currentRate">0</div>
                                <div class="text-gray-500">Req/min</div>
                            </div>
                            <div class="text-center">
                                <div class="text-lg font-bold text-blue-400" id="remainingCapacity">60</div>
                                <div class="text-gray-500">Remaining</div>
                            </div>
                            <div class="text-center">
                                <div class="text-lg font-bold text-yellow-400" id="totalWaitTime">0s</div>
                                <div class="text-gray-500">Wait Time</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Token & Cost Stats -->
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <div class="text-sm text-gray-500 mb-1">Total Requests</div>
                            <div class="text-2xl font-bold strix-text" id="resApiCalls">0</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-500 mb-1">Total Cost</div>
                            <div class="text-2xl font-bold text-blue-400" id="resCost">$0.00</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-500 mb-1">Input Tokens</div>
                            <div class="text-lg" id="resInputTokens">0</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-500 mb-1">Output Tokens</div>
                            <div class="text-lg" id="resOutputTokens">0</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-500 mb-1">Cached Tokens</div>
                            <div class="text-lg text-yellow-400" id="resCachedTokens">0</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-500 mb-1">Avg Req/min</div>
                            <div class="text-lg" id="resRequests">0</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>
    
    <!-- Footer -->
    <footer class="p-4 mt-8 border-t border-gray-800 text-center text-gray-500 text-sm">
        <p>
            🦉 Strix Security Scanner | 
            <a href="https://usestrix.com" class="strix-text hover:underline">Website</a> |
            <a href="https://discord.gg/YjKFvEZSdZ" class="strix-text hover:underline">Discord</a>
        </p>
        <p class="mt-1">This dashboard is for information only - it does not control the agent.</p>
    </footer>
    
    <script>
        // Dashboard JavaScript
        let eventSource = null;
        let lastState = null;
        let feedEntries = [];
        
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
                btn.classList.add('active');
                document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
            });
        });
        
        function connectSSE() {
            eventSource = new EventSource('/api/stream');
            
            eventSource.onopen = () => {
                updateConnectionStatus(true);
            };
            
            eventSource.addEventListener('state', (e) => {
                const state = JSON.parse(e.data);
                updateDashboard(state);
            });
            
            eventSource.addEventListener('update', (e) => {
                const state = JSON.parse(e.data);
                updateDashboard(state);
            });
            
            eventSource.onerror = () => {
                updateConnectionStatus(false);
                eventSource.close();
                setTimeout(connectSSE, 3000);
            };
        }
        
        function updateConnectionStatus(connected) {
            const status = document.getElementById('connectionStatus');
            const text = document.getElementById('connectionText');
            
            if (connected) {
                status.className = 'connection-status connected';
                text.textContent = 'Connected';
            } else {
                status.className = 'connection-status disconnected';
                text.textContent = 'Reconnecting...';
            }
        }
        
        function updateDashboard(state) {
            lastState = state;
            
            // Update last update time
            if (state.last_updated) {
                const date = new Date(state.last_updated);
                document.getElementById('lastUpdate').textContent = 'Last update: ' + date.toLocaleTimeString();
            }
            
            // Update time panel
            updateTimePanel(state.time);
            
            // Update current step
            updateCurrentStep(state.current_step);
            
            // Update target info
            updateTargetInfo(state.scan_config);
            
            // Update live feed
            updateLiveFeed(state.live_feed);
            
            // Update agents
            updateAgents(state.agents);
            
            // Update collaboration
            updateCollaboration(state.collaboration);
            
            // Update tool executions
            updateTools(state.tool_executions);
            
            // Update vulnerabilities
            updateVulnerabilities(state.vulnerabilities);
            
            // Update resources
            updateResources(state.resources);
            
            // Update rate limiter
            updateRateLimiter(state.rate_limiter);
        }
        
        function updateTimePanel(time) {
            if (!time) return;
            
            document.getElementById('timeStatus').textContent = time.status || '--';
            document.getElementById('timeElapsed').textContent = (time.elapsed_minutes || 0).toFixed(1) + 'm';
            document.getElementById('timeRemaining').textContent = (time.remaining_minutes || 0).toFixed(1) + 'm';
            
            const progress = document.getElementById('timeProgress');
            progress.style.width = (time.progress_percentage || 0) + '%';
            progress.className = 'progress-fill';
            if (time.is_critical) {
                progress.classList.add('critical');
            } else if (time.is_warning) {
                progress.classList.add('warning');
            }
        }
        
        function updateCurrentStep(step) {
            if (!step) return;
            
            document.getElementById('currentAgent').textContent = step.agent_name || '--';
            document.getElementById('currentAction').textContent = step.action || 'Waiting...';
            document.getElementById('currentTool').innerHTML = 
                '<span class="text-gray-500">Tool:</span>' +
                '<span class="ml-1 text-blue-400">' + (step.tool_name || '--') + '</span>';
        }
        
        function updateTargetInfo(config) {
            const container = document.getElementById('targetInfo');
            if (!config || !config.targets || config.targets.length === 0) {
                container.innerHTML = '<div class="text-gray-500">No target information</div>';
                return;
            }
            
            let html = '';
            config.targets.forEach((target, i) => {
                const type = target.type || 'unknown';
                const details = target.details || {};
                const icon = type === 'repository' ? 'fab fa-github' : 
                            type === 'web_application' ? 'fas fa-globe' : 
                            type === 'ip_address' ? 'fas fa-server' : 'fas fa-folder';
                
                const displayTarget = details.target_url || details.target_repo || 
                                     details.target_ip || details.target_path || target.original || 'Unknown';
                
                html += '<div class="flex items-center mb-1">' +
                       '<i class="' + icon + ' mr-2 text-gray-500"></i>' +
                       '<span class="truncate">' + escapeHtml(displayTarget) + '</span>' +
                       '</div>';
            });
            
            container.innerHTML = html;
        }
        
        function updateLiveFeed(feed) {
            const container = document.getElementById('liveFeed');
            if (!feed || feed.length === 0) {
                container.innerHTML = '<div class="text-gray-500 text-center py-8">' +
                    '<i class="fas fa-spinner fa-spin mr-2"></i>Waiting for agent activity...</div>';
                return;
            }
            
            // Only update if we have new entries
            if (feed.length === feedEntries.length && feed[feed.length-1]?.timestamp === feedEntries[feedEntries.length-1]?.timestamp) {
                return;
            }
            feedEntries = feed;
            
            let html = '';
            feed.slice(-100).reverse().forEach(entry => {
                const time = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '--';
                let icon, colorClass, content;
                
                switch (entry.type) {
                    case 'tool_execution':
                        icon = 'fa-wrench';
                        colorClass = 'feed-tool';
                        content = '<span class="text-blue-400">' + (entry.tool_name || 'tool') + '</span>';
                        if (entry.status === 'completed') {
                            content += ' <span class="text-green-400">✓</span>';
                        } else if (entry.status === 'failed') {
                            content += ' <span class="text-red-400">✗</span>';
                        } else {
                            content += ' <span class="text-yellow-400 blinking">●</span>';
                        }
                        if (entry.args_summary) {
                            content += ' <span class="text-gray-500">' + escapeHtml(entry.args_summary) + '</span>';
                        }
                        break;
                    case 'chat_message':
                        icon = entry.role === 'user' ? 'fa-user' : 'fa-robot';
                        colorClass = 'feed-chat';
                        const roleLabel = entry.role === 'user' ? 'User' : 'Agent';
                        content = '<span class="text-purple-400">[' + roleLabel + ']</span> ' + 
                                 escapeHtml(entry.content_preview || '');
                        break;
                    case 'agent_created':
                        icon = 'fa-plus-circle';
                        colorClass = 'feed-agent';
                        content = '<span class="strix-text">Agent created:</span> ' + escapeHtml(entry.agent_name || '');
                        break;
                    case 'vulnerability':
                        icon = 'fa-bug';
                        colorClass = 'feed-vuln';
                        content = '<span class="text-red-400">Vulnerability:</span> ' + escapeHtml(entry.title || '');
                        break;
                    default:
                        icon = 'fa-info-circle';
                        colorClass = '';
                        content = escapeHtml(JSON.stringify(entry));
                }
                
                html += '<div class="feed-entry ' + colorClass + '">' +
                       '<span class="feed-timestamp">' + time + '</span>' +
                       '<i class="fas ' + icon + ' mr-2"></i>' +
                       content + '</div>';
            });
            
            container.innerHTML = html;
        }
        
        function updateAgents(agents) {
            const container = document.getElementById('agentTree');
            if (!agents || Object.keys(agents).length === 0) {
                container.innerHTML = '<div class="text-gray-500 text-center py-8">No agents running yet...</div>';
                return;
            }
            
            // Build tree structure
            const agentList = Object.values(agents);
            const rootAgents = agentList.filter(a => !a.parent_id);
            
            let html = '';
            rootAgents.forEach(agent => {
                html += renderAgentNode(agent, agents);
            });
            
            container.innerHTML = html;
        }
        
        function renderAgentNode(agent, allAgents) {
            const statusClass = 'status-' + (agent.status || 'running');
            const children = Object.values(allAgents).filter(a => a.parent_id === agent.id);
            
            let html = '<div class="p-2 border border-gray-700 rounded mb-2">' +
                      '<div class="flex items-center">' +
                      '<span class="status-dot ' + statusClass + '"></span>' +
                      '<span class="font-semibold">' + escapeHtml(agent.name || 'Agent') + '</span>' +
                      '<span class="ml-2 text-sm text-gray-500">(' + (agent.status || 'unknown') + ')</span>' +
                      '</div>';
            
            if (agent.task) {
                html += '<div class="text-sm text-gray-400 mt-1 truncate">' + escapeHtml(agent.task) + '</div>';
            }
            
            if (children.length > 0) {
                html += '<div class="agent-tree mt-2">';
                children.forEach(child => {
                    html += renderAgentNode(child, allAgents);
                });
                html += '</div>';
            }
            
            html += '</div>';
            return html;
        }
        
        function updateCollaboration(collab) {
            if (!collab) return;
            
            // Update claims
            const claimsContainer = document.getElementById('collaborationClaims');
            if (collab.claims && collab.claims.length > 0) {
                let html = '';
                collab.claims.slice(0, 10).forEach(claim => {
                    html += '<div class="p-2 bg-gray-800 rounded text-sm">' +
                           '<span class="strix-text">' + escapeHtml(claim.target || '') + '</span>' +
                           '<span class="text-gray-500 ml-2">[' + (claim.test_type || 'test') + ']</span>' +
                           '<span class="text-gray-500 ml-2">by ' + escapeHtml(claim.agent_name || 'agent') + '</span>' +
                           '</div>';
                });
                claimsContainer.innerHTML = html;
            } else {
                claimsContainer.innerHTML = '<div class="text-gray-500">No active claims</div>';
            }
            
            // Update findings
            const findingsContainer = document.getElementById('collaborationFindings');
            if (collab.findings && collab.findings.length > 0) {
                let html = '';
                collab.findings.slice(0, 10).forEach(finding => {
                    const sevClass = 'severity-' + (finding.severity || 'info').toLowerCase();
                    html += '<div class="p-2 bg-gray-800 rounded text-sm">' +
                           '<span class="' + sevClass + '">' + escapeHtml(finding.title || '') + '</span>' +
                           '<span class="text-gray-500 ml-2">[' + (finding.vulnerability_type || 'vuln') + ']</span>' +
                           '</div>';
                });
                findingsContainer.innerHTML = html;
            } else {
                findingsContainer.innerHTML = '<div class="text-gray-500">No shared findings</div>';
            }
            
            // Update stats
            document.getElementById('statClaims').textContent = collab.claims?.length || 0;
            document.getElementById('statFindings').textContent = collab.findings?.length || 0;
            document.getElementById('statWorkQueue').textContent = collab.work_queue?.length || 0;
            document.getElementById('statHelpRequests').textContent = collab.help_requests?.length || 0;
        }
        
        function updateTools(tools) {
            const container = document.getElementById('toolExecutions');
            if (!tools || tools.length === 0) {
                container.innerHTML = '<div class="text-gray-500 text-center py-8">No tool executions yet...</div>';
                return;
            }
            
            let html = '';
            tools.slice(-50).reverse().forEach(tool => {
                const statusIcon = tool.status === 'completed' ? '✓' : 
                                  tool.status === 'failed' ? '✗' : '●';
                const statusColor = tool.status === 'completed' ? 'text-green-400' : 
                                   tool.status === 'failed' ? 'text-red-400' : 'text-yellow-400';
                
                html += '<div class="p-2 bg-gray-800 rounded flex items-center justify-between">' +
                       '<div>' +
                       '<span class="text-blue-400 font-semibold">' + escapeHtml(tool.tool_name || 'tool') + '</span>' +
                       '</div>' +
                       '<span class="' + statusColor + '">' + statusIcon + '</span>' +
                       '</div>';
            });
            
            container.innerHTML = html;
        }
        
        function updateVulnerabilities(vulns) {
            const countEl = document.getElementById('vulnCount');
            const listEl = document.getElementById('vulnList');
            
            if (!vulns || vulns.length === 0) {
                countEl.textContent = '0';
                listEl.innerHTML = '<div class="text-gray-500 text-center py-4">No vulnerabilities discovered yet</div>';
                document.getElementById('vulnCritical').textContent = '0';
                document.getElementById('vulnHigh').textContent = '0';
                document.getElementById('vulnMedium').textContent = '0';
                document.getElementById('vulnLow').textContent = '0';
                document.getElementById('vulnInfo').textContent = '0';
                return;
            }
            
            countEl.textContent = vulns.length;
            
            // Count by severity
            const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
            vulns.forEach(v => {
                const sev = (v.severity || 'info').toLowerCase();
                if (counts[sev] !== undefined) counts[sev]++;
            });
            
            document.getElementById('vulnCritical').textContent = counts.critical;
            document.getElementById('vulnHigh').textContent = counts.high;
            document.getElementById('vulnMedium').textContent = counts.medium;
            document.getElementById('vulnLow').textContent = counts.low;
            document.getElementById('vulnInfo').textContent = counts.info;
            
            // Render list
            let html = '';
            vulns.slice(0, 20).forEach(vuln => {
                const sevClass = 'severity-' + (vuln.severity || 'info').toLowerCase();
                html += '<div class="p-2 bg-gray-800 rounded">' +
                       '<div class="flex items-center justify-between">' +
                       '<span class="' + sevClass + ' font-semibold">' + escapeHtml(vuln.title || 'Vulnerability') + '</span>' +
                       '<span class="text-xs text-gray-500">' + escapeHtml(vuln.id || '') + '</span>' +
                       '</div>' +
                       '</div>';
            });
            
            listEl.innerHTML = html;
        }
        
        function updateResources(res) {
            if (!res) return;
            
            document.getElementById('resApiCalls').textContent = formatNumber(res.api_calls || res.requests || 0);
            document.getElementById('resCost').textContent = '$' + (res.total_cost || res.cost || 0).toFixed(4);
            document.getElementById('resInputTokens').textContent = formatNumber(res.input_tokens || 0);
            document.getElementById('resOutputTokens').textContent = formatNumber(res.output_tokens || 0);
            document.getElementById('resCachedTokens').textContent = formatNumber(res.cached_tokens || 0);
            document.getElementById('resRequests').textContent = formatNumber(res.request_count || res.requests || 0);
        }
        
        function updateRateLimiter(rate) {
            if (!rate) return;
            
            const currentRate = rate.current_rate || 0;
            const maxRate = rate.max_rate || 60;
            const remaining = rate.remaining_capacity || maxRate;
            const waitTime = rate.total_wait_time || 0;
            
            // Update values
            document.getElementById('currentRate').textContent = currentRate;
            document.getElementById('remainingCapacity').textContent = remaining;
            document.getElementById('totalWaitTime').textContent = waitTime.toFixed(1) + 's';
            
            // Update progress bar
            const progress = document.getElementById('rateProgress');
            const percentage = (currentRate / maxRate) * 100;
            progress.style.width = percentage + '%';
            
            // Update status and colors
            const status = document.getElementById('rateStatus');
            progress.className = 'progress-fill';
            
            if (currentRate >= maxRate * 0.9) {
                status.textContent = 'THROTTLED';
                status.className = 'text-xs px-2 py-1 rounded bg-red-900 text-red-300';
                progress.classList.add('critical');
            } else if (currentRate >= maxRate * 0.7) {
                status.textContent = 'HIGH';
                status.className = 'text-xs px-2 py-1 rounded bg-yellow-900 text-yellow-300';
                progress.classList.add('warning');
            } else {
                status.textContent = 'OK';
                status.className = 'text-xs px-2 py-1 rounded bg-green-900 text-green-300';
            }
        }
        
        function formatNumber(num) {
            return num.toLocaleString();
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Initialize
        connectSSE();
        
        // Fetch initial state via REST as backup
        fetch('/api/state')
            .then(r => r.json())
            .then(state => updateDashboard(state))
            .catch(e => console.error('Initial fetch failed:', e));
    </script>
</body>
</html>'''


def get_dashboard_css() -> str:
    """Return the dashboard CSS (included inline in HTML)."""
    return ""


def get_dashboard_js() -> str:
    """Return the dashboard JavaScript (included inline in HTML)."""
    return ""
