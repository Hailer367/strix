"""Opik Integration for Strix.

This module provides integration with Opik for real-time AI observability,
replacing the custom web-based dashboard with Opik's comprehensive tracing
and monitoring capabilities.

Features:
- Real-time trace logging of agent activities
- Tool execution tracking with timing
- Vulnerability discovery logging
- Agent hierarchy visualization
- LLM request/response tracking
- Token usage and cost tracking

The integration mirrors the CLI-like dashboard view shown in screenshot.png:
- Tool executions (clicking, typing, press_key, etc.)
- Thinking sections (AI reasoning)
- Vulnerability reports with severity levels
- Agent tree visualization

Usage:
    from strix.telemetry.opik_integration import (
        setup_opik,
        get_opik_tracer,
        OpikStrixTracer,
    )
    
    # Setup opik at scan start
    setup_opik(project_name="strix-security-scan")
    
    # Get the global opik tracer
    tracer = get_opik_tracer()
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Global opik tracer instance
_opik_tracer: Optional["OpikStrixTracer"] = None

# Track if opik is available
_opik_available = False

try:
    import opik
    from opik import Opik, track, flush_tracker
    from opik.api_objects.trace import Trace
    from opik.api_objects.span import Span
    _opik_available = True
    logger.info("Opik SDK available - real-time tracing enabled")
except ImportError:
    logger.info("Opik SDK not installed - using fallback logging")
    Opik = None
    track = None
    flush_tracker = None
    Trace = None
    Span = None


def is_opik_available() -> bool:
    """Check if Opik SDK is available."""
    return _opik_available


def get_opik_tracer() -> Optional["OpikStrixTracer"]:
    """Get the global Opik tracer instance."""
    return _opik_tracer


def setup_opik(
    project_name: str = "strix-security-scan",
    workspace: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Optional["OpikStrixTracer"]:
    """Setup Opik integration for Strix.
    
    Args:
        project_name: Name of the Opik project (default: strix-security-scan)
        workspace: Opik workspace name (optional)
        api_key: Opik API key (optional, uses env var if not provided)
    
    Returns:
        OpikStrixTracer instance if Opik is available, None otherwise
    """
    global _opik_tracer
    
    if not _opik_available:
        logger.warning("Opik SDK not available. Install with: pip install opik")
        return None
    
    try:
        # Configure opik (uses environment variables if not provided)
        if api_key:
            os.environ["OPIK_API_KEY"] = api_key
        if workspace:
            os.environ["OPIK_WORKSPACE"] = workspace
        
        # Initialize the Opik client
        client = Opik(project_name=project_name)
        
        # Create our custom tracer wrapper
        _opik_tracer = OpikStrixTracer(
            client=client,
            project_name=project_name,
        )
        
        logger.info(f"Opik integration initialized - project: {project_name}")
        return _opik_tracer
        
    except Exception as e:
        logger.warning(f"Failed to initialize Opik: {e}")
        return None


def teardown_opik() -> None:
    """Cleanup Opik integration."""
    global _opik_tracer
    
    if _opik_tracer:
        _opik_tracer.flush()
        _opik_tracer = None
        logger.info("Opik integration shutdown complete")


class OpikStrixTracer:
    """Opik-based tracer for Strix that mirrors the CLI dashboard view.
    
    This tracer provides:
    - Real-time logging of tool executions (like the CLI feed)
    - AI thinking/reasoning sections
    - Vulnerability reports
    - Agent hierarchy tracking
    - LLM metrics and token usage
    """
    
    def __init__(
        self,
        client: Optional["Opik"] = None,
        project_name: str = "strix-security-scan",
    ):
        self.client = client
        self.project_name = project_name
        self.run_id = f"strix-{uuid4().hex[:8]}"
        self.start_time = datetime.now(UTC)
        
        # Active traces and spans
        self._active_traces: Dict[str, Any] = {}  # agent_id -> Trace
        self._active_spans: Dict[str, Any] = {}   # execution_id -> Span
        self._root_trace: Optional[Any] = None
        
        # Statistics tracking
        self._tool_count = 0
        self._vulnerability_count = 0
        self._agent_count = 0
        
        # Store metadata for the dashboard view
        self._live_feed: List[Dict[str, Any]] = []
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._vulnerabilities: List[Dict[str, Any]] = []
        
    def start_scan_trace(
        self,
        scan_config: Dict[str, Any],
        targets: List[str],
    ) -> Optional[str]:
        """Start the root trace for a security scan.
        
        This creates the top-level trace that all agent activities will be nested under.
        """
        if not self.client:
            return None
            
        try:
            trace_id = f"scan-{self.run_id}"
            
            # Create root trace with scan metadata
            self._root_trace = self.client.trace(
                name="Strix Security Scan",
                input={
                    "targets": targets,
                    "scan_config": scan_config,
                    "start_time": self.start_time.isoformat(),
                },
                metadata={
                    "run_id": self.run_id,
                    "project": self.project_name,
                    "scan_type": "security_penetration_test",
                },
            )
            
            self._add_to_feed({
                "type": "scan_start",
                "message": f"🦉 Strix Security Scan Started",
                "targets": targets,
            })
            
            logger.info(f"Started Opik scan trace: {trace_id}")
            return trace_id
            
        except Exception as e:
            logger.error(f"Failed to start scan trace: {e}")
            return None
    
    def log_agent_created(
        self,
        agent_id: str,
        agent_name: str,
        task: str,
        parent_id: Optional[str] = None,
    ) -> Optional[str]:
        """Log the creation of a new agent.
        
        Creates a nested span under the root trace (or parent agent's span).
        """
        if not self.client or not self._root_trace:
            return None
            
        try:
            self._agent_count += 1
            
            # Store agent metadata
            self._agents[agent_id] = {
                "id": agent_id,
                "name": agent_name,
                "task": task,
                "parent_id": parent_id,
                "status": "running",
                "created_at": datetime.now(UTC).isoformat(),
            }
            
            # Create span for this agent
            parent_trace = self._active_traces.get(parent_id, self._root_trace)
            
            agent_span = self._root_trace.span(
                name=f"Agent: {agent_name}",
                input={
                    "agent_id": agent_id,
                    "task": task,
                    "parent_id": parent_id,
                },
                metadata={
                    "agent_type": agent_name,
                    "is_sub_agent": parent_id is not None,
                },
            )
            
            self._active_traces[agent_id] = agent_span
            
            self._add_to_feed({
                "type": "agent_created",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task": task[:100] if task else "",
                "parent_id": parent_id,
            })
            
            return agent_id
            
        except Exception as e:
            logger.error(f"Failed to log agent creation: {e}")
            return None
    
    def log_tool_start(
        self,
        agent_id: str,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Optional[str]:
        """Log the start of a tool execution.
        
        Creates a span under the agent's trace for this tool execution.
        Mirrors the CLI feed entries like: clicking, typing, press_key, etc.
        """
        if not self.client:
            return None
            
        try:
            execution_id = f"tool-{self._tool_count + 1:04d}"
            self._tool_count += 1
            
            # Get the agent's span
            agent_span = self._active_traces.get(agent_id)
            parent = agent_span if agent_span else self._root_trace
            
            if not parent:
                return execution_id
            
            # Create tool execution span
            tool_span = parent.span(
                name=f"Tool: {tool_name}",
                input=self._sanitize_args(args),
                metadata={
                    "tool_name": tool_name,
                    "agent_id": agent_id,
                    "execution_id": execution_id,
                },
            )
            
            self._active_spans[execution_id] = tool_span
            
            # Add CLI-like feed entry
            self._add_to_feed({
                "type": "tool_start",
                "tool_name": tool_name,
                "agent_id": agent_id,
                "args_summary": self._summarize_args(args),
                "execution_id": execution_id,
            })
            
            return execution_id
            
        except Exception as e:
            logger.error(f"Failed to log tool start: {e}")
            return None
    
    def log_tool_end(
        self,
        execution_id: str,
        status: str,
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """Log the completion of a tool execution."""
        if not self.client or execution_id not in self._active_spans:
            return
            
        try:
            tool_span = self._active_spans.pop(execution_id)
            
            output = {"status": status}
            if result is not None:
                output["result"] = self._truncate_result(result)
            if error:
                output["error"] = error
            
            tool_span.end(output=output)
            
            # Update feed with completion status
            self._add_to_feed({
                "type": "tool_end",
                "execution_id": execution_id,
                "status": status,
                "has_error": error is not None,
            })
            
        except Exception as e:
            logger.error(f"Failed to log tool end: {e}")
    
    def log_thinking(
        self,
        agent_id: str,
        agent_name: str,
        content: str,
    ) -> None:
        """Log AI thinking/reasoning (like Claude Code's thinking display).
        
        This creates entries that mirror the "Thinking" sections in the CLI dashboard.
        """
        if not self.client or not self._root_trace:
            return
            
        try:
            # Truncate long thinking content
            max_length = 1000
            truncated_content = content[:max_length] + "..." if len(content) > max_length else content
            
            # Add as a span annotation
            agent_span = self._active_traces.get(agent_id)
            if agent_span:
                # Log as a child span for the thinking
                thinking_span = agent_span.span(
                    name="Thinking",
                    input={"content_preview": truncated_content[:200]},
                    metadata={
                        "type": "reasoning",
                        "agent_id": agent_id,
                        "full_length": len(content),
                    },
                )
                thinking_span.end(output={"content": truncated_content})
            
            # Add to CLI-like feed
            self._add_to_feed({
                "type": "thinking",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "content": truncated_content[:500],  # Keep feed entries shorter
            })
            
        except Exception as e:
            logger.error(f"Failed to log thinking: {e}")
    
    def log_vulnerability(
        self,
        title: str,
        severity: str,
        description: str,
        agent_id: Optional[str] = None,
    ) -> Optional[str]:
        """Log a discovered vulnerability.
        
        Creates a prominently marked span for vulnerabilities and adds to the feed
        similar to the "Vulnerability Report" entries in the CLI dashboard.
        """
        if not self.client or not self._root_trace:
            return None
            
        try:
            self._vulnerability_count += 1
            vuln_id = f"vuln-{self._vulnerability_count:04d}"
            
            # Store vulnerability
            vuln_data = {
                "id": vuln_id,
                "title": title,
                "severity": severity.lower(),
                "description": description,
                "agent_id": agent_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self._vulnerabilities.append(vuln_data)
            
            # Create a span for the vulnerability
            parent = self._active_traces.get(agent_id, self._root_trace)
            vuln_span = parent.span(
                name=f"🚨 Vulnerability: {title}",
                input={
                    "title": title,
                    "severity": severity,
                },
                metadata={
                    "type": "vulnerability_report",
                    "severity": severity.lower(),
                    "vuln_id": vuln_id,
                },
            )
            vuln_span.end(output={
                "description": description[:2000],
                "severity": severity,
            })
            
            # Add to feed (prominent vulnerability entry)
            self._add_to_feed({
                "type": "vulnerability",
                "vuln_id": vuln_id,
                "title": title,
                "severity": severity.lower(),
                "description": description[:500],
            })
            
            logger.info(f"Logged vulnerability to Opik: {vuln_id} - {title} ({severity})")
            return vuln_id
            
        except Exception as e:
            logger.error(f"Failed to log vulnerability: {e}")
            return None
    
    def log_llm_request(
        self,
        agent_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float = 0.0,
    ) -> None:
        """Log LLM request metrics."""
        if not self.client:
            return
            
        try:
            agent_span = self._active_traces.get(agent_id)
            if agent_span:
                # Update span with LLM usage
                agent_span.update(
                    metadata={
                        "llm_model": model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost,
                    }
                )
        except Exception as e:
            logger.debug(f"Failed to log LLM request: {e}")
    
    def update_agent_status(
        self,
        agent_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Update agent status."""
        if agent_id in self._agents:
            self._agents[agent_id]["status"] = status
            self._agents[agent_id]["updated_at"] = datetime.now(UTC).isoformat()
            if error_message:
                self._agents[agent_id]["error"] = error_message
        
        # Close agent span if completed/failed
        if status in ("completed", "failed", "error") and agent_id in self._active_traces:
            try:
                agent_span = self._active_traces.pop(agent_id)
                agent_span.end(output={
                    "status": status,
                    "error": error_message,
                })
            except Exception as e:
                logger.debug(f"Failed to close agent span: {e}")
    
    def end_scan(
        self,
        success: bool = True,
        final_report: Optional[str] = None,
    ) -> None:
        """End the scan trace."""
        if not self._root_trace:
            return
            
        try:
            duration = (datetime.now(UTC) - self.start_time).total_seconds()
            
            self._root_trace.end(output={
                "success": success,
                "duration_seconds": duration,
                "tool_executions": self._tool_count,
                "vulnerabilities_found": self._vulnerability_count,
                "agents_spawned": self._agent_count,
                "final_report_preview": final_report[:2000] if final_report else None,
            })
            
            self._add_to_feed({
                "type": "scan_end",
                "success": success,
                "duration_seconds": duration,
                "tool_count": self._tool_count,
                "vuln_count": self._vulnerability_count,
            })
            
            logger.info(f"Scan trace ended - tools: {self._tool_count}, vulns: {self._vulnerability_count}")
            
        except Exception as e:
            logger.error(f"Failed to end scan trace: {e}")
    
    def flush(self) -> None:
        """Flush all pending data to Opik."""
        if _opik_available:
            try:
                flush_tracker()
            except Exception as e:
                logger.debug(f"Failed to flush Opik tracker: {e}")
    
    def get_dashboard_state(self) -> Dict[str, Any]:
        """Get current state for dashboard display.
        
        Returns data structured like the original web dashboard for compatibility.
        """
        return {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "tool_count": self._tool_count,
            "vulnerability_count": self._vulnerability_count,
            "agent_count": self._agent_count,
            "agents": self._agents,
            "vulnerabilities": self._vulnerabilities,
            "live_feed": self._live_feed[-100:],  # Last 100 entries
        }
    
    def get_opik_dashboard_url(self) -> Optional[str]:
        """Get URL to the Opik dashboard for this trace.
        
        Returns the URL where users can view the real-time trace in Opik's UI.
        """
        # For Opik Cloud, the URL would be something like:
        # https://app.opik.com/workspace/{workspace}/traces/{trace_id}
        # This depends on how opik is configured (cloud vs self-hosted)
        
        try:
            opik_base_url = os.getenv("OPIK_BASE_URL", "https://app.opik.com")
            workspace = os.getenv("OPIK_WORKSPACE", "default")
            
            if self._root_trace and hasattr(self._root_trace, "id"):
                return f"{opik_base_url}/{workspace}/traces/{self._root_trace.id}"
            return f"{opik_base_url}/{workspace}/projects/{self.project_name}"
        except Exception:
            return None
    
    # Private helper methods
    
    def _add_to_feed(self, entry: Dict[str, Any]) -> None:
        """Add entry to the CLI-like live feed."""
        entry["timestamp"] = datetime.now(UTC).isoformat()
        self._live_feed.append(entry)
        
        # Keep feed manageable
        if len(self._live_feed) > 500:
            self._live_feed = self._live_feed[-500:]
    
    def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize arguments for logging (remove sensitive data)."""
        sanitized = {}
        sensitive_keys = {"password", "token", "api_key", "secret", "credential"}
        
        for key, value in args.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + "..."
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _summarize_args(self, args: Dict[str, Any]) -> str:
        """Create a brief summary of arguments for feed display."""
        if not args:
            return ""
        
        # Get first key-value pair
        for key, value in list(args.items())[:1]:
            str_val = str(value)
            if len(str_val) > 50:
                str_val = str_val[:47] + "..."
            return f"{key}={str_val}"
        
        return ""
    
    def _truncate_result(self, result: Any) -> Any:
        """Truncate result for logging."""
        if isinstance(result, str):
            if len(result) > 2000:
                return result[:2000] + "... [truncated]"
        elif isinstance(result, dict):
            return {k: self._truncate_result(v) for k, v in list(result.items())[:20]}
        return result


# Decorator for tracking Strix functions with Opik
def track_strix(
    name: Optional[str] = None,
    capture_input: bool = True,
    capture_output: bool = True,
):
    """Decorator to track Strix functions with Opik.
    
    Usage:
        @track_strix(name="scan_target")
        async def scan_target(url: str) -> dict:
            ...
    """
    if not _opik_available:
        # Return a no-op decorator if Opik is not available
        def noop_decorator(func):
            return func
        return noop_decorator
    
    return track(
        name=name,
        capture_input=capture_input,
        capture_output=capture_output,
    )
