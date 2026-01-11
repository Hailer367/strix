import os
from typing import Any

from strix.tools.registry import register_tool


# Minimum percentage of allocated time that must be used before allowing finish
# Default: 80% of allocated time must be used (e.g., for 4 hours, must use at least 3.2 hours)
# Set STRIX_MIN_TIME_PERCENT=0 to disable this check
MIN_TIME_USAGE_PERCENT = float(os.getenv("STRIX_MIN_TIME_PERCENT", "80"))


def _check_minimum_time_elapsed(agent_state: Any) -> dict[str, Any] | None:
    """Check if the agent has used at least the minimum required time.
    
    This prevents agents from finishing too early when they have been allocated
    a specific timeframe for scanning. The agent should utilize most of the 
    allocated time for thorough testing.
    
    Returns:
        Error dict if minimum time hasn't elapsed, None otherwise.
    """
    # Skip check if disabled
    if MIN_TIME_USAGE_PERCENT <= 0:
        return None
    
    if agent_state is None:
        return None
    
    # Check if session timer is active
    if not hasattr(agent_state, "session_start_time") or agent_state.session_start_time is None:
        return None
    
    if not hasattr(agent_state, "session_duration_minutes"):
        return None
    
    try:
        elapsed_minutes = agent_state.get_elapsed_session_minutes()
        total_minutes = agent_state.session_duration_minutes
        remaining_minutes = agent_state.get_remaining_session_minutes()
        
        # Calculate usage percentage
        usage_percent = (elapsed_minutes / total_minutes) * 100 if total_minutes > 0 else 100
        
        # Check if minimum time has been used
        if usage_percent < MIN_TIME_USAGE_PERCENT:
            min_required_minutes = (MIN_TIME_USAGE_PERCENT / 100) * total_minutes
            additional_minutes_needed = min_required_minutes - elapsed_minutes
            
            return {
                "success": False,
                "message": (
                    f"🚫 CANNOT FINISH YET: You have only used {elapsed_minutes:.1f} minutes "
                    f"({usage_percent:.1f}%) of your allocated {total_minutes:.0f} minutes.\n\n"
                    f"You must use at least {MIN_TIME_USAGE_PERCENT:.0f}% ({min_required_minutes:.0f} minutes) "
                    f"of your allocated time before finishing.\n\n"
                    f"⏰ You have {remaining_minutes:.1f} minutes remaining. "
                    f"You need to work for at least {additional_minutes_needed:.1f} more minutes.\n\n"
                    f"WHAT TO DO:\n"
                    f"1. Continue your security assessment - there are likely more vulnerabilities to find\n"
                    f"2. Explore additional attack vectors you haven't tried yet\n"
                    f"3. Go deeper on promising findings\n"
                    f"4. Test with different payloads and techniques\n"
                    f"5. Create subagents for parallel testing\n\n"
                    f"Remember: Bug bounty hunters spend DAYS on single targets. "
                    f"Use your time wisely and thoroughly!"
                ),
                "time_stats": {
                    "elapsed_minutes": elapsed_minutes,
                    "total_minutes": total_minutes,
                    "remaining_minutes": remaining_minutes,
                    "usage_percent": usage_percent,
                    "min_required_percent": MIN_TIME_USAGE_PERCENT,
                    "min_required_minutes": min_required_minutes,
                    "additional_minutes_needed": additional_minutes_needed,
                },
            }
        
    except (AttributeError, TypeError, ZeroDivisionError) as e:
        # If we can't check time, allow finish (fail-safe)
        import logging
        logging.warning(f"Could not check minimum time elapsed: {e}")
        return None
    
    return None


def _validate_root_agent(agent_state: Any) -> dict[str, Any] | None:
    if (
        agent_state is not None
        and hasattr(agent_state, "parent_id")
        and agent_state.parent_id is not None
    ):
        return {
            "success": False,
            "message": (
                "This tool can only be used by the root/main agent. "
                "Subagents must use agent_finish instead."
            ),
        }
    return None


def _validate_content(content: str) -> dict[str, Any] | None:
    if not content or not content.strip():
        return {"success": False, "message": "Content cannot be empty"}
    return None


def _check_active_agents(agent_state: Any = None) -> dict[str, Any] | None:
    try:
        from strix.tools.agents_graph.agents_graph_actions import _agent_graph

        current_agent_id = None
        if agent_state and hasattr(agent_state, "agent_id"):
            current_agent_id = agent_state.agent_id

        running_agents = []
        stopping_agents = []

        for agent_id, node in _agent_graph.get("nodes", {}).items():
            if agent_id == current_agent_id:
                continue

            status = node.get("status", "")
            if status == "running":
                running_agents.append(
                    {
                        "id": agent_id,
                        "name": node.get("name", "Unknown"),
                        "task": node.get("task", "No task description"),
                    }
                )
            elif status == "stopping":
                stopping_agents.append(
                    {
                        "id": agent_id,
                        "name": node.get("name", "Unknown"),
                    }
                )

        if running_agents or stopping_agents:
            message_parts = ["Cannot finish scan while other agents are still active:"]

            if running_agents:
                message_parts.append("\n\nRunning agents:")
                message_parts.extend(
                    [
                        f"  - {agent['name']} ({agent['id']}): {agent['task']}"
                        for agent in running_agents
                    ]
                )

            if stopping_agents:
                message_parts.append("\n\nStopping agents:")
                message_parts.extend(
                    [f"  - {agent['name']} ({agent['id']})" for agent in stopping_agents]
                )

            message_parts.extend(
                [
                    "\n\nSuggested actions:",
                    "1. Use wait_for_message to wait for all agents to complete",
                    "2. Send messages to agents asking them to finish if urgent",
                    "3. Use view_agent_graph to monitor agent status",
                ]
            )

            return {
                "success": False,
                "message": "\n".join(message_parts),
                "active_agents": {
                    "running": len(running_agents),
                    "stopping": len(stopping_agents),
                    "details": {
                        "running": running_agents,
                        "stopping": stopping_agents,
                    },
                },
            }

    except ImportError:
        import logging

        logging.warning("Could not check agent graph status - agents_graph module unavailable")

    return None


def _finalize_with_tracer(content: str, success: bool) -> dict[str, Any]:
    try:
        from strix.telemetry.tracer import get_global_tracer

        tracer = get_global_tracer()
        if tracer:
            tracer.set_final_scan_result(
                content=content.strip(),
                success=success,
            )

            return {
                "success": True,
                "scan_completed": True,
                "message": "Scan completed successfully"
                if success
                else "Scan completed with errors",
                "vulnerabilities_found": len(tracer.vulnerability_reports),
            }

        import logging

        logging.warning("Global tracer not available - final scan result not stored")

        return {  # noqa: TRY300
            "success": True,
            "scan_completed": True,
            "message": "Scan completed successfully (not persisted)"
            if success
            else "Scan completed with errors (not persisted)",
            "warning": "Final result could not be persisted - tracer unavailable",
        }

    except ImportError:
        return {
            "success": True,
            "scan_completed": True,
            "message": "Scan completed successfully (not persisted)"
            if success
            else "Scan completed with errors (not persisted)",
            "warning": "Final result could not be persisted - tracer module unavailable",
        }


@register_tool(sandbox_execution=False)
def finish_scan(
    content: str,
    success: bool = True,
    agent_state: Any = None,
    force_finish: bool = False,
) -> dict[str, Any]:
    """Finish the security scan and generate final report.
    
    This tool can only be used by the root/main agent to conclude the scan.
    The agent must have used at least 80% of allocated time before finishing
    (unless force_finish=True or time has naturally expired).
    
    Args:
        content: The final scan report/summary content
        success: Whether the scan was successful overall
        agent_state: The agent's state (injected automatically)
        force_finish: If True, bypass the minimum time check (use sparingly)
    
    Returns:
        Dictionary with completion status and any error messages.
    """
    try:
        validation_error = _validate_root_agent(agent_state)
        if validation_error:
            return validation_error

        validation_error = _validate_content(content)
        if validation_error:
            return validation_error

        # Check if minimum time has elapsed (unless force_finish is set)
        # This prevents agents from finishing too early
        if not force_finish:
            time_error = _check_minimum_time_elapsed(agent_state)
            if time_error:
                return time_error

        active_agents_error = _check_active_agents(agent_state)
        if active_agents_error:
            return active_agents_error

        return _finalize_with_tracer(content, success)

    except (ValueError, TypeError, KeyError) as e:
        return {"success": False, "message": f"Failed to complete scan: {e!s}"}
