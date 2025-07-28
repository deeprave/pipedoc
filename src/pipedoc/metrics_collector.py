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
            
            return {
                'connection_attempts': self._connection_attempts,
                'successful_connections': self._successful_connections,
                'failed_connections': self._failed_connections,
                'success_rate': success_rate,
                'avg_connection_time': avg_connection_time,
                'connection_times': self._connection_times.copy()  # Return copy to prevent mutation
            }
    
    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        with self._metrics_lock:
            self._connection_attempts = 0
            self._successful_connections = 0
            self._failed_connections = 0
            self._connection_times.clear()