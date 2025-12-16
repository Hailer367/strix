import os
from typing import Any

from strix.tools.registry import register_tool

from .terminal_manager import get_terminal_manager


def _get_root_access_info() -> dict[str, Any]:
    """Get information about root access configuration."""
    root_enabled = os.getenv("STRIX_ROOT_ACCESS", "").lower() == "true"
    return {
        "root_access_enabled": root_enabled,
        "access_level": os.getenv("STRIX_ACCESS_LEVEL", "standard"),
        "command_timeout": int(os.getenv("STRIX_COMMAND_TIMEOUT", "300")),
    }


@register_tool
def terminal_execute(
    command: str,
    is_input: bool = False,
    timeout: float | None = None,
    terminal_id: str | None = None,
    no_enter: bool = False,
    use_sudo: bool = False,
) -> dict[str, Any]:
    """
    Execute a command in the terminal.

    When STRIX_ROOT_ACCESS=true is set, the agent has full root access
    and can execute any command including:
    - Installing packages (apt-get, pip, npm, etc.)
    - Downloading and setting up tools
    - Modifying system configurations
    - Running privileged network commands

    Args:
        command: The command to execute
        is_input: Whether this is input to a running command
        timeout: Command timeout in seconds
        terminal_id: Terminal session ID
        no_enter: Don't press enter after command
        use_sudo: Explicitly prepend sudo to the command

    Returns:
        Command execution result
    """
    manager = get_terminal_manager()

    # Prepend sudo if explicitly requested
    if use_sudo and not command.strip().startswith("sudo "):
        command = f"sudo {command}"

    try:
        result = manager.execute_command(
            command=command,
            is_input=is_input,
            timeout=timeout,
            terminal_id=terminal_id,
            no_enter=no_enter,
        )

        # Add root access info to result
        result["root_access"] = _get_root_access_info()

        return result
    except (ValueError, RuntimeError) as e:
        return {
            "error": str(e),
            "command": command,
            "terminal_id": terminal_id or "default",
            "content": "",
            "status": "error",
            "exit_code": None,
            "working_dir": None,
            "root_access": _get_root_access_info(),
        }


@register_tool
def terminal_get_root_status() -> dict[str, Any]:
    """
    Get the current root access status and configuration.

    Returns information about:
    - Whether root access is enabled
    - Current access level (standard, elevated, root)
    - Command timeout settings
    - Available privileged operations

    Returns:
        Root access configuration information
    """
    root_enabled = os.getenv("STRIX_ROOT_ACCESS", "").lower() == "true"
    access_level = os.getenv("STRIX_ACCESS_LEVEL", "standard")
    manager = get_terminal_manager()

    return {
        "root_access_enabled": root_enabled,
        "access_level": access_level,
        "command_timeout": int(os.getenv("STRIX_COMMAND_TIMEOUT", "300")),
        "capabilities": {
            "can_install_packages": root_enabled or access_level in ("elevated", "root"),
            "can_download_tools": root_enabled or access_level in ("elevated", "root"),
            "can_modify_network": root_enabled or access_level == "root",
            "can_modify_system": root_enabled or access_level == "root",
            "can_use_sudo": root_enabled or access_level in ("elevated", "root"),
            "can_create_temporary_terminals": True,
            "max_temporary_terminals": manager.MAX_TEMPORARY_TERMINALS,
        },
        "available_package_managers": ["apt-get", "pip", "pip3", "npm", "go install", "pipx"],
        "note": (
            "Root access allows unrestricted command execution. "
            "Use responsibly within the sandboxed environment."
            if root_enabled
            else "Standard access mode. Use --root-access flag to enable full access."
        ),
    }


@register_tool
def terminal_create_temporary(
    task_description: str = "",
    timeout_minutes: float = 30.0,
) -> dict[str, Any]:
    """
    Create a new temporary terminal with root access for parallel task execution.

    Temporary terminals allow the AI to work on multiple tasks simultaneously.
    Each temporary terminal has the same root access as the main terminal and
    can be used to run commands, install packages, and perform any other
    terminal operations.

    The AI should close temporary terminals when tasks are complete to free
    up resources.

    Maximum of 7 temporary terminals can be active at once.

    Args:
        task_description: Description of what this terminal will be used for
                         (helps with organization and debugging)
        timeout_minutes: Auto-close timeout in minutes (default: 30 minutes)
                        After this time, the terminal will be automatically closed

    Returns:
        dict containing:
        - terminal_id: The unique ID for this temporary terminal
        - status: 'created' on success
        - root_access: Root access configuration
        - active_temporary_terminals: Current count of active temp terminals
        - remaining_slots: Number of temp terminals that can still be created
    
    Example usage:
        1. Create temporary terminal for a specific task:
           terminal_create_temporary(task_description="Running nmap scan")
        
        2. Execute commands on the temporary terminal:
           terminal_execute(command="nmap -sV target.com", terminal_id="temp_1")
        
        3. Close when done:
           terminal_close_temporary(terminal_id="temp_1")
    """
    manager = get_terminal_manager()
    return manager.create_temporary_terminal(
        task_description=task_description,
        timeout_seconds=timeout_minutes * 60,
    )


@register_tool
def terminal_close_temporary(terminal_id: str) -> dict[str, Any]:
    """
    Close a temporary terminal and clean up its resources.

    This should be called when the task on a temporary terminal is complete.
    Closing temporary terminals frees up slots for new ones.

    Args:
        terminal_id: The ID of the temporary terminal to close (e.g., "temp_1")
                    Must be a temporary terminal ID starting with "temp_"

    Returns:
        dict containing:
        - terminal_id: The closed terminal's ID
        - status: 'closed' on success
        - active_temporary_terminals: Remaining active temp terminals
        - remaining_slots: Number of temp terminals that can be created
    """
    manager = get_terminal_manager()
    return manager.close_temporary_terminal(terminal_id)


@register_tool
def terminal_list_temporary() -> dict[str, Any]:
    """
    List all active temporary terminals with their status and metadata.

    Use this to see which temporary terminals are available and their
    current state. This helps with managing parallel tasks.

    Returns:
        dict containing:
        - temporary_terminals: List of temporary terminal info
          Each entry includes:
          - terminal_id: The terminal's unique ID
          - task_description: What the terminal is being used for
          - age_seconds: How long the terminal has been active
          - timeout_remaining_seconds: Time until auto-close
          - is_running: Whether commands are currently executing
          - working_dir: Current working directory
        - total_count: Number of active temporary terminals
        - max_allowed: Maximum allowed (7)
        - remaining_slots: How many more can be created
    """
    manager = get_terminal_manager()
    return manager.list_temporary_terminals()


@register_tool
def terminal_list_all() -> dict[str, Any]:
    """
    List all terminal sessions including the main terminal and temporary terminals.

    Provides a complete overview of all active terminals and their status.

    Returns:
        dict containing:
        - sessions: Dictionary of all terminal sessions with their info
        - total_count: Total number of active sessions
        - temporary_terminal_count: Number of temporary terminals
        - max_temporary_terminals: Maximum allowed temporary terminals (7)
    """
    manager = get_terminal_manager()
    return manager.list_sessions()


@register_tool
def terminal_cleanup_expired() -> dict[str, Any]:
    """
    Clean up temporary terminals that have exceeded their timeout.

    Temporary terminals are automatically cleaned up after their timeout
    (default 30 minutes), but this tool can be used to force cleanup.

    Returns:
        dict containing:
        - cleaned_up_terminals: List of terminal IDs that were closed
        - count: Number of terminals cleaned up
        - message: Summary message
    """
    manager = get_terminal_manager()
    return manager.cleanup_expired_temporary_terminals()
