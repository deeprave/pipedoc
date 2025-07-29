"""
Connection event system for lifecycle monitoring.

This module provides event data structures and management for connection
lifecycle events including connect, disconnect, queue, and error events.
"""

import threading
import time
import queue
from enum import Enum
from typing import List, Optional, Dict, Any, Protocol, runtime_checkable
from concurrent.futures import ThreadPoolExecutor

from pipedoc.event_system import ApplicationEvent, EventListener, EventLevel


class ConnectionEventType(Enum):
    """Connection lifecycle event types."""
    CONNECT_ATTEMPT = "connect_attempt"
    CONNECT_SUCCESS = "connect_success"
    CONNECT_FAILURE = "connect_failure"
    CONNECT_QUEUED = "connect_queued"
    CONNECT_DEQUEUED = "connect_dequeued"
    CONNECT_TIMEOUT = "connect_timeout"
    DISCONNECT = "disconnect"


class ConnectionEvent(ApplicationEvent):
    """Connection lifecycle event, inheriting from ApplicationEvent."""
    
    def __init__(self, event_type: ConnectionEventType, connection_id: str, timestamp: float, 
                 duration: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None):
        """Initialise connection event."""
        # Map connection events to appropriate levels
        level_mapping = {
            ConnectionEventType.CONNECT_FAILURE: EventLevel.WARNING,
            ConnectionEventType.CONNECT_TIMEOUT: EventLevel.WARNING,
            ConnectionEventType.CONNECT_QUEUED: EventLevel.DEBUG,
            ConnectionEventType.CONNECT_DEQUEUED: EventLevel.DEBUG,
        }
        level = level_mapping.get(event_type, EventLevel.INFO)
        
        # Call parent constructor with connection-specific attributes as additional kwargs
        super().__init__(
            event_type=event_type.value,
            timestamp=timestamp,
            component="ConnectionManager",
            message=f"Connection {connection_id}: {event_type.value}",
            level=level,
            metadata=metadata or {},
            # Connection-specific attributes passed as kwargs
            connection_event_type=event_type,
            connection_id=connection_id,
            duration=duration
        )


@runtime_checkable
class ConnectionEventListener(EventListener, Protocol):
    """Protocol for connection event listeners, specialised from EventListener."""
    
    def on_connection_event(self, event_data: 'ConnectionEvent') -> None:
        """Handle a connection event.
        
        Args:
            event_data: The connection event data
        """
        ...
    
    def on_event(self, event: ApplicationEvent) -> None:
        """Handle general application event - delegate to connection-specific handler if applicable."""
        if isinstance(event, ConnectionEvent):
            self.on_connection_event(event)
        # Can be extended to handle other event types


class ConnectionEventManager:
    """Manages connection event listeners and dispatching."""
    
    def __init__(self):
        """Initialise the event manager."""
        self._listeners: List[ConnectionEventListener] = []
        self._event_queue: queue.Queue = queue.Queue()
        self._running = False
        self._dispatcher_executor: Optional[ThreadPoolExecutor] = None
        self._lock = threading.Lock()
    
    def add_listener(self, listener: ConnectionEventListener) -> None:
        """Add an event listener.
        
        Args:
            listener: The event listener to add
        """
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)
    
    def remove_listener(self, listener: ConnectionEventListener) -> None:
        """Remove an event listener.
        
        Args:
            listener: The event listener to remove
        """
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
    
    def get_listener_count(self) -> int:
        """Get the number of registered listeners.
        
        Returns:
            Number of registered listeners
        """
        with self._lock:
            return len(self._listeners)
    
    def is_running(self) -> bool:
        """Check if async dispatching is running.
        
        Returns:
            True if async dispatching is active
        """
        return self._running
    
    def start_dispatching(self) -> None:
        """Start async event dispatching."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._dispatcher_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="event-dispatcher"
            )
            self._dispatcher_executor.submit(self._dispatch_events)
    
    def stop_dispatching(self) -> None:
        """Stop async event dispatching."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Signal dispatcher to stop
            self._event_queue.put(None)
            
            if self._dispatcher_executor:
                self._dispatcher_executor.shutdown(wait=True)
                self._dispatcher_executor = None
    
    def emit_event(self, event_data: 'ConnectionEvent') -> None:
        """Emit an event to all listeners.
        
        Args:
            event_data: The event data to emit
        """
        if self._running:
            # Async dispatching - add to queue
            self._event_queue.put(event_data)
        else:
            # Sync dispatching - dispatch immediately
            self._dispatch_to_listeners(event_data)
    
    def _dispatch_events(self) -> None:
        """Background event dispatcher worker."""
        while self._running:
            try:
                # Wait for event with timeout
                event_data = self._event_queue.get(timeout=1.0)
                
                # Check for shutdown signal
                if event_data is None:
                    break
                
                # Dispatch to listeners
                self._dispatch_to_listeners(event_data)
                
            except queue.Empty:
                # Timeout waiting for events - continue
                continue
            except Exception:
                # Error in event dispatching - continue to prevent thread death
                continue
    
    def _dispatch_to_listeners(self, event_data: 'ConnectionEvent') -> None:
        """Dispatch event to all listeners with error isolation.
        
        Args:
            event_data: The event data to dispatch
        """
        # Get current listeners under lock
        with self._lock:
            current_listeners = self._listeners.copy()
        
        # Dispatch to each listener with error isolation
        for listener in current_listeners:
            try:
                listener.on_connection_event(event_data)
            except Exception:
                # Isolate listener errors - don't let them affect other listeners
                # In production, this might log the error
                continue