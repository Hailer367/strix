"""Time Tracker for Strix Sessions.

Tracks elapsed time and manages time-based warnings for the AI agent.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from strix.config import StrixConfig


logger = logging.getLogger(__name__)


@dataclass
class TimeEvent:
    """Represents a time-related event."""
    
    event_type: str  # "start", "warning", "critical", "end"
    timestamp: datetime
    message: str
    remaining_minutes: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "remaining_minutes": self.remaining_minutes,
        }


@dataclass
class TimeTracker:
    """Tracks time for a Strix session and manages warnings.
    
    This tracker monitors the elapsed time during a scan/session and
    triggers appropriate warnings when time is running low.
    """
    
    # Total duration in minutes
    duration_minutes: float = 60.0
    
    # Warning threshold in minutes before end
    warning_minutes: float = 5.0
    
    # Enable time awareness
    time_awareness_enabled: bool = True
    
    # Internal state
    start_time: datetime | None = None
    end_time: datetime | None = None
    
    # Tracking
    events: list[TimeEvent] = field(default_factory=list)
    warning_sent: bool = False
    critical_warning_sent: bool = False
    
    def start(self) -> None:
        """Start tracking time."""
        self.start_time = datetime.now()
        self.end_time = None
        self.warning_sent = False
        self.critical_warning_sent = False
        
        event = TimeEvent(
            event_type="start",
            timestamp=self.start_time,
            message=f"Session started with {self.duration_minutes} minute time limit",
            remaining_minutes=self.duration_minutes,
        )
        self.events.append(event)
        logger.info(event.message)
    
    def stop(self) -> None:
        """Stop tracking time."""
        self.end_time = datetime.now()
        elapsed = self.get_elapsed_minutes()
        
        event = TimeEvent(
            event_type="end",
            timestamp=self.end_time,
            message=f"Session ended after {elapsed:.1f} minutes",
            remaining_minutes=0,
        )
        self.events.append(event)
        logger.info(event.message)
    
    def get_elapsed_minutes(self) -> float:
        """Get elapsed time in minutes."""
        if self.start_time is None:
            return 0.0
        
        end = self.end_time or datetime.now()
        elapsed = (end - self.start_time).total_seconds() / 60.0
        return elapsed
    
    def get_remaining_minutes(self) -> float:
        """Get remaining time in minutes."""
        elapsed = self.get_elapsed_minutes()
        remaining = self.duration_minutes - elapsed
        return max(0.0, remaining)
    
    def is_expired(self) -> bool:
        """Check if time has expired."""
        return self.get_remaining_minutes() <= 0
    
    def is_warning_threshold(self) -> bool:
        """Check if we're at or past the warning threshold."""
        return self.get_remaining_minutes() <= self.warning_minutes
    
    def is_critical_threshold(self) -> bool:
        """Check if we're at or past the critical threshold (half of warning time)."""
        return self.get_remaining_minutes() <= (self.warning_minutes / 2)
    
    def get_progress_percentage(self) -> float:
        """Get progress as a percentage (0-100)."""
        if self.duration_minutes <= 0:
            return 100.0
        return min(100.0, (self.get_elapsed_minutes() / self.duration_minutes) * 100)
    
    def check_and_get_warning(self) -> str | None:
        """Check time and return a warning message if appropriate.
        
        Returns None if no warning is needed.
        """
        if not self.time_awareness_enabled:
            return None
        
        remaining = self.get_remaining_minutes()
        
        # Critical warning (final warning before time runs out)
        if self.is_critical_threshold() and not self.critical_warning_sent:
            self.critical_warning_sent = True
            message = (
                f"⚠️ CRITICAL TIME WARNING: Only {remaining:.1f} minutes remaining! "
                f"You MUST finish your current task immediately. "
                f"Call the appropriate finish tool NOW - do NOT start any new tasks."
            )
            event = TimeEvent(
                event_type="critical",
                timestamp=datetime.now(),
                message=message,
                remaining_minutes=remaining,
            )
            self.events.append(event)
            logger.warning(message)
            return message
        
        # Standard warning
        if self.is_warning_threshold() and not self.warning_sent:
            self.warning_sent = True
            message = (
                f"⏰ TIME WARNING: Approximately {remaining:.1f} minutes remaining. "
                f"Start wrapping up your current investigations. "
                f"Document your findings and prepare to finish."
            )
            event = TimeEvent(
                event_type="warning",
                timestamp=datetime.now(),
                message=message,
                remaining_minutes=remaining,
            )
            self.events.append(event)
            logger.info(message)
            return message
        
        return None
    
    def get_status_string(self) -> str:
        """Get a formatted status string for display."""
        if self.start_time is None:
            return "Not started"
        
        elapsed = self.get_elapsed_minutes()
        remaining = self.get_remaining_minutes()
        progress = self.get_progress_percentage()
        
        if self.is_expired():
            return "⏰ TIME EXPIRED"
        elif self.is_critical_threshold():
            return f"🔴 {remaining:.1f}m remaining (CRITICAL)"
        elif self.is_warning_threshold():
            return f"🟡 {remaining:.1f}m remaining (Warning)"
        else:
            return f"🟢 {remaining:.1f}m remaining ({progress:.0f}%)"
    
    def get_progress_bar(self, width: int = 20) -> str:
        """Get a text-based progress bar."""
        progress = self.get_progress_percentage() / 100.0
        filled = int(width * progress)
        empty = width - filled
        
        if self.is_critical_threshold():
            bar_char = "█"
            color_code = "red"
        elif self.is_warning_threshold():
            bar_char = "█"
            color_code = "yellow"
        else:
            bar_char = "█"
            color_code = "green"
        
        # Return with Rich markup
        filled_bar = bar_char * filled
        empty_bar = "░" * empty
        return f"[{color_code}]{filled_bar}[/{color_code}][dim]{empty_bar}[/dim]"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "duration_minutes": self.duration_minutes,
            "warning_minutes": self.warning_minutes,
            "time_awareness_enabled": self.time_awareness_enabled,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "elapsed_minutes": self.get_elapsed_minutes(),
            "remaining_minutes": self.get_remaining_minutes(),
            "progress_percentage": self.get_progress_percentage(),
            "is_expired": self.is_expired(),
            "is_warning": self.is_warning_threshold(),
            "is_critical": self.is_critical_threshold(),
            "status": self.get_status_string(),
            "events": [e.to_dict() for e in self.events],
        }
    
    @classmethod
    def from_config(cls, config: "StrixConfig") -> "TimeTracker":
        """Create a TimeTracker from StrixConfig."""
        return cls(
            duration_minutes=config.timeframe.duration_minutes,
            warning_minutes=config.timeframe.warning_minutes,
            time_awareness_enabled=config.timeframe.time_awareness_enabled,
        )
