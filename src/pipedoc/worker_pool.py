"""
Enhanced worker pool component for thread management.

This module provides the WorkerPool class which wraps ThreadPoolExecutor
with additional functionality including capacity management, overload protection,
metrics integration, and enhanced error handling.
"""

import threading
import os
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future

from .metrics_collector import MetricsCollector


class WorkerPool:
    """
    Enhanced worker pool that wraps ThreadPoolExecutor with additional functionality.
    
    This component provides capacity management, overload protection, metrics integration,
    and enhanced error handling for worker thread management.
    
    Key Features:
    -------------
    - Capacity management and overload detection
    - Optional metrics integration with MetricsCollector
    - Enhanced error handling and recovery
    - Graceful shutdown with proper resource cleanup
    """
    
    def __init__(self, max_workers: Optional[int] = None, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize the worker pool.
        
        Args:
            max_workers: Maximum number of worker threads. If None, defaults to min(32, CPU count + 4)
            metrics_collector: Optional MetricsCollector for integration
        """
        # Configure worker count
        if max_workers is None:
            max_workers = min(32, (os.cpu_count() or 1) + 4)
        
        self._max_workers = max_workers
        self._metrics_collector = metrics_collector
        
        # Initialize thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="enhanced-worker"
        )
        
        # Track active futures and state
        self._active_futures: set = set()
        self._futures_lock = threading.Lock()
        self._running = True
        
    def submit_task(self, fn: Callable, *args, **kwargs) -> Optional[Future]:
        """
        Submit a task to the worker pool.
        
        Args:
            fn: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Future object representing the task execution, or None if pool is shutdown
        """
        if not self._running:
            return None
            
        try:
            # Submit task to executor
            future = self._executor.submit(fn, *args, **kwargs)
            
            # Track the future
            with self._futures_lock:
                self._active_futures.add(future)
            
            # Add completion callback to clean up tracking
            future.add_done_callback(self._task_completed_callback)
            
            return future
            
        except Exception as e:
            # Handle submission failures (e.g., pool shutdown)
            return None
    
    def _task_completed_callback(self, future: Future) -> None:
        """Callback invoked when a task completes."""
        with self._futures_lock:
            self._active_futures.discard(future)
    
    def is_running(self) -> bool:
        """Check if the worker pool is running."""
        return self._running
    
    def get_capacity(self) -> int:
        """Get the maximum worker capacity."""
        return self._max_workers
    
    def get_active_count(self) -> int:
        """Get the number of active workers."""
        with self._futures_lock:
            return len(self._active_futures)
    
    def can_accept_task(self) -> bool:
        """Check if the pool can accept new tasks."""
        return self._running and self.get_active_count() < self._max_workers
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current worker pool metrics.
        
        Returns:
            Dictionary containing pool statistics
        """
        with self._futures_lock:
            return {
                'max_workers': self._max_workers,
                'active_workers': len(self._active_futures),
                'is_running': self._running,
                'utilization': len(self._active_futures) / self._max_workers
            }
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Shut down the worker pool.
        
        Args:
            wait: Whether to wait for active tasks to complete
        """
        self._running = False
        
        try:
            self._executor.shutdown(wait=wait)
        finally:
            # Clear tracking
            with self._futures_lock:
                self._active_futures.clear()