import atexit
import contextlib
import os
import signal
import sys
import threading
import time
from typing import Any

from .terminal_session import TerminalSession


class TerminalManager:
    """
    Manages terminal sessions including a main terminal and temporary terminals.
    
    The manager supports:
    - One main terminal (default) with root access
    - Up to 7 temporary terminals with root access that can be created/destroyed dynamically
    - Temporary terminals are automatically cleaned up after use or timeout
    """
    
    # Maximum number of temporary terminals allowed
    MAX_TEMPORARY_TERMINALS = 7
    
    # Prefix for temporary terminal IDs
    TEMPORARY_TERMINAL_PREFIX = "temp_"
    
    # Default timeout for temporary terminals (30 minutes)
    TEMPORARY_TERMINAL_TIMEOUT = 1800  # seconds
    
    def __init__(self) -> None:
        self.sessions: dict[str, TerminalSession] = {}
        self._lock = threading.Lock()
        self.default_terminal_id = "default"
        self.default_timeout = 30.0
        
        # Track temporary terminals with their creation times and metadata
        self._temporary_terminals: dict[str, dict[str, Any]] = {}
        
        # Counter for generating unique temporary terminal IDs
        self._temp_terminal_counter = 0

        self._register_cleanup_handlers()

    def execute_command(
        self,
        command: str,
        is_input: bool = False,
        timeout: float | None = None,
        terminal_id: str | None = None,
        no_enter: bool = False,
    ) -> dict[str, Any]:
        if terminal_id is None:
            terminal_id = self.default_terminal_id

        session = self._get_or_create_session(terminal_id)

        try:
            result = session.execute(command, is_input, timeout or self.default_timeout, no_enter)

            return {
                "content": result["content"],
                "command": command,
                "terminal_id": terminal_id,
                "status": result["status"],
                "exit_code": result.get("exit_code"),
                "working_dir": result.get("working_dir"),
            }

        except RuntimeError as e:
            return {
                "error": str(e),
                "command": command,
                "terminal_id": terminal_id,
                "content": "",
                "status": "error",
                "exit_code": None,
                "working_dir": None,
            }
        except OSError as e:
            return {
                "error": f"System error: {e}",
                "command": command,
                "terminal_id": terminal_id,
                "content": "",
                "status": "error",
                "exit_code": None,
                "working_dir": None,
            }

    def _get_or_create_session(self, terminal_id: str) -> TerminalSession:
        with self._lock:
            if terminal_id not in self.sessions:
                self.sessions[terminal_id] = TerminalSession(terminal_id)
            return self.sessions[terminal_id]

    def close_session(self, terminal_id: str | None = None) -> dict[str, Any]:
        if terminal_id is None:
            terminal_id = self.default_terminal_id

        with self._lock:
            if terminal_id not in self.sessions:
                return {
                    "terminal_id": terminal_id,
                    "message": f"Terminal '{terminal_id}' not found",
                    "status": "not_found",
                }

            session = self.sessions.pop(terminal_id)
            
            # Also remove from temporary terminals tracking if applicable
            if terminal_id in self._temporary_terminals:
                del self._temporary_terminals[terminal_id]

        try:
            session.close()
        except (RuntimeError, OSError) as e:
            return {
                "terminal_id": terminal_id,
                "error": f"Failed to close terminal '{terminal_id}': {e}",
                "status": "error",
            }
        else:
            return {
                "terminal_id": terminal_id,
                "message": f"Terminal '{terminal_id}' closed successfully",
                "status": "closed",
            }
    
    def _is_temporary_terminal(self, terminal_id: str) -> bool:
        """Check if a terminal ID is for a temporary terminal."""
        return terminal_id.startswith(self.TEMPORARY_TERMINAL_PREFIX)
    
    def _get_temporary_terminal_count(self) -> int:
        """Get the current count of active temporary terminals."""
        return len(self._temporary_terminals)
    
    def create_temporary_terminal(
        self,
        task_description: str = "",
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """
        Create a new temporary terminal with root access.
        
        Temporary terminals are designed for the AI to perform parallel tasks.
        They have the same root access as the main terminal and can be closed
        when the task is complete.
        
        Args:
            task_description: Optional description of what this terminal will be used for
            timeout_seconds: Optional custom timeout (default: 30 minutes)
            
        Returns:
            dict containing terminal_id, status, and root_access info
        """
        with self._lock:
            # Check if we've reached the maximum number of temporary terminals
            if self._get_temporary_terminal_count() >= self.MAX_TEMPORARY_TERMINALS:
                return {
                    "error": f"Maximum number of temporary terminals ({self.MAX_TEMPORARY_TERMINALS}) reached",
                    "status": "limit_reached",
                    "active_temporary_terminals": self._get_temporary_terminal_count(),
                    "max_allowed": self.MAX_TEMPORARY_TERMINALS,
                    "suggestion": "Close an existing temporary terminal before creating a new one",
                }
            
            # Generate unique terminal ID
            self._temp_terminal_counter += 1
            terminal_id = f"{self.TEMPORARY_TERMINAL_PREFIX}{self._temp_terminal_counter}"
            
            # Create the terminal session
            try:
                session = TerminalSession(terminal_id)
                self.sessions[terminal_id] = session
                
                # Track the temporary terminal with metadata
                self._temporary_terminals[terminal_id] = {
                    "created_at": time.time(),
                    "task_description": task_description,
                    "timeout_seconds": timeout_seconds or self.TEMPORARY_TERMINAL_TIMEOUT,
                }
                
                # Get root access info
                root_enabled = os.getenv("STRIX_ROOT_ACCESS", "").lower() == "true"
                access_level = os.getenv("STRIX_ACCESS_LEVEL", "standard")
                
                return {
                    "terminal_id": terminal_id,
                    "status": "created",
                    "message": f"Temporary terminal '{terminal_id}' created successfully",
                    "task_description": task_description,
                    "root_access": {
                        "root_access_enabled": root_enabled,
                        "access_level": access_level,
                        "command_timeout": int(os.getenv("STRIX_COMMAND_TIMEOUT", "300")),
                    },
                    "active_temporary_terminals": self._get_temporary_terminal_count(),
                    "max_allowed": self.MAX_TEMPORARY_TERMINALS,
                    "remaining_slots": self.MAX_TEMPORARY_TERMINALS - self._get_temporary_terminal_count(),
                }
            except (RuntimeError, OSError) as e:
                return {
                    "error": f"Failed to create temporary terminal: {e}",
                    "status": "error",
                }
    
    def close_temporary_terminal(self, terminal_id: str) -> dict[str, Any]:
        """
        Close a temporary terminal and clean up its resources.
        
        This should be called when the AI has finished its task on a temporary terminal.
        
        Args:
            terminal_id: The ID of the temporary terminal to close
            
        Returns:
            dict containing status and result information
        """
        if not self._is_temporary_terminal(terminal_id):
            return {
                "error": f"'{terminal_id}' is not a temporary terminal",
                "status": "invalid",
                "hint": "Use close_session() for non-temporary terminals or provide a valid temporary terminal ID",
            }
        
        result = self.close_session(terminal_id)
        
        # Add additional info about remaining temporary terminals
        with self._lock:
            result["active_temporary_terminals"] = self._get_temporary_terminal_count()
            result["remaining_slots"] = self.MAX_TEMPORARY_TERMINALS - self._get_temporary_terminal_count()
        
        return result
    
    def list_temporary_terminals(self) -> dict[str, Any]:
        """
        List all active temporary terminals with their metadata.
        
        Returns:
            dict containing list of temporary terminals and their status
        """
        with self._lock:
            terminals = []
            current_time = time.time()
            
            for terminal_id, metadata in self._temporary_terminals.items():
                session = self.sessions.get(terminal_id)
                age_seconds = current_time - metadata["created_at"]
                timeout_remaining = metadata["timeout_seconds"] - age_seconds
                
                terminals.append({
                    "terminal_id": terminal_id,
                    "task_description": metadata["task_description"],
                    "created_at": metadata["created_at"],
                    "age_seconds": age_seconds,
                    "timeout_remaining_seconds": max(0, timeout_remaining),
                    "is_running": session.is_running() if session else False,
                    "working_dir": session.get_working_dir() if session else None,
                })
            
            return {
                "temporary_terminals": terminals,
                "total_count": len(terminals),
                "max_allowed": self.MAX_TEMPORARY_TERMINALS,
                "remaining_slots": self.MAX_TEMPORARY_TERMINALS - len(terminals),
            }
    
    def cleanup_expired_temporary_terminals(self) -> dict[str, Any]:
        """
        Clean up temporary terminals that have exceeded their timeout.
        
        Returns:
            dict containing information about cleaned up terminals
        """
        with self._lock:
            current_time = time.time()
            expired_terminals = []
            
            for terminal_id, metadata in list(self._temporary_terminals.items()):
                age_seconds = current_time - metadata["created_at"]
                if age_seconds > metadata["timeout_seconds"]:
                    expired_terminals.append(terminal_id)
        
        # Close expired terminals (outside lock to avoid deadlock)
        closed_terminals = []
        for terminal_id in expired_terminals:
            result = self.close_session(terminal_id)
            if result.get("status") == "closed":
                closed_terminals.append(terminal_id)
        
        return {
            "cleaned_up_terminals": closed_terminals,
            "count": len(closed_terminals),
            "message": f"Cleaned up {len(closed_terminals)} expired temporary terminal(s)",
        }

    def list_sessions(self) -> dict[str, Any]:
        with self._lock:
            session_info: dict[str, dict[str, Any]] = {}
            for tid, session in self.sessions.items():
                is_temp = self._is_temporary_terminal(tid)
                info = {
                    "is_running": session.is_running(),
                    "working_dir": session.get_working_dir(),
                    "is_temporary": is_temp,
                }
                
                # Add metadata for temporary terminals
                if is_temp and tid in self._temporary_terminals:
                    metadata = self._temporary_terminals[tid]
                    info["task_description"] = metadata.get("task_description", "")
                    info["created_at"] = metadata.get("created_at")
                    info["age_seconds"] = time.time() - metadata.get("created_at", time.time())
                
                session_info[tid] = info

        return {
            "sessions": session_info, 
            "total_count": len(session_info),
            "temporary_terminal_count": self._get_temporary_terminal_count(),
            "max_temporary_terminals": self.MAX_TEMPORARY_TERMINALS,
        }

    def cleanup_dead_sessions(self) -> None:
        with self._lock:
            dead_sessions: list[str] = []
            for tid, session in self.sessions.items():
                if not session.is_running():
                    dead_sessions.append(tid)

            for tid in dead_sessions:
                session = self.sessions.pop(tid)
                with contextlib.suppress(Exception):
                    session.close()

    def close_all_sessions(self) -> None:
        with self._lock:
            sessions_to_close = list(self.sessions.values())
            self.sessions.clear()

        for session in sessions_to_close:
            with contextlib.suppress(Exception):
                session.close()

    def _register_cleanup_handlers(self) -> None:
        atexit.register(self.close_all_sessions)

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, self._signal_handler)

    def _signal_handler(self, _signum: int, _frame: Any) -> None:
        self.close_all_sessions()
        sys.exit(0)


_terminal_manager = TerminalManager()


def get_terminal_manager() -> TerminalManager:
    return _terminal_manager
