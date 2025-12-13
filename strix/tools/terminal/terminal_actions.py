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
        },
        "available_package_managers": ["apt-get", "pip", "pip3", "npm", "go install", "pipx"],
        "note": (
            "Root access allows unrestricted command execution. "
            "Use responsibly within the sandboxed environment."
            if root_enabled
            else "Standard access mode. Use --root-access flag to enable full access."
        ),
    }
