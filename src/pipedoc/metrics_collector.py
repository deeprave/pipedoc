"""
Thread-safe metrics collection component for connection statistics.

This module provides the MetricsCollector class which handles all connection
metrics including attempts, successes, failures, timing data, and calculated
statistics like success rates and average connection times.
"""

import threading
from typing import Dict, List, Any, DefaultDict
from collections import defaultdict


class MetricsCollector:
    """
    Thread-safe metrics collection for connection statistics and monitoring.
    
    This component handles all connection metrics including attempts, successes,
    failures, timing data, and calculated statistics like success rates and
    average connection times.
    
    Thread Safety:
    --------------
    All methods are thread-safe and can be called concurrently from multiple
    threads without data corruption.
    """
    
    def __init__(self):
        """Initialise the metrics collector with empty statistics."""
        # Core metrics data
        self._connection_attempts = 0
        self._successful_connections = 0
        self._failed_connections = 0
        self._connection_times: List[float] = []
        
        # Queue metrics data
        self._connections_queued = 0
        self._connections_timeout = 0
        self._max_queue_depth = 0
        self._current_queue_depth = 0
        self._queue_wait_times: List[float] = []
        
        # Event-driven enhanced metrics
        self._events_per_type: DefaultDict[str, int] = defaultdict(int)
        self._connection_duration_histogram: DefaultDict[str, int] = defaultdict(int)
        
        # Thread safety lock
        self._metrics_lock = threading.Lock()
    
    def record_connection_attempt(self) -> None:
        """Record a connection attempt."""
        with self._metrics_lock:
            self._connection_attempts += 1
    
    def record_connection_success(self, connection_time: float = 0.0) -> None:
        """
        Record a successful connection.
        
        Args:
            connection_time: Time taken to establish the connection in seconds
        """
        with self._metrics_lock:
            self._successful_connections += 1
            if connection_time > 0:  # Only record positive connection times
                self._connection_times.append(connection_time)
    
    def record_connection_failure(self) -> None:
        """Record a failed connection."""
        with self._metrics_lock:
            self._failed_connections += 1
    
    def record_connection_queued(self) -> None:
        """Record a connection being queued."""
        with self._metrics_lock:
            self._connections_queued += 1
            self._current_queue_depth += 1
            self._max_queue_depth = max(self._max_queue_depth, self._current_queue_depth)
    
    def record_connection_dequeued(self, wait_time: float = 0.0) -> None:
        """
        Record a connection being processed from the queue.
        
        Args:
            wait_time: Time the connection spent waiting in the queue in seconds
        """
        with self._metrics_lock:
            self._current_queue_depth = max(0, self._current_queue_depth - 1)
            if wait_time > 0:  # Only record positive wait times
                self._queue_wait_times.append(wait_time)
    
    def record_connection_timeout(self) -> None:
        """Record a queued connection timing out."""
        with self._metrics_lock:
            self._connections_timeout += 1
            self._current_queue_depth = max(0, self._current_queue_depth - 1)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current connection metrics.
        
        Returns:
            Dictionary containing all current metrics and calculated statistics
        """
        with self._metrics_lock:
            # Calculate success rate
            if self._connection_attempts > 0:
                success_rate = self._successful_connections / self._connection_attempts
            else:
                success_rate = 0.0
            
            # Calculate average connection time
            if self._connection_times:
                avg_connection_time = sum(self._connection_times) / len(self._connection_times)
            else:
                avg_connection_time = 0.0
            
            # Calculate average queue wait time
            if self._queue_wait_times:
                avg_queue_wait_time = sum(self._queue_wait_times) / len(self._queue_wait_times)
            else:
                avg_queue_wait_time = 0.0
            
            # Calculate queue utilisation (percentage of max depth reached)
            if self._max_queue_depth > 0:
                queue_utilisation = 1.0  # If we have a max depth, utilisation is 100%
            else:
                queue_utilisation = 0.0
            
            return {
                # Core metrics
                'connection_attempts': self._connection_attempts,
                'successful_connections': self._successful_connections,
                'failed_connections': self._failed_connections,
                'success_rate': success_rate,
                'avg_connection_time': avg_connection_time,
                'connection_times': self._connection_times.copy(),  # Return copy to prevent mutation
                
                # Queue metrics
                'connections_queued': self._connections_queued,
                'connections_timeout': self._connections_timeout,
                'current_queue_depth': self._current_queue_depth,
                'max_queue_depth': self._max_queue_depth,
                'avg_queue_wait_time': avg_queue_wait_time,
                'queue_wait_times': self._queue_wait_times.copy(),  # Return copy to prevent mutation
                'queue_utilisation': queue_utilisation,
                
                # Enhanced event-driven metrics
                'events_per_type': dict(self._events_per_type),
                'connection_duration_histogram': dict(self._connection_duration_histogram)
            }
    
    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        with self._metrics_lock:
            self._connection_attempts = 0
            self._successful_connections = 0
            self._failed_connections = 0
            self._connection_times.clear()
            
            # Reset queue metrics
            self._connections_queued = 0
            self._connections_timeout = 0
            self._max_queue_depth = 0
            self._current_queue_depth = 0
            self._queue_wait_times.clear()
            
            # Reset event-driven metrics
            self._events_per_type.clear()
            self._connection_duration_histogram.clear()
    
    def on_event(self, event: 'ApplicationEvent') -> None:
        """
        Handle general application events - delegate to connection-specific handler if applicable.
        
        This method implements the EventListener protocol and delegates to the
        connection-specific handler for ConnectionEvent.
        
        Args:
            event: The application event to process
        """
        # Import here to avoid circular imports
        from pipedoc.connection_events import ConnectionEventType
        
        if isinstance(event, ConnectionEvent):
            self.on_connection_event(event)
    
    def on_connection_event(self, event_data: 'ConnectionEvent') -> None:
        """
        Handle connection events for enhanced metrics collection.
        
        This method implements the ConnectionEventListener protocol to collect
        enhanced metrics from connection lifecycle events.
        
        Args:
            event_data: The connection event data to process
        """
        # Import here to avoid circular imports
        from pipedoc.connection_events import ConnectionEventType
        
        with self._metrics_lock:
            # Track event types
            self._events_per_type[event_data.event_type] += 1
            
            # Handle different event types
            if event_data.connection_event_type == ConnectionEventType.CONNECT_ATTEMPT:
                self._connection_attempts += 1
                
            elif event_data.connection_event_type == ConnectionEventType.CONNECT_SUCCESS:
                self._successful_connections += 1
                
                # Record connection time if available
                if event_data.duration is not None:
                    self._connection_times.append(event_data.duration)
                    
                    # Update duration histogram
                    duration_bucket = self._get_duration_bucket(event_data.duration)
                    self._connection_duration_histogram[duration_bucket] += 1
                    
            elif event_data.connection_event_type == ConnectionEventType.CONNECT_FAILURE:
                self._failed_connections += 1
                
            elif event_data.connection_event_type == ConnectionEventType.CONNECT_QUEUED:
                self._connections_queued += 1
                self._current_queue_depth += 1
                
                # Update max queue depth from metadata if available
                if 'queue_depth' in event_data.metadata:
                    queue_depth = event_data.metadata['queue_depth']
                    self._max_queue_depth = max(self._max_queue_depth, queue_depth)
                else:
                    self._max_queue_depth = max(self._max_queue_depth, self._current_queue_depth)
                    
            elif event_data.connection_event_type == ConnectionEventType.CONNECT_DEQUEUED:
                self._current_queue_depth = max(0, self._current_queue_depth - 1)
                
                # Record wait time if available
                if 'wait_time' in event_data.metadata:
                    wait_time = event_data.metadata['wait_time']
                    self._queue_wait_times.append(wait_time)
                    
            elif event_data.connection_event_type == ConnectionEventType.CONNECT_TIMEOUT:
                self._connections_timeout += 1
                self._current_queue_depth = max(0, self._current_queue_depth - 1)
    
    def _get_duration_bucket(self, duration: float) -> str:
        """Get histogram bucket for connection duration."""
        if duration < 0.01:
            return "< 10ms"
        elif duration < 0.05:
            return "10-50ms"
        elif duration < 0.1:
            return "50-100ms"
        elif duration < 0.5:
            return "100-500ms"
        elif duration < 1.0:
            return "500ms-1s"
        else:
            return "> 1s"