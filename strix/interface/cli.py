import atexit
import json
import os
import signal
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from strix.agents.StrixAgent import StrixAgent
from strix.llm.config import LLMConfig
from strix.telemetry.tracer import Tracer, set_global_tracer

from .utils import build_final_stats_text, build_live_stats_text, get_severity_color


def _write_external_dashboard_state(
    tracer: Tracer,
    state_file: str,
    scan_config: dict[str, Any],
    start_time: datetime,
    duration_minutes: float,
    warning_minutes: float,
) -> None:
    """Write dashboard state to external file for CI/CD dashboard integration.
    
    This enables the external dashboard (started by workflow) to receive
    state updates from Strix even when STRIX_WEB_DASHBOARD is disabled.
    """
    try:
        # Calculate time tracking
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
        
        # Build agents data
        agents_data = {}
        for agent_id, agent_data in tracer.agents.items():
            agents_data[agent_id] = {
                "id": agent_id,
                "name": agent_data.get("name", "Agent"),
                "status": agent_data.get("status", "running"),
                "task": agent_data.get("task", ""),
                "parent_id": agent_data.get("parent_id"),
                "created_at": str(agent_data.get("created_at", "")),
                "updated_at": str(agent_data.get("updated_at", "")),
                "tool_executions": len(agent_data.get("tool_executions", [])),
            }
        
        # Build tool executions (last 100)
        tool_executions = []
        for tool_data in list(tracer.tool_executions.values())[-100:]:
            tool_executions.append({
                "tool_name": tool_data.get("tool_name", "unknown"),
                "status": tool_data.get("status", "unknown"),
                "agent_id": tool_data.get("agent_id"),
                "timestamp": str(tool_data.get("started_at", "")),
            })
        
        # Build live feed entries from recent tool executions
        live_feed = []
        for tool_data in list(tracer.tool_executions.values())[-50:]:
            live_feed.append({
                "type": "tool_execution",
                "tool_name": tool_data.get("tool_name", "unknown"),
                "status": tool_data.get("status", "running"),
                "agent_id": tool_data.get("agent_id"),
                "timestamp": str(tool_data.get("started_at", datetime.now(UTC).isoformat())),
            })
        
        # Get current step from most recent running agent
        current_step = {
            "agent_id": None,
            "agent_name": None,
            "action": "Scanning...",
            "tool_name": None,
            "status": "running",
            "details": {},
        }
        for agent_id, agent_data in tracer.agents.items():
            if agent_data.get("status") == "running":
                agent_tools = tracer.get_agent_tools(agent_id)
                if agent_tools:
                    last_tool = agent_tools[-1]
                    current_step = {
                        "agent_id": agent_id,
                        "agent_name": agent_data.get("name", "Agent"),
                        "action": f"Executing {last_tool.get('tool_name', 'tool')}",
                        "tool_name": last_tool.get("tool_name"),
                        "status": last_tool.get("status", "running"),
                        "details": {},
                    }
                break
        
        # Build resources from tracer
        resources = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "total_cost": 0.0,
            "request_count": 0,
            "api_calls": len(tracer.tool_executions),
        }
        try:
            llm_stats = tracer.get_total_llm_stats()
            if llm_stats and "total" in llm_stats:
                resources.update(llm_stats["total"])
        except Exception:
            pass
        
        # Build vulnerabilities list
        vulnerabilities = []
        for vuln in tracer.vulnerability_reports:
            vulnerabilities.append({
                "id": vuln.get("id", ""),
                "title": vuln.get("title", "Vulnerability"),
                "severity": vuln.get("severity", "info"),
                "target": vuln.get("target", ""),
                "vuln_type": vuln.get("type", "unknown"),
            })
        
        # Build state object
        state = {
            "scan_config": scan_config,
            "agents": agents_data,
            "tool_executions": tool_executions,
            "chat_messages": [],
            "vulnerabilities": vulnerabilities,
            "collaboration": {
                "claims": [],
                "findings": [],
                "work_queue": [],
                "help_requests": [],
                "messages": [],
                "stats": {},
            },
            "resources": resources,
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
            },
            "current_step": current_step,
            "live_feed": live_feed,
            "last_updated": datetime.now(UTC).isoformat(),
        }
        
        # Write to file atomically
        state_path = Path(state_file)
        temp_path = state_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(state, f)
        temp_path.replace(state_path)
        
    except Exception as e:
        # Silent fail - don't interrupt scan for dashboard issues
        pass


async def run_cli(args: Any) -> None:  # noqa: PLR0915
    console = Console()
    
    # Check if web dashboard should be enabled
    web_dashboard_enabled = os.getenv("STRIX_WEB_DASHBOARD", "false").lower() == "true"
    web_dashboard_port = int(os.getenv("STRIX_DASHBOARD_PORT", "8080"))
    web_dashboard_integration = None
    
    # Check for external dashboard state file (for CI/CD integration)
    # This allows Strix to update an external dashboard even when STRIX_WEB_DASHBOARD is false
    external_state_file = os.getenv("STRIX_DASHBOARD_STATE_FILE")
    if external_state_file:
        console.print(f"[bold cyan]📊 External dashboard state file:[/] {external_state_file}")
        console.print()

    start_text = Text()
    start_text.append("🦉 ", style="bold white")
    start_text.append("STRIX CYBERSECURITY AGENT", style="bold green")

    target_text = Text()
    if len(args.targets_info) == 1:
        target_text.append("🎯 Target: ", style="bold cyan")
        target_text.append(args.targets_info[0]["original"], style="bold white")
    else:
        target_text.append("🎯 Targets: ", style="bold cyan")
        target_text.append(f"{len(args.targets_info)} targets\n", style="bold white")
        for i, target_info in enumerate(args.targets_info):
            target_text.append("   • ", style="dim white")
            target_text.append(target_info["original"], style="white")
            if i < len(args.targets_info) - 1:
                target_text.append("\n")

    results_text = Text()
    results_text.append("📊 Results will be saved to: ", style="bold cyan")
    results_text.append(f"strix_runs/{args.run_name}", style="bold white")

    note_text = Text()
    note_text.append("\n\n", style="dim")
    note_text.append("⏱️  ", style="dim")
    note_text.append("This may take a while depending on target complexity. ", style="dim")
    note_text.append("Vulnerabilities will be displayed in real-time.", style="dim")

    startup_panel = Panel(
        Text.assemble(
            start_text,
            "\n\n",
            target_text,
            "\n",
            results_text,
            note_text,
        ),
        title="[bold green]🛡️  STRIX PENETRATION TEST INITIATED",
        title_align="center",
        border_style="green",
        padding=(1, 2),
    )

    console.print("\n")
    console.print(startup_panel)
    console.print()

    scan_mode = getattr(args, "scan_mode", "deep")

    scan_config = {
        "scan_id": args.run_name,
        "targets": args.targets_info,
        "user_instructions": args.instruction or "",
        "run_name": args.run_name,
    }

    llm_config = LLMConfig(scan_mode=scan_mode)
    agent_config = {
        "llm_config": llm_config,
        "max_iterations": 300,
        "non_interactive": True,
    }

    if getattr(args, "local_sources", None):
        agent_config["local_sources"] = args.local_sources

    tracer = Tracer(args.run_name)
    tracer.set_scan_config(scan_config)

    def display_vulnerability(report_id: str, title: str, content: str, severity: str) -> None:
        severity_color = get_severity_color(severity.lower())

        vuln_text = Text()
        vuln_text.append("🐞 ", style="bold red")
        vuln_text.append("VULNERABILITY FOUND", style="bold red")
        vuln_text.append(" • ", style="dim white")
        vuln_text.append(title, style="bold white")

        severity_text = Text()
        severity_text.append("Severity: ", style="dim white")
        severity_text.append(severity.upper(), style=f"bold {severity_color}")

        vuln_panel = Panel(
            Text.assemble(
                vuln_text,
                "\n\n",
                severity_text,
                "\n\n",
                content,
            ),
            title=f"[bold red]🔍 {report_id.upper()}",
            title_align="left",
            border_style="red",
            padding=(1, 2),
        )

        console.print(vuln_panel)
        console.print()

    tracer.vulnerability_found_callback = display_vulnerability

    def cleanup_on_exit() -> None:
        # Stop web dashboard if running
        nonlocal web_dashboard_integration
        if web_dashboard_integration:
            try:
                web_dashboard_integration.stop()
            except Exception:
                pass
        tracer.cleanup()

    def signal_handler(_signum: int, _frame: Any) -> None:
        cleanup_on_exit()
        sys.exit(1)

    atexit.register(cleanup_on_exit)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)

    set_global_tracer(tracer)
    
    # Get time configuration for dashboard
    try:
        from strix.config import get_config
        config = get_config()
        duration_minutes = config.timeframe.duration_minutes
        warning_minutes = config.timeframe.warning_minutes
    except Exception:
        duration_minutes = 60.0
        warning_minutes = 5.0
    
    # Record scan start time
    scan_start_time = datetime.now(UTC)
    
    # Start web dashboard if enabled
    if web_dashboard_enabled:
        try:
            from strix.dashboard.web_integration import setup_web_dashboard
            
            web_dashboard_integration = setup_web_dashboard(
                tracer=tracer,
                host="0.0.0.0",
                port=web_dashboard_port,
                duration_minutes=duration_minutes,
                warning_minutes=warning_minutes,
            )
            
            dashboard_url = web_dashboard_integration.get_url()
            console.print(f"[bold green]🌐 Web Dashboard:[/] {dashboard_url}")
            console.print()
        except Exception as e:
            console.print(f"[yellow]⚠️  Web dashboard failed to start: {e}[/]")
            console.print()

    def create_live_status() -> Panel:
        status_text = Text()
        status_text.append("🦉 ", style="bold white")
        status_text.append("Running penetration test...", style="bold #22c55e")
        status_text.append("\n\n")

        stats_text = build_live_stats_text(tracer, agent_config)
        if stats_text:
            status_text.append(stats_text)

        return Panel(
            status_text,
            title="[bold #22c55e]🔍 Live Penetration Test Status",
            title_align="center",
            border_style="#22c55e",
            padding=(1, 2),
        )

    try:
        console.print()

        with Live(
            create_live_status(), console=console, refresh_per_second=2, transient=False
        ) as live:
            stop_updates = threading.Event()

            def update_status() -> None:
                while not stop_updates.is_set():
                    try:
                        live.update(create_live_status())
                        
                        # Update web dashboard if enabled
                        if web_dashboard_integration:
                            try:
                                web_dashboard_integration._sync_from_tracer()
                            except Exception:
                                pass
                        
                        # Write to external dashboard state file if configured
                        # This enables CI/CD dashboards to receive updates
                        if external_state_file:
                            try:
                                _write_external_dashboard_state(
                                    tracer=tracer,
                                    state_file=external_state_file,
                                    scan_config=scan_config,
                                    start_time=scan_start_time,
                                    duration_minutes=duration_minutes,
                                    warning_minutes=warning_minutes,
                                )
                            except Exception:
                                pass
                        
                        time.sleep(2)
                    except Exception:  # noqa: BLE001
                        break

            update_thread = threading.Thread(target=update_status, daemon=True)
            update_thread.start()

            try:
                agent = StrixAgent(agent_config)
                result = await agent.execute_scan(scan_config)

                if isinstance(result, dict) and not result.get("success", True):
                    error_msg = result.get("error", "Unknown error")
                    console.print()
                    console.print(f"[bold red]❌ Penetration test failed:[/] {error_msg}")
                    console.print()
                    sys.exit(1)
            finally:
                stop_updates.set()
                update_thread.join(timeout=1)

    except Exception as e:
        console.print(f"[bold red]Error during penetration test:[/] {e}")
        raise

    console.print()
    final_stats_text = Text()
    final_stats_text.append("📊 ", style="bold cyan")
    final_stats_text.append("PENETRATION TEST COMPLETED", style="bold green")
    final_stats_text.append("\n\n")

    stats_text = build_final_stats_text(tracer)
    if stats_text:
        final_stats_text.append(stats_text)

    final_stats_panel = Panel(
        final_stats_text,
        title="[bold green]✅ Final Statistics",
        title_align="center",
        border_style="green",
        padding=(1, 2),
    )
    console.print(final_stats_panel)

    if tracer.final_scan_result:
        console.print()

        final_report_text = Text()
        final_report_text.append("📄 ", style="bold cyan")
        final_report_text.append("FINAL PENETRATION TEST REPORT", style="bold cyan")

        final_report_panel = Panel(
            Text.assemble(
                final_report_text,
                "\n\n",
                tracer.final_scan_result,
            ),
            title="[bold cyan]📊 PENETRATION TEST SUMMARY",
            title_align="center",
            border_style="cyan",
            padding=(1, 2),
        )

        console.print(final_report_panel)
        console.print()
