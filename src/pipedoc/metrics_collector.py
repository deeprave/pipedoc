"""
Thread-safe metrics collection component for connection statistics.

This module provides the MetricsCollector class which handles all connection
metrics including attempts, successes, failures, timing data, and calculated
statistics like success rates and average connection times.
"""

import threading
from typing import Dict, List, Any


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
        """Initialize the metrics collector with empty statistics."""
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
                'connection_attempts': self._connection_attempts,
                'successful_connections': self._successful_connections,
                'failed_connections': self._failed_connections,
                'success_rate': success_rate,
                'avg_connection_time': avg_connection_time,
                'connection_times': self._connection_times.copy(),  # Return copy to prevent mutation
                'connections_queued': self._connections_queued,
                'connections_timeout': self._connections_timeout,
                'current_queue_depth': self._current_queue_depth,
                'max_queue_depth': self._max_queue_depth,
                'avg_queue_wait_time': avg_queue_wait_time,
                'queue_wait_times': self._queue_wait_times.copy(),  # Return copy to prevent mutation
                'queue_utilisation': queue_utilisation
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