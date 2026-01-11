"""Web Dashboard Integration Module.

This module integrates the web dashboard with the Strix tracer and agent systems
to automatically stream updates to the web dashboard in real-time.
"""

import logging
import os
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .history import get_historical_tracker
from .web_server import (
    WebDashboardServer,
    add_chat_message,
    add_live_feed_entry,
    add_tool_execution,
    get_dashboard_state,
    get_web_dashboard_server,
    start_web_dashboard,
    stop_web_dashboard,
    update_dashboard_state,
)


if TYPE_CHECKING:
    from strix.telemetry.tracer import Tracer


logger = logging.getLogger(__name__)


class WebDashboardIntegration:
    """Integrates the web dashboard with Strix components.
    
    This class:
    - Starts/stops the web dashboard server
    - Hooks into the tracer to stream updates
    - Updates time tracking from config
    - Syncs collaboration data
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        tracer: "Tracer | None" = None,
    ):
        self.host = host
        self.port = port
        self.tracer = tracer
        self.server: WebDashboardServer | None = None
        self._sync_thread: threading.Thread | None = None
        self._running = False
        self._last_tool_count = 0
        self._last_message_count = 0
        self._last_vuln_count = 0
        self._session_start: datetime | None = None
        self._duration_minutes: float = 60.0
        self._warning_minutes: float = 5.0
    
    def start(self) -> str:
        """Start the web dashboard integration.
        
        Returns:
            The URL where the dashboard is accessible.
        """
        if self._running:
            return self.get_url()
        
        # Start the web server
        self.server = start_web_dashboard(
            host=self.host,
            port=self.port,
        )
        
        self._running = True
        self._session_start = datetime.now(UTC)
        
        # Initialize state from tracer if available
        if self.tracer:
            self._sync_from_tracer()
        
        # Start background sync thread
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        
        url = self.get_url()
        logger.info(f"Web dashboard integration started at {url}")
        
        # Add startup event to live feed
        add_live_feed_entry({
            "type": "system",
            "message": "Dashboard started",
            "url": url,
        })
        
        return url
    
    def stop(self) -> None:
        """Stop the web dashboard integration."""
        self._running = False
        
        if self._sync_thread:
            self._sync_thread.join(timeout=2.0)
        
        stop_web_dashboard()
        logger.info("Web dashboard integration stopped")
    
    def get_url(self) -> str:
        """Get the dashboard URL."""
        if self.server:
            return self.server.get_url()
        return f"http://{self.host}:{self.port}"
    
    def set_public_url(self, url: str) -> None:
        """Set the public URL (for tunnels/proxies)."""
        if self.server:
            self.server.set_public_url(url)
    
    def set_tracer(self, tracer: "Tracer") -> None:
        """Set the tracer instance."""
        self.tracer = tracer
        
        # Register callback for vulnerability findings
        tracer.vulnerability_found_callback = self._on_vulnerability_found
        
        # Initial sync
        self._sync_from_tracer()
    
    def set_time_config(
        self,
        duration_minutes: float,
        warning_minutes: float,
    ) -> None:
        """Set time configuration."""
        self._duration_minutes = duration_minutes
        self._warning_minutes = warning_minutes
    
    def _sync_loop(self) -> None:
        """Background loop to sync state periodically."""
        while self._running:
            try:
                self._sync_from_tracer()
                self._sync_time()
                self._sync_collaboration()
            except Exception as e:
                logger.debug(f"Sync error: {e}")
            
            time.sleep(1.0)
    
    def _sync_from_tracer(self) -> None:
        """Sync state from the tracer and update history."""
        if not self.tracer:
            return
        
        updates: dict[str, Any] = {}
        tracker = get_historical_tracker()
        
        # Sync scan config
        if self.tracer.scan_config:
            updates["scan_config"] = self.tracer.scan_config
        
        # Sync agents
        agents_data = {}
        for agent_id, agent_data in self.tracer.agents.items():
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
            
            # Update current step if agent is running
            if agent_data.get("status") == "running":
                # Get last tool execution for this agent
                agent_tools = self.tracer.get_agent_tools(agent_id)
                if agent_tools:
                    last_tool = agent_tools[-1]
                    updates["current_step"] = {
                        "agent_id": agent_id,
                        "agent_name": agent_data.get("name", "Agent"),
                        "action": f"Executing {last_tool.get('tool_name', 'tool')}",
                        "tool_name": last_tool.get("tool_name"),
                        "status": last_tool.get("status", "running"),
                        "details": {},
                    }
        
        if agents_data:
            updates["agents"] = agents_data
        
        # Sync new tool executions to live feed
        current_tool_count = len(self.tracer.tool_executions)
        if current_tool_count > self._last_tool_count:
            new_tools = list(self.tracer.tool_executions.values())[self._last_tool_count:]
            for tool_data in new_tools:
                add_tool_execution(tool_data)
                # Track tool execution events in history
                tracker.add_event("tool_execution", {
                    "tool_name": tool_data.get("tool_name"),
                    "agent_id": tool_data.get("agent_id"),
                    "status": tool_data.get("status"),
                    "execution_id": tool_data.get("execution_id"),
                })
            self._last_tool_count = current_tool_count
        
        # Sync new chat messages to live feed  
        current_message_count = len(self.tracer.chat_messages)
        if current_message_count > self._last_message_count:
            new_messages = self.tracer.chat_messages[self._last_message_count:]
            for msg in new_messages:
                add_chat_message(msg)
            self._last_message_count = current_message_count
        
        # Sync vulnerabilities
        current_vuln_count = len(self.tracer.vulnerability_reports)
        if current_vuln_count > self._last_vuln_count:
            updates["vulnerabilities"] = self.tracer.vulnerability_reports
            self._last_vuln_count = current_vuln_count
        
        # Sync LLM stats
        try:
            llm_stats = self.tracer.get_total_llm_stats()
            if llm_stats and "total" in llm_stats:
                resources = llm_stats["total"]
                updates["resources"] = resources
                
                # Track metrics in history
                tracker.add_data_point({
                    "tokens": {
                        "input": resources.get("input_tokens", 0),
                        "output": resources.get("output_tokens", 0),
                        "cached": resources.get("cached_tokens", 0),
                    },
                    "cost": resources.get("cost", 0.0),
                    "requests": resources.get("requests", 0),
                    "rate": len(self.tracer.tool_executions),
                })
                
                # Track agent count
                tracker.add_event("agent_count", {
                    "count": len(self.tracer.agents),
                })
        except Exception:
            pass
        
        if updates:
            update_dashboard_state(updates)
    
    def _sync_time(self) -> None:
        """Sync time tracking."""
        if not self._session_start:
            return
        
        if self.server:
            self.server.update_time(
                start_time=self._session_start,
                duration_minutes=self._duration_minutes,
                warning_minutes=self._warning_minutes,
            )
    
    def _sync_collaboration(self) -> None:
        """Sync collaboration data."""
        try:
            from strix.tools.collaboration.collaboration_actions import (
                _claims,
                _findings,
                _work_queue,
                _help_requests,
                _messages,
                _collaboration_stats,
            )
            
            # Flatten claims
            all_claims = []
            for agent_id, claims in _claims.items():
                for claim in claims:
                    if claim.get("status") == "active":
                        all_claims.append({
                            "agent_id": agent_id,
                            "agent_name": claim.get("agent_name"),
                            "target": claim.get("target"),
                            "test_type": claim.get("test_type"),
                            "priority": claim.get("priority"),
                            "claimed_at": claim.get("claimed_at"),
                        })
            
            # Format findings
            findings_list = [
                {
                    "finding_id": f_id,
                    "title": f.get("title"),
                    "vulnerability_type": f.get("vulnerability_type"),
                    "severity": f.get("severity"),
                    "target": f.get("target"),
                    "found_by": f.get("found_by", {}).get("agent_name"),
                    "chainable": f.get("chainable"),
                }
                for f_id, f in _findings.items()
            ]
            
            if self.server:
                self.server.update_collaboration(
                    claims=all_claims,
                    findings=findings_list,
                    work_queue=_work_queue,
                    help_requests=_help_requests,
                    messages=_messages[-50:],  # Last 50 messages
                    stats=_collaboration_stats,
                )
        
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Collaboration sync error: {e}")
    
    def _on_vulnerability_found(
        self,
        vuln_id: str,
        title: str,
        content: str,
        severity: str,
    ) -> None:
        """Callback when a vulnerability is found."""
        add_live_feed_entry({
            "type": "vulnerability",
            "vuln_id": vuln_id,
            "title": title,
            "severity": severity,
        })


# Global integration instance
_integration: WebDashboardIntegration | None = None


def get_integration() -> WebDashboardIntegration | None:
    """Get the global integration instance."""
    return _integration


def setup_web_dashboard(
    tracer: "Tracer | None" = None,
    host: str = "0.0.0.0",
    port: int = 8080,
    duration_minutes: float = 60.0,
    warning_minutes: float = 5.0,
) -> WebDashboardIntegration:
    """Set up and start the web dashboard integration.
    
    Args:
        tracer: The tracer instance to sync with
        host: Host to bind to
        port: Port to listen on
        duration_minutes: Total scan duration in minutes
        warning_minutes: Minutes before end to show warning
    
    Returns:
        The WebDashboardIntegration instance
    """
    global _integration
    
    _integration = WebDashboardIntegration(
        host=host,
        port=port,
        tracer=tracer,
    )
    _integration.set_time_config(duration_minutes, warning_minutes)
    _integration.start()
    
    return _integration


def teardown_web_dashboard() -> None:
    """Stop and clean up the web dashboard integration."""
    global _integration
    
    if _integration:
        _integration.stop()
        _integration = None
