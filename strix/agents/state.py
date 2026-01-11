import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _generate_agent_id() -> str:
    return f"agent_{uuid.uuid4().hex[:8]}"


class AgentState(BaseModel):
    agent_id: str = Field(default_factory=_generate_agent_id)
    agent_name: str = "Strix Agent"
    parent_id: str | None = None
    sandbox_id: str | None = None
    sandbox_token: str | None = None
    sandbox_info: dict[str, Any] | None = None

    task: str = ""
    iteration: int = 0
    max_iterations: int = 300
    completed: bool = False
    stop_requested: bool = False
    waiting_for_input: bool = False
    llm_failed: bool = False
    waiting_start_time: datetime | None = None
    final_result: dict[str, Any] | None = None
    max_iterations_warning_sent: bool = False
    
    # Time-based tracking
    session_start_time: datetime | None = None
    session_duration_minutes: float = 60.0  # Total session duration
    time_warning_minutes: float = 5.0  # Minutes before end to warn
    time_warning_sent: bool = False
    time_critical_warning_sent: bool = False
    time_final_warning_sent: bool = False  # 1 minute warning
    time_expired_warning_sent: bool = False  # When time actually expires
    last_time_reminder_iteration: int = 0  # Track iterations for periodic reminders

    messages: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    start_time: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_updated: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    actions_taken: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)

    errors: list[str] = Field(default_factory=list)

    def increment_iteration(self) -> None:
        self.iteration += 1
        self.last_updated = datetime.now(UTC).isoformat()

    def add_message(self, role: str, content: Any) -> None:
        self.messages.append({"role": role, "content": content})
        self.last_updated = datetime.now(UTC).isoformat()

    def add_action(self, action: dict[str, Any]) -> None:
        self.actions_taken.append(
            {
                "iteration": self.iteration,
                "timestamp": datetime.now(UTC).isoformat(),
                "action": action,
            }
        )

    def add_observation(self, observation: dict[str, Any]) -> None:
        self.observations.append(
            {
                "iteration": self.iteration,
                "timestamp": datetime.now(UTC).isoformat(),
                "observation": observation,
            }
        )

    def add_error(self, error: str) -> None:
        self.errors.append(f"Iteration {self.iteration}: {error}")
        self.last_updated = datetime.now(UTC).isoformat()

    def update_context(self, key: str, value: Any) -> None:
        self.context[key] = value
        self.last_updated = datetime.now(UTC).isoformat()

    def set_completed(self, final_result: dict[str, Any] | None = None) -> None:
        self.completed = True
        self.final_result = final_result
        self.last_updated = datetime.now(UTC).isoformat()

    def request_stop(self) -> None:
        self.stop_requested = True
        self.last_updated = datetime.now(UTC).isoformat()

    def should_stop(self) -> bool:
        return self.stop_requested or self.completed or self.has_reached_max_iterations()

    def is_waiting_for_input(self) -> bool:
        return self.waiting_for_input

    def enter_waiting_state(self, llm_failed: bool = False) -> None:
        self.waiting_for_input = True
        self.waiting_start_time = datetime.now(UTC)
        self.llm_failed = llm_failed
        self.last_updated = datetime.now(UTC).isoformat()

    def resume_from_waiting(self, new_task: str | None = None) -> None:
        self.waiting_for_input = False
        self.waiting_start_time = None
        self.stop_requested = False
        self.completed = False
        self.llm_failed = False
        if new_task:
            self.task = new_task
        self.last_updated = datetime.now(UTC).isoformat()

    def has_reached_max_iterations(self) -> bool:
        return self.iteration >= self.max_iterations

    def is_approaching_max_iterations(self, threshold: float = 0.85) -> bool:
        return self.iteration >= int(self.max_iterations * threshold)
    
    def start_session_timer(self, duration_minutes: float = 60.0, warning_minutes: float = 5.0) -> None:
        """Start the session timer with specified duration and warning threshold."""
        self.session_start_time = datetime.now(UTC)
        self.session_duration_minutes = duration_minutes
        self.time_warning_minutes = warning_minutes
        self.time_warning_sent = False
        self.time_critical_warning_sent = False
        self.time_final_warning_sent = False
        self.time_expired_warning_sent = False
        self.last_time_reminder_iteration = 0
        self.last_updated = datetime.now(UTC).isoformat()
    
    def get_elapsed_session_minutes(self) -> float:
        """Get elapsed time in minutes since session start."""
        if self.session_start_time is None:
            return 0.0
        elapsed = (datetime.now(UTC) - self.session_start_time).total_seconds() / 60.0
        return elapsed
    
    def get_remaining_session_minutes(self) -> float:
        """Get remaining time in minutes."""
        elapsed = self.get_elapsed_session_minutes()
        remaining = self.session_duration_minutes - elapsed
        return max(0.0, remaining)
    
    def is_session_expired(self) -> bool:
        """Check if the session time has expired."""
        return self.get_remaining_session_minutes() <= 0
    
    def is_time_warning_threshold(self) -> bool:
        """Check if we're at or past the warning threshold."""
        return self.get_remaining_session_minutes() <= self.time_warning_minutes
    
    def is_time_critical_threshold(self) -> bool:
        """Check if we're at or past the critical threshold (half of warning time)."""
        return self.get_remaining_session_minutes() <= (self.time_warning_minutes / 2)
    
    def get_time_warning_message(self) -> str | None:
        """Get a time warning message if appropriate.
        
        Returns None if no warning is needed.
        This method provides multiple warning levels:
        1. Standard warning at warning_minutes threshold
        2. Critical warning at half of warning_minutes
        3. Final warning at 1 minute remaining
        4. Expired warning when time is up
        5. Periodic reminders every 5 iterations after warning threshold
        """
        if self.session_start_time is None:
            return None
        
        remaining = self.get_remaining_session_minutes()
        elapsed = self.get_elapsed_session_minutes()
        
        # Time expired - highest priority
        if remaining <= 0 and not self.time_expired_warning_sent:
            self.time_expired_warning_sent = True
            return (
                f"🚨 TIME EXPIRED: Your allocated session time of {self.session_duration_minutes:.0f} minutes "
                f"has been COMPLETELY EXHAUSTED (elapsed: {elapsed:.1f} minutes). "
                f"You MUST call the finish_scan tool IMMEDIATELY with your findings. "
                f"The session will be forcefully terminated. DO NOT make any other tool calls."
            )
        
        # Final warning at 1 minute
        if remaining <= 1.0 and not self.time_final_warning_sent:
            self.time_final_warning_sent = True
            return (
                f"🔴 FINAL TIME WARNING: Less than 1 minute remaining ({remaining:.1f} minutes)! "
                f"This is your FINAL warning. You MUST call finish_scan NOW. "
                f"Your session will be forcefully terminated when time expires. "
                f"Stop all other activities and finish immediately."
            )
        
        # Critical warning at half of warning threshold
        if self.is_time_critical_threshold() and not self.time_critical_warning_sent:
            self.time_critical_warning_sent = True
            return (
                f"⚠️ CRITICAL TIME WARNING: Only {remaining:.1f} minutes remaining! "
                f"You MUST finish your current task immediately. "
                f"Call the finish_scan tool NOW - do NOT start any new tasks. "
                f"Document any findings quickly and wrap up. Time is almost up!"
            )
        
        # Standard warning at warning threshold
        if self.is_time_warning_threshold() and not self.time_warning_sent:
            self.time_warning_sent = True
            return (
                f"⏰ TIME WARNING: Approximately {remaining:.1f} minutes remaining in this session. "
                f"You have {self.session_duration_minutes:.0f} minutes total and have used {elapsed:.1f} minutes. "
                f"Start wrapping up your current investigations NOW. "
                f"Focus on documenting your findings and preparing to call finish_scan. "
                f"Do NOT start any new long-running scans or investigations."
            )
        
        # Periodic reminder every 5 iterations after warning threshold (but only if time is running low)
        if self.is_time_warning_threshold() and remaining > 0:
            iterations_since_last_reminder = self.iteration - self.last_time_reminder_iteration
            if iterations_since_last_reminder >= 5:
                self.last_time_reminder_iteration = self.iteration
                return (
                    f"⏱️ TIME REMINDER: {remaining:.1f} minutes remaining. "
                    f"Progress: {elapsed:.1f}/{self.session_duration_minutes:.0f} minutes used. "
                    f"You should be finishing up. Call finish_scan soon."
                )
        
        return None

    def has_waiting_timeout(self) -> bool:
        if not self.waiting_for_input or not self.waiting_start_time:
            return False

        if (
            self.stop_requested
            or self.llm_failed
            or self.completed
            or self.has_reached_max_iterations()
        ):
            return False

        elapsed = (datetime.now(UTC) - self.waiting_start_time).total_seconds()
        return elapsed > 600

    def has_empty_last_messages(self, count: int = 3) -> bool:
        if len(self.messages) < count:
            return False

        last_messages = self.messages[-count:]

        for message in last_messages:
            content = message.get("content", "")
            if isinstance(content, str) and content.strip():
                return False

        return True

    def get_conversation_history(self) -> list[dict[str, Any]]:
        return self.messages

    def get_execution_summary(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "parent_id": self.parent_id,
            "sandbox_id": self.sandbox_id,
            "sandbox_info": self.sandbox_info,
            "task": self.task,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "completed": self.completed,
            "final_result": self.final_result,
            "start_time": self.start_time,
            "last_updated": self.last_updated,
            "total_actions": len(self.actions_taken),
            "total_observations": len(self.observations),
            "total_errors": len(self.errors),
            "has_errors": len(self.errors) > 0,
            "max_iterations_reached": self.has_reached_max_iterations() and not self.completed,
        }
