"""
Root Access Configuration for Strix AI Agent

This module provides configuration for enabling root/unrestricted terminal access
for the Strix AI agent. When enabled, the agent can execute commands with elevated
privileges including:

- Installing additional tools and packages (apt-get, pip, npm, etc.)
- Modifying system configurations
- Running commands as root user
- Downloading and setting up custom security tools
- Full network configuration access

WARNING: Root access should only be enabled in controlled, sandboxed environments.
The Strix Docker container is designed to be fully sandboxed, so enabling root
access does not pose a risk to the host system.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


logger = logging.getLogger(__name__)


class TerminalAccessLevel(str, Enum):
    """Terminal access level for the AI agent."""

    STANDARD = "standard"  # Normal user access (default)
    ELEVATED = "elevated"  # Can use sudo for specific commands
    ROOT = "root"  # Full root access - unrestricted command execution


@dataclass
class RootAccessConfig:
    """Configuration for root/elevated terminal access."""

    access_level: TerminalAccessLevel = TerminalAccessLevel.STANDARD
    allow_package_install: bool = False
    allow_tool_download: bool = False
    allow_network_config: bool = False
    allow_system_modification: bool = False
    custom_allowed_commands: list[str] | None = None
    command_timeout: int = 300  # Increased timeout for package installations

    @classmethod
    def from_environment(cls) -> "RootAccessConfig":
        """Create configuration from environment variables."""
        access_level_str = os.getenv("STRIX_ACCESS_LEVEL", "standard").lower()

        try:
            access_level = TerminalAccessLevel(access_level_str)
        except ValueError:
            logger.warning(f"Invalid access level '{access_level_str}', using standard")
            access_level = TerminalAccessLevel.STANDARD

        # Check for root access environment variable
        if os.getenv("STRIX_ROOT_ACCESS", "").lower() == "true":
            access_level = TerminalAccessLevel.ROOT

        return cls(
            access_level=access_level,
            allow_package_install=os.getenv("STRIX_ALLOW_PACKAGE_INSTALL", "").lower() == "true"
            or access_level == TerminalAccessLevel.ROOT,
            allow_tool_download=os.getenv("STRIX_ALLOW_TOOL_DOWNLOAD", "").lower() == "true"
            or access_level == TerminalAccessLevel.ROOT,
            allow_network_config=os.getenv("STRIX_ALLOW_NETWORK_CONFIG", "").lower() == "true"
            or access_level == TerminalAccessLevel.ROOT,
            allow_system_modification=os.getenv("STRIX_ALLOW_SYSTEM_MOD", "").lower() == "true"
            or access_level == TerminalAccessLevel.ROOT,
            command_timeout=int(os.getenv("STRIX_COMMAND_TIMEOUT", "300")),
        )

    def is_root_enabled(self) -> bool:
        """Check if root access is enabled."""
        return self.access_level == TerminalAccessLevel.ROOT

    def is_elevated(self) -> bool:
        """Check if elevated access is enabled."""
        return self.access_level in (TerminalAccessLevel.ELEVATED, TerminalAccessLevel.ROOT)

    def can_install_packages(self) -> bool:
        """Check if package installation is allowed."""
        return self.allow_package_install or self.is_root_enabled()

    def can_download_tools(self) -> bool:
        """Check if tool download is allowed."""
        return self.allow_tool_download or self.is_root_enabled()

    def can_modify_network(self) -> bool:
        """Check if network configuration is allowed."""
        return self.allow_network_config or self.is_root_enabled()

    def can_modify_system(self) -> bool:
        """Check if system modification is allowed."""
        return self.allow_system_modification or self.is_root_enabled()


# Commands that are always allowed regardless of access level
ALWAYS_ALLOWED_COMMANDS = [
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "pwd",
    "cd",
    "echo",
    "printf",
    "whoami",
    "id",
    "env",
    "date",
    "uname",
    "file",
    "which",
    "whereis",
    "man",
    "help",
    "history",
    # Security testing tools (already installed)
    "nmap",
    "sqlmap",
    "nuclei",
    "subfinder",
    "httpx",
    "ffuf",
    "dirsearch",
    "nikto",
    "wfuzz",
    "gobuster",
    "dirb",
    "curl",
    "wget",
    "python",
    "python3",
    "pip",
    "pip3",
    "go",
    "node",
    "npm",
    "git",
]

# Commands that require elevated access
ELEVATED_COMMANDS = [
    "sudo",
    "apt-get",
    "apt",
    "dpkg",
    "pip install",
    "npm install -g",
    "go install",
    "make install",
    "systemctl",
    "service",
    "iptables",
    "ip",
    "ifconfig",
    "route",
    "netstat",
    "ss",
    "mount",
    "umount",
    "chmod",
    "chown",
    "chgrp",
]

# Commands that require root access
ROOT_ONLY_COMMANDS = [
    "rm -rf /",
    "dd if=/dev/",
    "mkfs",
    "fdisk",
    "parted",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init",
]


def get_root_access_config() -> RootAccessConfig:
    """Get the current root access configuration."""
    return RootAccessConfig.from_environment()


def is_command_allowed(command: str, config: RootAccessConfig | None = None) -> tuple[bool, str]:
    """
    Check if a command is allowed based on the access configuration.

    Args:
        command: The command to check
        config: Optional access configuration (uses environment if not provided)

    Returns:
        Tuple of (is_allowed, reason)
    """
    if config is None:
        config = get_root_access_config()

    command_lower = command.lower().strip()
    base_command = command_lower.split()[0] if command_lower else ""

    # Root access allows everything
    if config.is_root_enabled():
        return True, "Root access enabled - all commands allowed"

    # Check for always blocked commands (even in root mode for safety)
    for blocked in ROOT_ONLY_COMMANDS:
        if blocked in command_lower:
            if not config.is_root_enabled():
                return False, f"Command '{blocked}' requires root access"

    # Check for elevated commands
    for elevated in ELEVATED_COMMANDS:
        if command_lower.startswith(elevated) or elevated in command_lower:
            if config.is_elevated():
                return True, "Elevated access granted"
            return False, f"Command '{elevated}' requires elevated access"

    # Always allowed commands
    if base_command in ALWAYS_ALLOWED_COMMANDS:
        return True, "Command is in allowed list"

    # Standard access - allow most commands that aren't explicitly restricted
    if config.access_level == TerminalAccessLevel.STANDARD:
        # Be permissive by default for pentesting tools
        return True, "Standard access - command allowed"

    return True, "Command allowed"


def wrap_command_for_access(command: str, config: RootAccessConfig | None = None) -> str:
    """
    Wrap a command with appropriate sudo/access prefix if needed.

    Args:
        command: The command to wrap
        config: Optional access configuration

    Returns:
        The command, potentially wrapped with sudo
    """
    if config is None:
        config = get_root_access_config()

    # If root access is enabled, wrap with sudo if needed
    if config.is_root_enabled():
        # Check if command already has sudo
        if command.strip().startswith("sudo "):
            return command

        # Check if command needs sudo
        command_lower = command.lower().strip()
        for elevated in ELEVATED_COMMANDS:
            if command_lower.startswith(elevated) or elevated in command_lower:
                return f"sudo {command}"

    return command


def get_access_info(config: RootAccessConfig | None = None) -> dict[str, Any]:
    """Get information about the current access configuration."""
    if config is None:
        config = get_root_access_config()

    return {
        "access_level": config.access_level.value,
        "is_root": config.is_root_enabled(),
        "is_elevated": config.is_elevated(),
        "can_install_packages": config.can_install_packages(),
        "can_download_tools": config.can_download_tools(),
        "can_modify_network": config.can_modify_network(),
        "can_modify_system": config.can_modify_system(),
        "command_timeout": config.command_timeout,
    }


# Export the configuration class and functions
__all__ = [
    "RootAccessConfig",
    "TerminalAccessLevel",
    "get_root_access_config",
    "is_command_allowed",
    "wrap_command_for_access",
    "get_access_info",
    "ALWAYS_ALLOWED_COMMANDS",
    "ELEVATED_COMMANDS",
]
