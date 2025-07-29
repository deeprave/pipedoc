"""
Built-in connection event handlers for common event processing needs.

This module provides ready-to-use event handlers for logging, file output,
statistics collection, and other common event processing requirements.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List, Callable, Union
from collections import defaultdict

from pipedoc.connection_events import ConnectionEventListener, ConnectionEvent, ConnectionEventType


class EventHandlerChain:
    """Chain of event handlers that processes events through multiple handlers."""
    
    def __init__(self, handlers: Optional[List[ConnectionEventListener]] = None):
        """
        Initialise event handler chain.
        
        Args:
            handlers: List of event handlers to chain together
        """
        self._handlers = handlers or []
    
    def add_handler(self, handler: ConnectionEventListener) -> 'EventHandlerChain':
        """Add a handler to the chain (fluent interface)."""
        self._handlers.append(handler)
        return self
    
    def remove_handler(self, handler: ConnectionEventListener) -> bool:
        """Remove a handler from the chain."""
        try:
            self._handlers.remove(handler)
            return True
        except ValueError:
            return False
    
    def on_connection_event(self, event_data: ConnectionEvent) -> None:
        """Process event through all handlers in the chain."""
        for handler in self._handlers:
            try:
                handler.on_connection_event(event_data)
            except Exception:
                # Isolate handler errors - continue with other handlers
                continue
    
    def get_handler_count(self) -> int:
        """Get number of handlers in the chain."""
        return len(self._handlers)


class FilteringEventHandler:
    """Event handler that filters events before passing to another handler."""
    
    def __init__(self, 
                 target_handler: ConnectionEventListener,
                 event_filter: Callable[[ConnectionEvent], bool]):
        """
        Initialise filtering event handler.
        
        Args:
            target_handler: The handler to pass filtered events to
            event_filter: Function that returns True if event should be processed
        """
        self._target_handler = target_handler
        self._event_filter = event_filter
    
    def on_connection_event(self, event_data: ConnectionEvent) -> None:
        """Filter and conditionally process the event."""
        if self._event_filter(event_data):
            self._target_handler.on_connection_event(event_data)


class LoggingEventHandler:
    """Event handler that logs connection events using Python's logging system."""
    
    def __init__(self, 
                 logger_name: str = "pipedoc.events",
                 format_type: str = "text",
                 level_mapper: Optional[Callable[[ConnectionEventType], str]] = None):
        """
        Initialise the logging event handler.
        
        Args:
            logger_name: Name of the logger to use for event logging
            format_type: Format for log messages ("text" or "json")
            level_mapper: Function to map event types to log levels
        """
        self._logger = logging.getLogger(logger_name)
        self._format_type = format_type
        self._level_mapper = level_mapper or self._default_level_mapper
    
    def _default_level_mapper(self, event_type: ConnectionEventType) -> str:
        """Default mapping of event types to log levels."""
        if event_type in [ConnectionEventType.CONNECT_FAILURE, ConnectionEventType.CONNECT_TIMEOUT]:
            return "warning"
        elif event_type in [ConnectionEventType.CONNECT_QUEUED, ConnectionEventType.CONNECT_DEQUEUED]:
            return "debug"
        else:
            return "info"
    
    def on_connection_event(self, event_data: ConnectionEvent) -> None:
        """
        Handle a connection event by logging it.
        
        Args:
            event_data: The connection event data to log
        """
        # Determine log level
        level = self._level_mapper(event_data.connection_event_type)
        log_method = getattr(self._logger, level)
        
        if self._format_type == "json":
            # JSON format
            log_data = {
                "event_type": event_data.event_type,
                "connection_id": event_data.connection_id,
                "timestamp": event_data.timestamp,
                "duration": event_data.duration,
                "metadata": event_data.metadata or {}
            }
            log_method(json.dumps(log_data))
        else:
            # Text format
            message = f"Connection {event_data.connection_id}: {event_data.event_type}"
            
            # Add duration if available
            if event_data.duration is not None:
                message += f" (duration: {event_data.duration:.3f}s)"
            
            # Add metadata if available
            if event_data.metadata:
                metadata_str = ", ".join(f"{k}={v}" for k, v in event_data.metadata.items())
                message += f" [{metadata_str}]"
            
            log_method(message)


class FileEventHandler:
    """Event handler that writes connection events to a file."""
    
    def __init__(self, file_path: str, format: str = "text"):
        """
        Initialise the file event handler.
        
        Args:
            file_path: Path to the file where events should be written
            format: Format for event output ("text" or "json")
        """
        self._file_path = file_path
        self._format = format
        self._file = open(file_path, 'a', encoding='utf-8')
    
    def on_connection_event(self, event_data: ConnectionEvent) -> None:
        """
        Handle a connection event by writing it to file.
        
        Args:
            event_data: The connection event data to write
        """
        if self._format == "json":
            # JSON format
            event_dict = {
                "event_type": event_data.event_type,
                "connection_id": event_data.connection_id,
                "timestamp": event_data.timestamp,
                "duration": event_data.duration,
                "metadata": event_data.metadata or {}
            }
            line = json.dumps(event_dict) + "\n"
        else:
            # Text format
            timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event_data.timestamp))
            line = f"[{timestamp_str}] {event_data.event_type} {event_data.connection_id}"
            
            if event_data.duration is not None:
                line += f" duration={event_data.duration:.3f}s"
            
            if event_data.metadata:
                metadata_str = " ".join(f"{k}={v}" for k, v in event_data.metadata.items())
                line += f" {metadata_str}"
            
            line += "\n"
        
        self._file.write(line)
        self._file.flush()
    
    def cleanup(self) -> None:
        """Close the file handle."""
        if hasattr(self, '_file') and not self._file.closed:
            self._file.close()


class StatisticsEventHandler:
    """Event handler that collects statistics about connection events."""
    
    def __init__(self):
        """Initialise the statistics event handler."""
        self.reset_statistics()
    
    def on_connection_event(self, event_data: ConnectionEvent) -> None:
        """
        Handle a connection event by updating statistics.
        
        Args:
            event_data: The connection event data to process
        """
        # Update counters based on event type
        if event_data.connection_event_type == ConnectionEventType.CONNECT_ATTEMPT:
            self._total_attempts += 1
        elif event_data.connection_event_type == ConnectionEventType.CONNECT_SUCCESS:
            self._total_successes += 1
            
            # Track duration statistics
            if event_data.duration is not None:
                self._durations.append(event_data.duration)
                
        elif event_data.connection_event_type == ConnectionEventType.CONNECT_FAILURE:
            self._total_failures += 1
        elif event_data.connection_event_type == ConnectionEventType.CONNECT_QUEUED:
            self._total_queued += 1
        elif event_data.connection_event_type == ConnectionEventType.CONNECT_TIMEOUT:
            self._total_timeouts += 1
        
        # Track event type frequency
        self._event_counts[event_data.event_type] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current statistics.
        
        Returns:
            Dictionary containing connection statistics
        """
        # Calculate success rate
        if self._total_attempts > 0:
            success_rate = self._total_successes / self._total_attempts
        else:
            success_rate = 0.0
        
        # Calculate duration statistics
        if self._durations:
            avg_duration = sum(self._durations) / len(self._durations)
            min_duration = min(self._durations)
            max_duration = max(self._durations)
        else:
            avg_duration = 0.0
            min_duration = 0.0
            max_duration = 0.0
        
        return {
            'total_attempts': self._total_attempts,
            'total_successes': self._total_successes,
            'total_failures': self._total_failures,
            'total_queued': self._total_queued,
            'total_timeouts': self._total_timeouts,
            'success_rate': success_rate,
            'avg_duration': avg_duration,
            'min_duration': min_duration,
            'max_duration': max_duration,
            'event_counts': dict(self._event_counts),
            'total_events': sum(self._event_counts.values())
        }
    
    def reset_statistics(self) -> None:
        """Reset all statistics to initial state."""
        self._total_attempts = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_queued = 0
        self._total_timeouts = 0
        self._durations: List[float] = []
        self._event_counts: Dict[str, int] = defaultdict(int)