"""
Connection lifecycle management component.

This module provides the ConnectionManager class which implements the always-ready
writer pattern for race condition prevention, manages connection lifecycles, and
integrates with WorkerPool, MetricsCollector, and PipeResource components.
"""

import threading
import time
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pipedoc.app_logger import AppLogger
from concurrent.futures import Future
from queue import Queue, Empty, Full
from dataclasses import dataclass

from pipedoc.worker_pool import WorkerPool
from pipedoc.metrics_collector import MetricsCollector
from pipedoc.pipe_resource import PipeResource


@dataclass
class QueuedConnection:
    """Represents a connection waiting in the queue."""

    connection_id: str
    timestamp: float
    timeout_future: Future


class ConnectionManager:
    """
    Manages connection lifecycle with race condition prevention.

    This component implements the always-ready writer pattern to prevent race
    conditions during connection handling. It coordinates with WorkerPool for
    task execution, MetricsCollector for statistics, and PipeResource for
    pipe operations.

    Key Features:
    -------------
    - Always-ready writer pattern for race condition prevention
    - Proactive writer replacement for continuous availability
    - Connection lifecycle tracking and management
    - Integration with worker pool and metrics collection
    - Thread-safe operations
    """

    def __init__(
        self,
        worker_pool: WorkerPool,
        metrics_collector: MetricsCollector,
        pipe_resource: PipeResource,
        queue_size: int = 10,
        queue_timeout: float = 30.0,
        event_manager: Optional["ConnectionEventManager"] = None,
        content_callback: Optional[callable] = None,
        logger: Optional["AppLogger"] = None,
    ):
        """
        Initialise the connection manager with required components.

        Args:
            worker_pool: WorkerPool instance for task execution
            metrics_collector: MetricsCollector for connection statistics
            pipe_resource: PipeResource for named pipe operations
            queue_size: Maximum number of connections that can be queued (default: 10)
            queue_timeout: Timeout for connections waiting in queue in seconds (default: 30.0)
            event_manager: Optional ConnectionEventManager for lifecycle events
            content_callback: Optional callback to get content to serve
        """
        self._worker_pool = worker_pool
        self._metrics_collector = metrics_collector
        self._pipe_resource = pipe_resource
        self._event_manager = event_manager
        self._content_callback = content_callback

        # Logging setup
        from pipedoc.app_logger import LogContext

        if logger:
            self._logger = logger
            self._context = LogContext(component="ConnectionManager")
        else:
            from pipedoc.app_logger import get_default_logger

            self._logger = get_default_logger()
            self._context = LogContext(component="ConnectionManager")

        # Queue configuration
        self._queue_size = queue_size
        self._queue_timeout = queue_timeout

        # Connection management state
        self._is_running = False
        self._writer_ready = False
        self._active_connections = 0
        self._current_writer_future: Optional[Future] = None

        # Connection queue
        self._connection_queue: Queue = Queue(maxsize=queue_size)
        self._queue_processor_running = False
        self._queue_processor_future: Optional[Future] = None
        self._connection_id_counter = 0

        # Thread safety - use RLock to allow reentrant locking
        self._state_lock = threading.RLock()
        self._connection_lock = threading.Lock()
        self._queue_lock = threading.Lock()

        # Separate lock for connection counter to avoid callback deadlock
        # See: ThreadPoolExecutor deadlock when future.result() waits while
        # callback competes for the same lock (thread starvation)
        self._counter_lock = threading.Lock()

        # Writer management
        self._writer_id_counter = 0

    def _emit_event(
        self,
        event_type: "ConnectionEvent",
        connection_id: str,
        duration: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a connection event if event manager is available.

        Args:
            event_type: The type of connection event
            connection_id: Unique identifier for the connection
            duration: Optional duration for the event
            metadata: Optional additional event data
        """
        if self._event_manager:
            # Import here to avoid circular imports
            from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

            event_data = ConnectionEvent(
                event_type=event_type,
                connection_id=connection_id,
                timestamp=time.time(),
                duration=duration,
                metadata=metadata or {},
            )
            self._event_manager.emit_event(event_data)

    def start_connection_management(self) -> None:
        """Start connection management with always-ready writer pattern."""
        with self._state_lock:
            if self._is_running:
                return

            from pipedoc.app_logger import LogContext

            self._logger.info(
                "Starting connection management",
                context=LogContext(
                    component=self._context.component,
                    operation="start_connection_management",
                ),
                queue_size=self._queue_size,
                queue_timeout=self._queue_timeout,
            )
            self._is_running = True
            self._prepare_ready_writer()

    def shutdown(self) -> None:
        """Shutdown connection management and cleanup resources."""
        with self._state_lock:
            if not self._is_running:
                return

            from pipedoc.app_logger import LogContext

            self._logger.info(
                "Shutting down connection management",
                context=LogContext(
                    component=self._context.component, operation="shutdown"
                ),
                active_connections=self._active_connections,
                queue_depth=self._connection_queue.qsize(),
            )
            self._is_running = False
            self._writer_ready = False

            # Stop queue processor
            self._queue_processor_running = False
            if self._queue_processor_future and not self._queue_processor_future.done():
                self._queue_processor_future.cancel()

            # Cancel current writer if exists
            if self._current_writer_future and not self._current_writer_future.done():
                self._current_writer_future.cancel()

            self._current_writer_future = None

            # Clear the queue with timeout exceptions
            while not self._connection_queue.empty():
                try:
                    queued_conn = self._connection_queue.get_nowait()
                    if not queued_conn.timeout_future.done():
                        queued_conn.timeout_future.set_exception(
                            RuntimeError("Connection manager shutting down")
                        )
                except Empty:
                    break

    def is_running(self) -> bool:
        """Check if connection management is currently running."""
        with self._state_lock:
            return self._is_running

    def is_writer_ready(self) -> bool:
        """Check if a writer is ready to handle incoming connections."""
        with self._state_lock:
            return self._writer_ready and self._is_running

    def get_active_connections(self) -> int:
        """Get the current count of active connections."""
        with self._connection_lock:
            return self._active_connections

    def can_accept_connections(self) -> bool:
        """Check if the manager can accept new connections."""
        return (
            self.is_running()
            and self.is_writer_ready()
            and self._worker_pool.can_accept_task()
        )

    def handle_incoming_connection(self) -> Optional[Future]:
        """
        Handle an incoming connection with queueing support.

        Returns:
            Future for the connection handling task, or None if cannot accept (queue full)
        """
        # Generate connection ID for event tracking
        with self._queue_lock:
            self._connection_id_counter += 1
            connection_id = f"conn_{self._connection_id_counter}"

        # Log and emit connection attempt event
        from pipedoc.connection_events import ConnectionEventType
        from pipedoc.app_logger import LogContext

        self._logger.debug(
            "Incoming connection attempt",
            context=LogContext(
                component=self._context.component,
                operation="handle_incoming_connection",
            ),
            connection_id=connection_id,
            queue_depth=self._connection_queue.qsize(),
            can_accept=self.can_accept_connections(),
        )

        self._emit_event(
            ConnectionEventType.CONNECT_ATTEMPT,
            connection_id,
            metadata={"queue_depth": self._connection_queue.qsize()},
        )

        # Record connection attempt
        self._metrics_collector.record_connection_attempt()

        # Try immediate processing first if worker pool has capacity
        if self.can_accept_connections():
            return self._process_connection_immediately(connection_id)

        # If worker pool is busy, try to queue the connection
        return self._queue_connection(connection_id)

    def _process_connection_immediately(self, connection_id: str) -> Optional[Future]:
        """Process a connection immediately without queueing."""
        connection_future = None

        with self._connection_lock:
            try:
                # Submit connection handling task with connection_id
                connection_future = self._worker_pool.submit_task(
                    lambda: self._handle_connection_worker(connection_id)
                )

                if connection_future:
                    self._active_connections += 1

                    # Log successful connection acceptance
                    from pipedoc.app_logger import LogContext

                    self._logger.info(
                        "Connection accepted for immediate processing",
                        context=LogContext(
                            component=self._context.component,
                            operation="_process_connection_immediately",
                        ),
                        connection_id=connection_id,
                        active_connections=self._active_connections,
                    )

                    # Add callback to track connection completion and emit events
                    connection_future.add_done_callback(
                        lambda f: self._on_connection_complete_with_events(
                            f, connection_id
                        )
                    )
                else:
                    # Failed to submit task
                    self._metrics_collector.record_connection_failure()
                    from pipedoc.connection_events import (
                        ConnectionEvent,
                        ConnectionEventType,
                    )

                    self._emit_event(ConnectionEventType.CONNECT_FAILURE, connection_id)

            except Exception as e:
                # Error in connection handling
                self._logger.error(
                    f"Error handling connection {connection_id}: {e}",
                    context=LogContext(
                        component=self._context.component,
                        operation="handle_incoming_connection",
                    ),
                    exc_info=True,
                )
                self._metrics_collector.record_connection_failure()
                from pipedoc.connection_events import (
                    ConnectionEvent,
                    ConnectionEventType,
                )

                self._emit_event(ConnectionEventType.CONNECT_FAILURE, connection_id)

        # Prepare new writer after releasing lock (always-ready pattern)
        if connection_future:
            self._prepare_ready_writer()

        return connection_future

    def _queue_connection(self, connection_id: str) -> Optional[Future]:
        """Queue a connection request when worker pool is at capacity."""
        try:
            # Create a future that will be resolved when the connection is processed
            timeout_future = Future()

            # Create queued connection
            queued_conn = QueuedConnection(
                connection_id=connection_id,
                timestamp=time.time(),
                timeout_future=timeout_future,
            )

            # Try to add to queue (non-blocking)
            try:
                self._connection_queue.put_nowait(queued_conn)

                # Log and emit queued event
                from pipedoc.connection_events import (
                    ConnectionEvent,
                    ConnectionEventType,
                )
                from pipedoc.app_logger import LogContext

                self._logger.info(
                    "Connection queued for processing",
                    context=LogContext(
                        component=self._context.component, operation="_queue_connection"
                    ),
                    connection_id=connection_id,
                    queue_depth=self._connection_queue.qsize(),
                    queue_max_size=self._queue_size,
                )

                self._emit_event(
                    ConnectionEventType.CONNECT_QUEUED,
                    connection_id,
                    metadata={"queue_depth": self._connection_queue.qsize()},
                )

                # Record queuing in metrics
                self._metrics_collector.record_connection_queued()

                # Set up timeout handling
                self._setup_connection_timeout(queued_conn)

                # Start queue processor if not running
                self._start_queue_processor()

                return timeout_future

            except Full:
                # Queue is full, reject connection
                from pipedoc.app_logger import LogContext

                self._logger.warning(
                    "Connection rejected - queue at capacity",
                    context=LogContext(
                        component=self._context.component, operation="_queue_connection"
                    ),
                    connection_id=connection_id,
                    queue_depth=self._connection_queue.qsize(),
                    queue_max_size=self._queue_size,
                )
                self._metrics_collector.record_connection_failure()
                from pipedoc.connection_events import (
                    ConnectionEvent,
                    ConnectionEventType,
                )

                self._emit_event(ConnectionEventType.CONNECT_FAILURE, connection_id)
                return None

        except Exception as e:
            # Error in queueing
            self._logger.error(
                f"Error queueing connection {connection_id}: {e}",
                context=LogContext(
                    component=self._context.component, operation="_queue_connection"
                ),
                exc_info=True,
            )
            self._metrics_collector.record_connection_failure()
            from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

            self._emit_event(ConnectionEventType.CONNECT_FAILURE, connection_id)
            return None

    def _setup_connection_timeout(self, queued_conn: QueuedConnection) -> None:
        """Set up timeout handling for a queued connection."""

        def timeout_handler():
            """Handle connection timeout."""
            try:
                # Try to remove from queue (may already be processed)
                with self._queue_lock:
                    # Mark as timed out in metrics
                    self._metrics_collector.record_connection_timeout()

                # Emit timeout event
                from pipedoc.connection_events import (
                    ConnectionEvent,
                    ConnectionEventType,
                )

                self._emit_event(
                    ConnectionEventType.CONNECT_TIMEOUT, queued_conn.connection_id
                )

                # Set exception on the future to indicate timeout
                if not queued_conn.timeout_future.done():
                    queued_conn.timeout_future.set_exception(
                        TimeoutError(
                            f"Connection {queued_conn.connection_id} timed out after {self._queue_timeout}s"
                        )
                    )
            except Exception as e:
                # Error in timeout handling - log but continue
                from pipedoc.app_logger import LogContext

                self._logger.error(
                    f"Error in connection timeout handler for {queued_conn.connection_id}: {e}",
                    context=LogContext(
                        component=self._context.component, operation="timeout_handler"
                    ),
                    exc_info=True,
                    connection_id=queued_conn.connection_id,
                )

        # Schedule timeout
        timer = threading.Timer(self._queue_timeout, timeout_handler)
        timer.daemon = True
        timer.start()

    def _start_queue_processor(self) -> None:
        """Start the background queue processor if not already running."""
        with self._state_lock:
            if not self._queue_processor_running and self._is_running:
                self._queue_processor_running = True
                try:
                    self._queue_processor_future = self._worker_pool.submit_task(
                        self._queue_processor_worker
                    )
                except Exception as e:
                    from pipedoc.app_logger import LogContext

                    self._logger.error(
                        f"Failed to start queue processor: {e}",
                        context=LogContext(
                            component=self._context.component,
                            operation="start_queue_processor",
                        ),
                        exc_info=True,
                    )
                    self._queue_processor_running = False

    def _queue_processor_worker(self) -> None:
        """Background worker that processes queued connections."""
        while self._queue_processor_running and self._is_running:
            try:
                # Wait for queued connection with timeout
                queued_conn = self._connection_queue.get(timeout=1.0)

                # Wait for worker pool capacity
                while not self._worker_pool.can_accept_task() and self._is_running:
                    if not self._queue_processor_running:
                        return
                    time.sleep(0.1)

                if not self._is_running:
                    return

                # Process the queued connection
                self._process_queued_connection(queued_conn)

            except Empty:
                # Timeout waiting for queue item - continue
                continue
            except Exception as e:
                # Handle errors in queue processing - log unexpected errors but continue
                # Note: queue.Empty is handled above and is expected
                from pipedoc.app_logger import LogContext

                self._logger.error(
                    f"Unexpected error in queue processor: {e}",
                    context=LogContext(
                        component=self._context.component,
                        operation="queue_processor_worker",
                    ),
                    exc_info=True,
                )
                continue

    def _process_queued_connection(self, queued_conn: QueuedConnection) -> None:
        """Process a connection that was waiting in the queue."""
        if queued_conn.timeout_future.done():
            # Connection already timed out or cancelled
            return

        wait_time = time.time() - queued_conn.timestamp

        try:
            # Emit dequeue event
            from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

            self._emit_event(
                ConnectionEventType.CONNECT_DEQUEUED,
                queued_conn.connection_id,
                metadata={"wait_time": wait_time},
            )

            # Submit connection handling task
            connection_future = self._worker_pool.submit_task(
                lambda: self._handle_connection_worker(queued_conn.connection_id)
            )

            if connection_future:
                # Record successful dequeue
                self._metrics_collector.record_connection_dequeued(wait_time)

                # Log successful dequeue
                from pipedoc.app_logger import LogContext

                self._logger.info(
                    "Connection dequeued for processing",
                    context=LogContext(
                        component=self._context.component,
                        operation="_process_queued_connection",
                    ),
                    connection_id=queued_conn.connection_id,
                    wait_time=wait_time,
                    queue_depth=self._connection_queue.qsize(),
                )

                # Set the result on the timeout future
                queued_conn.timeout_future.set_result("connection_handled")

                with self._connection_lock:
                    self._active_connections += 1
                    connection_future.add_done_callback(
                        lambda f: self._on_connection_complete_with_events(
                            f, queued_conn.connection_id
                        )
                    )
            else:
                # Failed to submit task
                self._metrics_collector.record_connection_failure()
                from pipedoc.connection_events import (
                    ConnectionEvent,
                    ConnectionEventType,
                )

                self._emit_event(
                    ConnectionEventType.CONNECT_FAILURE, queued_conn.connection_id
                )
                if not queued_conn.timeout_future.done():
                    queued_conn.timeout_future.set_exception(
                        RuntimeError("Failed to submit connection task")
                    )

        except Exception as e:
            # Error processing queued connection
            self._metrics_collector.record_connection_failure()
            from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

            self._emit_event(
                ConnectionEventType.CONNECT_FAILURE, queued_conn.connection_id
            )
            if not queued_conn.timeout_future.done():
                queued_conn.timeout_future.set_exception(e)

    def _prepare_ready_writer(self) -> None:
        """Prepare a ready writer for the always-ready pattern."""
        with self._state_lock:
            if not self._is_running:
                return

            # Don't create a new writer if one is already ready
            if (
                self._writer_ready
                and self._current_writer_future
                and not self._current_writer_future.done()
            ):
                return

            try:
                # Cancel previous writer if it exists
                if (
                    self._current_writer_future
                    and not self._current_writer_future.done()
                ):
                    self._current_writer_future.cancel()

                # Submit a background task that waits for incoming connections
                self._writer_id_counter += 1
                writer_id = self._writer_id_counter

                # Submit the ready writer worker to the thread pool
                self._current_writer_future = self._worker_pool.submit_task(
                    self._ready_writer_worker, writer_id
                )

                # Mark writer as ready
                self._writer_ready = True

            except Exception as e:
                self._writer_ready = False
                from pipedoc.app_logger import LogContext

                self._logger.error(
                    f"Failed to prepare ready writer: {e}",
                    context=LogContext(
                        component=self._context.component,
                        operation="_prepare_ready_writer",
                    ),
                    exc_info=True,
                )

    def _ready_writer_worker(self, writer_id: int) -> None:
        """Worker that waits ready to handle incoming connections."""
        # Simplified implementation that just marks the writer as ready
        # In a real implementation, this would use select() or poll() to monitor the pipe
        # For the always-ready pattern, we just need to indicate readiness
        return "ready"

    def _handle_connection_worker(self, connection_id: str) -> str:
        """Worker that handles an individual connection."""
        start_time = time.time()

        try:
            # Get content to serve
            content = ""
            if self._content_callback:
                content = self._content_callback()

            # Get pipe path
            pipe_path = self._pipe_resource.get_pipe_path()
            if not pipe_path:
                # In test scenarios, just simulate handling without actual pipe
                connection_time = time.time() - start_time
                self._metrics_collector.record_connection_success(connection_time)
                return "connection_handled"

            # Write content to pipe
            with open(pipe_path, "w") as pipe:
                pipe.write(content)
                pipe.flush()

            connection_time = time.time() - start_time
            self._metrics_collector.record_connection_success(connection_time)

            return "connection_handled"

        except Exception as e:
            # Error in connection handling
            self._metrics_collector.record_connection_failure()
            raise e

    def _on_connection_complete_lockfree(self, future: Future) -> None:
        """
        Deadlock-safe callback for connection completion tracking.

        CRITICAL: This callback uses a separate lock (_counter_lock) instead of
        _connection_lock to prevent ThreadPoolExecutor deadlock scenario:

        Without this fix:
        1. Main thread calls future.result() and waits
        2. Worker completes task, ThreadPoolExecutor runs this callback
        3. Callback tries to acquire _connection_lock
        4. DEADLOCK: Main thread waits for callback, callback waits for lock

        Solution: Use dedicated lock that doesn't compete with main operations.
        """
        with self._counter_lock:
            self._active_connections = max(0, self._active_connections - 1)

    def _on_connection_complete_with_events(
        self, future: Future, connection_id: str
    ) -> None:
        """Handle connection completion with event emission."""
        # Update connection count first
        self._on_connection_complete_lockfree(future)

        # Emit completion events
        try:
            result = future.result()
            # Connection succeeded
            from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

            self._emit_event(ConnectionEventType.CONNECT_SUCCESS, connection_id)
            # Note: DISCONNECT event could be emitted here if needed
        except Exception:
            # Connection failed
            from pipedoc.connection_events import ConnectionEvent, ConnectionEventType

            self._emit_event(ConnectionEventType.CONNECT_FAILURE, connection_id)

    def _on_connection_complete(self, future: Future) -> None:
        """Original callback (causes deadlock - kept for reference)."""
        with self._connection_lock:
            self._active_connections = max(0, self._active_connections - 1)

    def get_queue_metrics(self) -> Dict[str, Any]:
        """Get current queue metrics and statistics."""
        with self._queue_lock:
            return {
                "current_depth": self._connection_queue.qsize(),
                "max_size": self._queue_size,
                "total_queued": self._metrics_collector.get_metrics()[
                    "connections_queued"
                ],
                "timeout_count": self._metrics_collector.get_metrics()[
                    "connections_timeout"
                ],
            }

    def get_queue_state(self) -> Dict[str, Any]:
        """Get current queue state for testing and monitoring."""
        with self._queue_lock:
            # For FIFO testing, we'd need to track queue order
            # This is a simplified implementation
            return {
                "size": self._connection_queue.qsize(),
                "empty": self._connection_queue.empty(),
                "full": self._connection_queue.full(),
                "order": list(
                    range(self._connection_queue.qsize())
                ),  # Simplified for testing
            }

    def _get_current_writer_id(self) -> int:
        """Get the current writer ID for testing purposes."""
        return self._writer_id_counter
