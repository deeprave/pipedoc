"""
Enhanced pipe manager module for orchestrating pipe operations.

This module implements a component-based architecture where PipeManager
serves as an orchestrator that delegates to specialised components:
- PipeResource: Named pipe creation and management
- WorkerPool: Thread management and task execution
- MetricsCollector: Connection statistics and monitoring
- ConnectionManager: Race condition prevention and connection lifecycle

The refactored architecture maintains full backwards compatibility while
providing better separation of concerns, testability, and maintainability.
"""

import os
import threading
import time
from typing import Optional, List

from pipedoc.metrics_collector import MetricsCollector
from pipedoc.worker_pool import WorkerPool
from pipedoc.pipe_resource import PipeResource
from pipedoc.connection_manager import ConnectionManager
from pipedoc.connection_events import ConnectionEventManager, ConnectionEventListener
from pipedoc.event_system import StructuredLogger


class PipeManager:
    """
    Enhanced pipe manager that orchestrates specialised components.
    
    This class provides a clean public API while internally delegating operations 
    to focused, testable components that follow the Single Responsibility Principle.
    
    Architecture:
    -------------
    - PipeResource: Handles named pipe creation, monitoring, and cleanup
    - WorkerPool: Manages thread pool and task execution
    - MetricsCollector: Tracks connection statistics and performance metrics
    - ConnectionManager: Implements always-ready writer pattern for race prevention
    
    Benefits:
    ---------
    - Single Responsibility: Each component has one clear purpose
    - Testability: Components can be tested in isolation
    - Maintainability: Smaller, focused classes are easier to understand
    - Extensibility: Easy to add new features like connection queueing
    - Clean Architecture: Clear separation of concerns and dependencies
    """
    
    def __init__(self, max_workers: Optional[int] = None, thread_pool_timeout: float = 30.0,
                 queue_size: int = 10, queue_timeout: float = 30.0,
                 event_listeners: Optional[List[ConnectionEventListener]] = None):
        """
        Initialise the enhanced pipe manager with component architecture.
        
        Args:
            max_workers: Maximum number of worker threads (auto-calculated if None)
            thread_pool_timeout: Timeout for thread pool operations (for compatibility)
            queue_size: Maximum number of connections that can be queued (default: 10)
            queue_timeout: Timeout for connections waiting in queue in seconds (default: 30.0)
            event_listeners: Optional list of event listeners for connection lifecycle events
        """
        # Component initialisation
        self._metrics_collector = MetricsCollector()
        self._worker_pool = WorkerPool(max_workers=max_workers, metrics_collector=self._metrics_collector)
        self._pipe_resource = PipeResource()
        
        # Event management setup
        # Create event manager if event listeners are provided
        # To disable events completely, pass event_listeners=False
        if event_listeners is False:
            # Explicitly disable events
            self._event_manager = None
        elif event_listeners is None:
            # Default behaviour: create event manager with just metrics collector
            self._event_manager = ConnectionEventManager()
            self._event_manager.add_listener(self._metrics_collector)
            self._event_manager.start_dispatching()
        elif isinstance(event_listeners, list):
            # Event listeners provided (could be empty list)
            self._event_manager = ConnectionEventManager()
            
            # Register provided listeners
            for listener in event_listeners:
                self._event_manager.add_listener(listener)
            
            # Always register metrics collector as event listener for enhanced metrics
            self._event_manager.add_listener(self._metrics_collector)
            
            # Start async event dispatching
            self._event_manager.start_dispatching()
        else:
            # Other falsy values - disable events
            self._event_manager = None
        
        # Create connection manager with event manager
        self._connection_manager = ConnectionManager(
            worker_pool=self._worker_pool,
            metrics_collector=self._metrics_collector,
            pipe_resource=self._pipe_resource,
            queue_size=queue_size,
            queue_timeout=queue_timeout,
            event_manager=self._event_manager
        )
        
        # State management
        self._is_serving = False  # Internal state: actually serving clients
        self._current_content = ""
        self._thread_pool_timeout = thread_pool_timeout
        
        # Thread safety
        self._state_lock = threading.RLock()
        
        # Structured logging
        self._logger = StructuredLogger("PipeManager")
        
        self._logger.info("Enhanced PipeManager initialised with component architecture",
                         max_workers=max_workers,
                         queue_size=queue_size,
                         event_listeners_enabled=self._event_manager is not None)

    def create_named_pipe(self) -> str:
        """
        Create a named pipe using the PipeResource component.
        
        Returns:
            Path to the created named pipe
            
        Raises:
            OSError: If pipe creation fails
        """
        with self._state_lock:
            pipe_path = self._pipe_resource.create_pipe()
            if pipe_path:
                self._logger.info("Created named pipe", pipe_path=pipe_path)
                return pipe_path
            else:
                self._logger.error("Failed to create named pipe")
                raise OSError("Failed to create named pipe")

    def serve_client(self, client_id: int, content: str) -> None:
        """
        Serve content to a specific client.
        
        This method uses the enhanced component architecture to provide 
        reliable client serving with proper metrics tracking and error handling.
        
        Args:
            client_id: Identifier for the client connection
            content: Content to serve to the client
        """
        self._logger.debug("Client opening pipe for writing", client_id=client_id)
        start_time = time.time()
        
        # Record connection attempt through metrics
        self._metrics_collector.record_connection_attempt()
        
        try:
            pipe_path = self._pipe_resource.get_pipe_path()
            if not pipe_path:
                # Create a pipe if none exists
                pipe_path = self.create_named_pipe()
            
            # Open pipe and write content to client
            with open(pipe_path, "w") as pipe:
                connection_time = time.time() - start_time
                self._logger.debug("Client connected, sending content", 
                                 client_id=client_id, 
                                 connection_time=connection_time)
                
                # Write content to pipe (original behaviour)
                pipe.write(content)
                pipe.flush()
                
                self._metrics_collector.record_connection_success(connection_time)
                self._logger.info("Client content sent successfully", 
                                client_id=client_id,
                                content_length=len(content))
            
        except BrokenPipeError:
            self._logger.warning("Client reader disconnected", client_id=client_id)
            self._metrics_collector.record_connection_failure()
        except Exception as e:
            self._logger.error("Error serving content to client", 
                             client_id=client_id, 
                             error=str(e))
            self._metrics_collector.record_connection_failure()
            raise

    def start_serving(self, content: str) -> None:
        """
        Start accepting connections using the always-ready writer pattern.
        
        This method coordinates components to provide race-free connection handling
        through the ConnectionManager's always-ready writer implementation.
        
        Args:
            content: Content to serve to clients
        """
        with self._state_lock:
            if self._is_serving:
                return
                
            self._current_content = content
            self._is_serving = True
            
            self._logger.info("Initialising always-ready writer")
            
            # Ensure pipe is created
            if not self._pipe_resource.is_pipe_created():
                self.create_named_pipe()
            
            # Start connection management for race condition prevention
            self._connection_manager.start_connection_management()
            
            pipe_path = self._pipe_resource.get_pipe_path()
            self._logger.info("Server ready for client connections", 
                            pipe_path=pipe_path,
                            content_length=len(content))
            self._logger.info("Press Ctrl+C to stop the server")

    def stop_serving(self) -> None:
        """Stop serving clients and shutdown connection management."""
        with self._state_lock:
            if not self._is_serving:
                return
                
            self._is_serving = False
            self._connection_manager.shutdown()
            self._logger.info("Server stopped")

    def cleanup(self) -> None:
        """
        Clean up all resources across all components.
        
        This method ensures proper cleanup of:
        - Named pipes (PipeResource)
        - Thread pools (WorkerPool) 
        - Connection management (ConnectionManager)
        - Metrics collection (MetricsCollector)
        """
        with self._state_lock:
            # Stop serving if active
            if self._is_serving:
                self.stop_serving()
            
            # Shutdown components in reverse order of dependency
            self._connection_manager.shutdown()
            
            # Shutdown worker pool
            active_tasks = self._worker_pool.get_metrics().get('active_workers', 0)
            self._logger.info("Shutting down thread pool gracefully", 
                            active_tasks=active_tasks)
            self._worker_pool.shutdown(wait=True)
            self._logger.info("Thread pool shut down gracefully")
            
            # Cleanup pipe resource
            pipe_path = self._pipe_resource.get_pipe_path()
            if pipe_path:
                self._logger.info("Cleaned up pipe", pipe_path=pipe_path)
            self._pipe_resource.cleanup()
            
            # Reset metrics
            self._metrics_collector.reset_metrics()
            
            # Stop event manager if present
            if self._event_manager:
                self._event_manager.stop_dispatching()

    def get_pipe_path(self) -> Optional[str]:
        """
        Get the current pipe path using PipeResource component.
        
        Returns:
            Path to the named pipe, or None if not created
        """
        return self._pipe_resource.get_pipe_path()

    def is_running(self) -> bool:
        """
        Check if the pipe manager is currently serving clients.
        
        Returns:
            True if serving, False otherwise
        """
        with self._state_lock:
            return self._is_serving

    # Additional methods for component access (internal use)
    def _get_metrics(self) -> dict:
        """Get current connection metrics."""
        return self._metrics_collector.get_metrics()
    
    def _get_worker_pool_metrics(self) -> dict:
        """Get worker pool statistics."""
        return self._worker_pool.get_metrics()
    
    def _can_accept_connection(self) -> bool:
        """Check if new connections can be accepted."""
        return self._connection_manager.can_accept_connections()
    
    def _handle_incoming_connection(self):
        """Handle an incoming connection through ConnectionManager."""
        return self._connection_manager.handle_incoming_connection()
    
    def _get_queue_metrics(self) -> dict:
        """Get current queue metrics and statistics."""
        return self._connection_manager.get_queue_metrics()
    
    def add_event_listener(self, listener: ConnectionEventListener) -> None:
        """
        Add an event listener dynamically.
        
        Args:
            listener: The event listener to add
        """
        if self._event_manager:
            self._event_manager.add_listener(listener)
    
    def remove_event_listener(self, listener: ConnectionEventListener) -> None:
        """
        Remove an event listener dynamically.
        
        Args:
            listener: The event listener to remove
        """
        if self._event_manager:
            self._event_manager.remove_listener(listener)

