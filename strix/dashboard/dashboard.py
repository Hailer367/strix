"""Real-Time Dashboard for Strix.

Provides a real-time monitoring dashboard for Strix agent activity.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from .time_tracker import TimeTracker


if TYPE_CHECKING:
    from strix.config import StrixConfig
    from strix.telemetry.tracer import Tracer


logger = logging.getLogger(__name__)


@dataclass
class AgentStatus:
    """Represents the status of an agent."""
    
    agent_id: str
    name: str
    status: str  # "running", "waiting", "completed", "failed", "stopped"
    task: str = ""
    iteration: int = 0
    max_iterations: int = 300
    start_time: datetime | None = None
    tool_count: int = 0
    last_tool: str = ""
    
    def get_status_icon(self) -> str:
        """Get status icon."""
        icons = {
            "running": "🟢",
            "waiting": "🟡",
            "completed": "✅",
            "failed": "❌",
            "stopped": "⏹️",
            "stopping": "⏸️",
            "llm_failed": "🔴",
        }
        return icons.get(self.status, "🔵")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status,
            "task": self.task,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "tool_count": self.tool_count,
            "last_tool": self.last_tool,
        }


@dataclass  
class ResourceUsage:
    """Tracks resource usage."""
    
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "total_cost": round(self.total_cost, 4),
            "request_count": self.request_count,
        }


@dataclass
class DashboardWidget:
    """Represents a dashboard widget/section."""
    
    title: str
    content: Any
    style: str = "green"
    
    def render(self) -> Panel:
        """Render the widget as a Rich Panel."""
        return Panel(
            self.content,
            title=f"[bold]{self.title}[/bold]",
            border_style=self.style,
            padding=(0, 1),
        )


@dataclass
class Dashboard:
    """Real-time dashboard for monitoring Strix activity.
    
    Usage:
        dashboard = Dashboard.from_config(config)
        dashboard.start()
        
        # Update during scan
        dashboard.update_agent(agent_status)
        dashboard.update_resources(usage)
        
        # Display
        dashboard.render()
        
        dashboard.stop()
    """
    
    # Time tracking
    time_tracker: TimeTracker = field(default_factory=TimeTracker)
    
    # Configuration
    enabled: bool = True
    refresh_interval: float = 1.0
    show_agent_details: bool = True
    show_tool_logs: bool = True
    show_time_remaining: bool = True
    show_resource_usage: bool = True
    
    # State
    agents: dict[str, AgentStatus] = field(default_factory=dict)
    resources: ResourceUsage = field(default_factory=ResourceUsage)
    vulnerabilities_found: int = 0
    tool_log: list[dict[str, Any]] = field(default_factory=list)
    max_tool_log_size: int = 10
    
    # Console
    console: Console = field(default_factory=Console)
    live: Live | None = None
    
    def start(self) -> None:
        """Start the dashboard."""
        if not self.enabled:
            return
        
        self.time_tracker.start()
        logger.info("Dashboard started")
    
    def stop(self) -> None:
        """Stop the dashboard."""
        self.time_tracker.stop()
        if self.live:
            self.live.stop()
        logger.info("Dashboard stopped")
    
    def update_agent(self, agent_status: AgentStatus) -> None:
        """Update agent status."""
        self.agents[agent_status.agent_id] = agent_status
    
    def update_from_tracer(self, tracer: "Tracer") -> None:
        """Update dashboard from tracer data."""
        # Update agents
        for agent_id, agent_data in tracer.agents.items():
            self.agents[agent_id] = AgentStatus(
                agent_id=agent_id,
                name=agent_data.get("name", "Agent"),
                status=agent_data.get("status", "running"),
                task=agent_data.get("task", ""),
                start_time=agent_data.get("created_at"),
            )
        
        # Update resources from usage stats if available
        if hasattr(tracer, "total_usage"):
            usage = tracer.total_usage
            self.resources = ResourceUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                total_cost=usage.get("cost", 0.0),
                request_count=usage.get("requests", 0),
            )
        
        # Update vulnerabilities count
        self.vulnerabilities_found = len(tracer.vulnerability_reports)
        
        # Update tool log (recent tools)
        recent_tools = list(tracer.tool_executions.values())[-self.max_tool_log_size:]
        self.tool_log = recent_tools
    
    def update_resources(self, usage: ResourceUsage) -> None:
        """Update resource usage."""
        self.resources = usage
    
    def add_tool_execution(self, tool_data: dict[str, Any]) -> None:
        """Add a tool execution to the log."""
        self.tool_log.append(tool_data)
        if len(self.tool_log) > self.max_tool_log_size:
            self.tool_log = self.tool_log[-self.max_tool_log_size:]
    
    def check_time_warning(self) -> str | None:
        """Check for time warnings and return message if any."""
        return self.time_tracker.check_and_get_warning()
    
    def render_time_widget(self) -> Panel:
        """Render the time tracking widget."""
        content = Text()
        
        # Progress bar
        content.append(self.time_tracker.get_progress_bar(30))
        content.append("\n")
        
        # Status
        content.append(self.time_tracker.get_status_string())
        content.append("\n")
        
        # Details
        elapsed = self.time_tracker.get_elapsed_minutes()
        total = self.time_tracker.duration_minutes
        content.append(f"Elapsed: {elapsed:.1f}m / {total:.0f}m", style="dim")
        
        # Color based on status
        if self.time_tracker.is_critical_threshold():
            style = "red"
        elif self.time_tracker.is_warning_threshold():
            style = "yellow"
        else:
            style = "green"
        
        return Panel(
            content,
            title="[bold]⏱️ Time Remaining[/bold]",
            border_style=style,
            padding=(0, 1),
        )
    
    def render_agents_widget(self) -> Panel:
        """Render the agents status widget."""
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Agent", style="white")
        table.add_column("Status", style="dim")
        table.add_column("Iter", justify="right")
        
        for agent in self.agents.values():
            status_icon = agent.get_status_icon()
            iter_str = f"{agent.iteration}/{agent.max_iterations}"
            table.add_row(
                agent.name[:25],
                f"{status_icon} {agent.status}",
                iter_str,
            )
        
        if not self.agents:
            table.add_row("No agents yet", "", "")
        
        return Panel(
            table,
            title="[bold]🤖 Agents[/bold]",
            border_style="cyan",
            padding=(0, 1),
        )
    
    def render_resources_widget(self) -> Panel:
        """Render the resource usage widget."""
        content = Text()
        
        content.append("Tokens: ", style="dim")
        content.append(f"{self.resources.input_tokens:,}", style="green")
        content.append(" in / ", style="dim")
        content.append(f"{self.resources.output_tokens:,}", style="blue")
        content.append(" out\n")
        
        if self.resources.cached_tokens > 0:
            content.append("Cached: ", style="dim")
            content.append(f"{self.resources.cached_tokens:,}", style="yellow")
            content.append("\n")
        
        content.append("Cost: ", style="dim")
        content.append(f"${self.resources.total_cost:.4f}", style="green")
        content.append(f"  ({self.resources.request_count} requests)", style="dim")
        
        return Panel(
            content,
            title="[bold]📊 Resources[/bold]",
            border_style="blue",
            padding=(0, 1),
        )
    
    def render_findings_widget(self) -> Panel:
        """Render the findings summary widget."""
        content = Text()
        
        if self.vulnerabilities_found > 0:
            content.append("🔴 ", style="red")
            content.append(f"{self.vulnerabilities_found} vulnerabilities found", style="bold red")
        else:
            content.append("🟢 ", style="green")
            content.append("No vulnerabilities found yet", style="dim")
        
        return Panel(
            content,
            title="[bold]🐞 Findings[/bold]",
            border_style="red" if self.vulnerabilities_found > 0 else "green",
            padding=(0, 1),
        )
    
    def render_tool_log_widget(self) -> Panel:
        """Render recent tool executions widget."""
        content = Text()
        
        for tool_data in self.tool_log[-5:]:
            tool_name = tool_data.get("tool_name", "unknown")
            status = tool_data.get("status", "unknown")
            
            status_icon = "✓" if status == "completed" else "○"
            content.append(f"{status_icon} ", style="green" if status == "completed" else "dim")
            content.append(f"{tool_name}\n", style="cyan")
        
        if not self.tool_log:
            content.append("No tool executions yet", style="dim")
        
        return Panel(
            content,
            title="[bold]🔧 Recent Tools[/bold]",
            border_style="cyan",
            padding=(0, 1),
        )
    
    def render(self) -> Group:
        """Render the full dashboard."""
        widgets = []
        
        if self.show_time_remaining:
            widgets.append(self.render_time_widget())
        
        if self.show_agent_details:
            widgets.append(self.render_agents_widget())
        
        if self.show_resource_usage:
            widgets.append(self.render_resources_widget())
        
        widgets.append(self.render_findings_widget())
        
        if self.show_tool_logs:
            widgets.append(self.render_tool_log_widget())
        
        return Group(*widgets)
    
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the dashboard state."""
        return {
            "time": self.time_tracker.to_dict(),
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "resources": self.resources.to_dict(),
            "vulnerabilities_found": self.vulnerabilities_found,
            "tool_count": len(self.tool_log),
        }
    
    @classmethod
    def from_config(cls, config: "StrixConfig") -> "Dashboard":
        """Create a Dashboard from StrixConfig."""
        time_tracker = TimeTracker.from_config(config)
        
        return cls(
            time_tracker=time_tracker,
            enabled=config.dashboard.enabled,
            refresh_interval=config.dashboard.refresh_interval,
            show_agent_details=config.dashboard.show_agent_details,
            show_tool_logs=config.dashboard.show_tool_logs,
            show_time_remaining=config.dashboard.show_time_remaining,
            show_resource_usage=config.dashboard.show_resource_usage,
        )
