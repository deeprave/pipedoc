"""
General-purpose event system for structured logging and event handling.

This module provides a general event system that can be used throughout the
application for structured logging, monitoring, and event-driven architecture.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Import app_logger to avoid circular dependency when importing at module level
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipedoc.app_logger import AppLogger


class EventLevel(Enum):
    """Standard event levels for application events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Event:
    """Base class for all application events."""

    def __init__(
        self,
        event_type: str,
        timestamp: float,
        component: str,
        message: str,
        level: EventLevel = EventLevel.INFO,
        metadata: Optional[Dict[str, Any]] = None,
        **additional_attributes,
    ):
        """
        Initialise Event with optional additional attributes.

        Args:
            event_type: Type of the event
            timestamp: When the event occurred
            component: Component that generated the event
            message: Human-readable message
            level: Event level
            metadata: Additional metadata dictionary
            **additional_attributes: Any additional attributes to set on the event
        """
        # Set the core attributes
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "component", component)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "level", level)
        object.__setattr__(self, "metadata", metadata or {})

        # Set any additional attributes passed as kwargs
        for attr_name, attr_value in additional_attributes.items():
            object.__setattr__(self, attr_name, attr_value)

    def __setattr__(self, name, value):
        """Prevent modification after initialisation (frozen behaviour)."""
        raise AttributeError(f"can't set attribute '{name}'")


@runtime_checkable
class EventListener(Protocol):
    """Protocol for general event listeners."""

    def on_event(self, event: Event) -> None:
        """Handle an application event."""
        ...


class EventManager:
    """General-purpose event manager for application-wide events."""

    def __init__(self, logger: Optional["AppLogger"] = None):
        """Initialise the event manager.

        Args:
            logger: Application logger for error reporting (uses Python logging if None)
        """
        self._listeners: List[EventListener] = []
        self._python_logger = logging.getLogger("pipedoc.events")
        self._app_logger = logger

    def add_listener(self, listener: EventListener) -> None:
        """Add an event listener."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: EventListener) -> None:
        """Remove an event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit(self, event: Event) -> None:
        """Emit an event to all listeners."""
        # Log the event by default using Python logger
        log_method = getattr(self._python_logger, event.level.value)
        log_message = f"[{event.component}] {event.event_type}: {event.message}"
        if event.metadata:
            metadata_str = ", ".join(f"{k}={v}" for k, v in event.metadata.items())
            log_message += f" [{metadata_str}]"
        log_method(log_message)

        # Dispatch to listeners with error isolation
        for listener in self._listeners:
            try:
                listener.on_event(event)
            except Exception as e:
                # Isolate listener errors - use app logger if available, otherwise Python logger
                if self._app_logger:
                    from pipedoc.app_logger import LogContext

                    context = LogContext(component="EventManager", operation="emit")
                    self._app_logger.error(
                        f"Error in event listener {listener.__class__.__name__}: {e}",
                        context=context,
                        exc_info=True,
                        event_type=event.event_type,
                    )
                else:
                    self._python_logger.error(
                        f"Error in event listener {listener.__class__.__name__}: {e}",
                        exc_info=True,
                    )
                continue

    def create_event(
        self,
        event_type: str,
        component: str,
        message: str,
        level: EventLevel = EventLevel.INFO,
        **metadata,
    ) -> Event:
        """Create and emit an event."""
        event = Event(
            event_type=event_type,
            timestamp=time.time(),
            component=component,
            message=message,
            level=level,
            metadata=metadata,
        )
        self.emit(event)
        return event


# Global event manager instance
event_manager = EventManager()


# Convenience functions for common event types
def log_info(component: str, message: str, **metadata):
    """Log an info event."""
    return event_manager.create_event(
        "log", component, message, EventLevel.INFO, **metadata
    )


def log_warning(component: str, message: str, **metadata):
    """Log a warning event."""
    return event_manager.create_event(
        "log", component, message, EventLevel.WARNING, **metadata
    )


def log_error(component: str, message: str, **metadata):
    """Log an error event."""
    return event_manager.create_event(
        "log", component, message, EventLevel.ERROR, **metadata
    )


def log_debug(component: str, message: str, **metadata):
    """Log a debug event."""
    return event_manager.create_event(
        "log", component, message, EventLevel.DEBUG, **metadata
    )


class StructuredLogger:
    """Structured logger that replaces print statements with proper events."""

    def __init__(self, component: str, event_mgr: Optional[EventManager] = None):
        """
        Initialise structured logger for a component.

        Args:
            component: Name of the component using this logger
            event_mgr: Event manager to use (defaults to global instance)
        """
        self.component = component
        self.event_manager = event_mgr or event_manager

    def info(self, message: str, **metadata):
        """Log info message."""
        self.event_manager.create_event(
            "info", self.component, message, EventLevel.INFO, **metadata
        )

    def warning(self, message: str, **metadata):
        """Log warning message."""
        self.event_manager.create_event(
            "warning", self.component, message, EventLevel.WARNING, **metadata
        )

    def error(self, message: str, **metadata):
        """Log error message."""
        self.event_manager.create_event(
            "error", self.component, message, EventLevel.ERROR, **metadata
        )

    def debug(self, message: str, **metadata):
        """Log debug message."""
        self.event_manager.create_event(
            "debug", self.component, message, EventLevel.DEBUG, **metadata
        )

    def critical(self, message: str, **metadata):
        """Log critical message."""
        self.event_manager.create_event(
            "critical", self.component, message, EventLevel.CRITICAL, **metadata
        )
