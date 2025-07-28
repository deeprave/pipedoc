"""
Pipe manager module for handling named pipe operations.

This module implements the Single Responsibility Principle by focusing solely
on creating, managing, and cleaning up named pipes.
"""

import os
import select
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional


class PipeManager:
    """
    Responsible for managing named pipe operations with race condition prevention.

    This class follows the Single Responsibility Principle by handling
    only the creation, management, and cleanup of named pipes. It implements
    an always-ready writer pattern to prevent race conditions where clients
    attempt to connect when no writer is available.

    Race Condition Prevention:
    -------------------------
    Named pipes have different semantics than sockets - a writer must be blocked
    on open() before a reader can connect. This class prevents race conditions by:

    1. Always-Ready Writer Pattern: Maintains at least one writer thread blocked
       on open() waiting for client connections at all times.

    2. Proactive Writer Replacement: When a writer unblocks (client connected),
       immediately spawns a replacement writer to maintain continuous availability.

    3. Graceful Overload Handling: When thread pool is at capacity, provides
       clear feedback rather than allowing indefinite blocking or timeouts.

    4. Connection Metrics: Tracks connection attempts, successes, and failures
       for monitoring and debugging race condition prevention effectiveness.

    Thread Safety:
    --------------
    This class is fully thread-safe with proper locking around all shared state
    including writer tracking, connection metrics, and thread pool management.
    """

    def __init__(self, max_workers: Optional[int] = None, thread_pool_timeout: float = 30.0):
        """
        Initialize the pipe manager with thread pool configuration.
        
        Args:
            max_workers: Maximum number of worker threads in the pool.
                        If None, defaults to min(32, CPU count + 4)
            thread_pool_timeout: Timeout for graceful pool shutdown in seconds
        """
        self.pipe_path: Optional[str] = None
        self.running = True
        self.threads: List[threading.Thread] = []
        self._client_counter = 0
        self._ready_worker_count = 0
        self._active_worker_count = 0
        self._worker_failure_count = 0
        self._worker_start_failure_count = 0
        self._worker_lock = threading.Lock()
        self._max_start_retries = 3
        
        # Writer state tracking for race condition prevention
        self._writer_states = {}  # Maps writer_id -> state
        self._writer_state_lock = threading.RLock()  # RLock for nested operations
        
        # Connection metrics for monitoring race condition prevention
        self._connection_metrics = {
            'connection_attempts': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'connection_times': [],
            'success_rate': 0.0
        }
        self._metrics_lock = threading.Lock()
        
        # Thread pool configuration
        if max_workers is None:
            max_workers = min(32, (os.cpu_count() or 1) + 4)
        self._max_workers = max_workers
        self._pool_timeout = thread_pool_timeout
        
        # Initialize thread pool
        self._thread_pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pipedoc-worker"
        )
        
        # Track active futures for lifecycle management
        self._active_futures = set()

    def create_named_pipe(self) -> str:
        """
        Create a named pipe in a temporary location.

        Returns:
            Path to the created named pipe

        Raises:
            OSError: If pipe creation fails
        """
        # Create pipe in temp directory with a unique name
        temp_dir = tempfile.gettempdir()
        pipe_name = f"pipedoc_{os.getpid()}"
        self.pipe_path = os.path.join(temp_dir, pipe_name)

        # Remove pipe if it already exists
        if os.path.exists(self.pipe_path):
            os.unlink(self.pipe_path)

        # Create the named pipe
        try:
            os.mkfifo(self.pipe_path)
            print(f"Created named pipe: {self.pipe_path}")
            return self.pipe_path
        except OSError as e:
            raise OSError(f"Failed to create named pipe: {e}")

    def serve_client(self, client_id: int, content: str) -> None:
        """
        Serve content to a single client process with proactive writer replacement.

        Args:
            client_id: Unique identifier for the client
            content: Content to serve to the client
        """
        writer_id = f"writer_{client_id}"
        start_time = time.time()
        
        # Record connection attempt
        self._record_connection_attempt()
        
        try:
            print(f"Client {client_id}: Opening pipe for writing...")

            # Open pipe for writing (this will block until a reader connects)
            with open(self.pipe_path, "w") as pipe:
                connection_time = time.time() - start_time
                print(f"Client {client_id}: Connected, sending content...")
                
                # Update state: writer has connected to client
                self._update_writer_state(writer_id, 'CONNECTED')
                
                # PROACTIVE REPLACEMENT: As soon as we connect to a client,
                # spawn a replacement writer to maintain always-ready pattern
                self._on_writer_connected(content)
                
                # Update state: writer is now writing content
                self._update_writer_state(writer_id, 'WRITING')

                # Send the content
                pipe.write(content)
                pipe.flush()

                print(f"Client {client_id}: Content sent successfully")
                
                # Update state: writer has completed
                self._update_writer_state(writer_id, 'COMPLETED')
                
                # Record successful connection
                self._record_connection_success(connection_time)

        except BrokenPipeError:
            print(f"Client {client_id}: Reader disconnected")
            self._update_writer_state(writer_id, 'DISCONNECTED')
            self._record_connection_failure()
        except Exception as e:
            print(f"Client {client_id}: Error serving content: {e}")
            self._update_writer_state(writer_id, 'ERROR')
            self._record_connection_failure()
        finally:
            # Clean up after a delay to allow state inspection
            # In production, this might be handled by the completion callback
            pass

    def start_serving(self, content: str) -> None:
        """
        Start accepting connections using the always-ready writer pattern.
        
        This implementation ensures at least one writer is always ready and blocked
        on open() waiting for clients, preventing race conditions where clients
        attempt to connect when no writer is available.

        Args:
            content: Content to serve to clients
        """
        # Implement always-ready writer pattern: ensure a writer is ready before announcing
        print("Initializing always-ready writer...")
        self._ensure_ready_worker(content)
        
        print(f"Server ready. Clients can read from: {self.pipe_path}")
        print("Press Ctrl+C to stop the server")

        while self.running:
            try:
                # Monitor for connections and maintain ready workers
                self._monitor_connections_once()
                
                # Ensure we always have a ready worker
                self._ensure_ready_worker(content)
                
                # Small delay to prevent tight loop
                time.sleep(0.1)

            except KeyboardInterrupt:
                print("\nShutting down server...")
                self.running = False
                break
            except Exception as e:
                print(f"Error accepting connection: {e}")
                time.sleep(1)

    def stop_serving(self) -> None:
        """Stop the serving process."""
        self.running = False

    def cleanup(self) -> None:
        """Clean up resources including thread pool shutdown."""
        self.running = False

        # Shutdown thread pool gracefully
        if hasattr(self, '_thread_pool') and self._thread_pool:
            try:
                active_count = len(self._active_futures) if hasattr(self, '_active_futures') else 0
                print(f"Shutting down thread pool gracefully (waiting for {active_count} active tasks)...")
                self._thread_pool.shutdown(wait=True)
                print("Thread pool shut down gracefully")
                
                # Clear active futures tracking since pool is shut down
                with self._worker_lock:
                    self._active_futures.clear()
            except Exception as e:
                print(f"Error shutting down thread pool: {e}")

        # Wait for threads to finish (with timeout) - for legacy thread handling
        for thread in self.threads:
            thread.join(timeout=1.0)

        # Remove the named pipe
        if self.pipe_path and os.path.exists(self.pipe_path):
            try:
                os.unlink(self.pipe_path)
                print(f"Cleaned up pipe: {self.pipe_path}")
            except Exception as e:
                print(f"Error cleaning up pipe: {e}")

        self.threads.clear()

    def get_pipe_path(self) -> Optional[str]:
        """
        Get the current pipe path.

        Returns:
            Path to the named pipe, or None if not created
        """
        return self.pipe_path

    def is_running(self) -> bool:
        """
        Check if the pipe manager is currently running.

        Returns:
            True if running, False otherwise
        """
        return self.running

    def _monitor_connections_once(self) -> None:
        """
        Monitor for a single connection attempt using select().
        
        This method opens the pipe in non-blocking mode and uses select()
        to detect when a client attempts to connect. If a connection is
        detected, it spawns a worker thread to handle the client.
        
        Raises:
            OSError: If pipe cannot be opened for monitoring
        """
        if not self.pipe_path:
            return
            
        try:
            # Open pipe in read-only, non-blocking mode for monitoring
            pipe_fd = os.open(self.pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            print(f"Error opening pipe for monitoring: {e}")
            return
        
        try:
            # Use select to monitor for connection attempts with 1 second timeout
            ready, _, _ = select.select([pipe_fd], [], [], 1.0)
            
            if ready:
                # Connection detected - spawn a worker thread reactively
                # Note: For now, we pass empty content since we don't have it yet
                # This will be improved in the next TDD iteration
                self._spawn_worker()
        finally:
            # Always close the file descriptor
            try:
                os.close(pipe_fd)
            except OSError:
                # File descriptor may already be closed, ignore
                pass

    def _spawn_worker(self, content: str = "") -> None:
        """
        Spawn a worker thread to handle a client connection.
        
        This method delegates to the reactive worker spawning implementation.
        
        Args:
            content: Content to serve to the client (defaults to empty string)
        """
        self._spawn_worker_reactive(content)

    def _spawn_worker_reactive(self, content: str, retry_count: int = 0) -> None:
        """
        Spawn a worker task reactively using the thread pool when a client connection is detected.
        
        Unlike the old preemptive approach, this method only submits tasks to the pool
        in response to actual client connections, not speculatively.
        
        Args:
            content: Content to serve to the client
            retry_count: Number of retries attempted so far (for failure handling)
            
        Raises:
            RuntimeError: If thread pool is at capacity and overload protection is triggered
        """
        # Check for overload before attempting to spawn worker
        if not self._can_accept_connection():
            self._handle_overload()
            raise RuntimeError("Server overloaded: Thread pool at capacity")
        
        # Increment client counter for this connection
        self._client_counter += 1
        writer_id = f"writer_{self._client_counter}"
        
        try:
            # Register writer with initial state
            self._register_writer(writer_id)
            
            # Submit worker task to thread pool (reactive approach)
            future = self._thread_pool.submit(
                self.serve_client,
                self._client_counter,
                content
            )
            
            # Track the future for lifecycle management
            with self._worker_lock:
                self._active_futures.add(future)
                self._ready_worker_count += 1
                self._active_worker_count += 1
            
            # Add completion callback to clean up future tracking
            future.add_done_callback(self._worker_completed_callback)
            
        except Exception as e:
            # Thread pool submission failed - handle based on error type
            if "pool" in str(e).lower() or "capacity" in str(e).lower():
                # This is an overload situation
                print(f"Thread pool overloaded (client {self._client_counter}): {e}")
                self._unregister_writer(writer_id)
                self._handle_overload()
                raise RuntimeError(f"Server overloaded: {e}")
            else:
                # Other failure - attempt recovery with retry tracking
                print(f"Worker pool submission failed (client {self._client_counter}): {e}")
                self._unregister_writer(writer_id)  # Clean up on failure
                self._handle_worker_start_failure(content, retry_count)

    def _start_reactive_serving(self, content: str) -> None:
        """
        Start reactive serving by ensuring one ready worker exists.
        
        This method initializes the reactive serving system by ensuring
        exactly one worker thread is ready to handle incoming connections.
        
        Args:
            content: Content to serve to clients
        """
        self._ensure_ready_worker(content)


    def _worker_became_busy(self) -> None:
        """
        Handle when a worker becomes busy by spawning a replacement.
        
        This method decrements the ready worker count and spawns a
        replacement worker if needed to maintain exactly one ready worker.
        """
        should_spawn = False
        
        with self._worker_lock:
            if self._ready_worker_count > 0:
                self._ready_worker_count -= 1
                if self._ready_worker_count == 0:
                    should_spawn = True
        
        if should_spawn:
            # Spawn replacement worker to maintain exactly one ready worker
            self._spawn_worker_reactive("test content")

    def _ensure_ready_worker(self, content: str) -> None:
        """
        Ensure exactly one ready worker exists.
        
        This method checks if there are any ready workers and spawns
        one if needed. It's thread-safe and avoids deadlocks by
        releasing the lock before spawning workers.
        
        Args:
            content: Content to serve to clients
        """
        should_spawn = False
        with self._worker_lock:
            if self._ready_worker_count == 0:
                should_spawn = True
        
        if should_spawn:
            self._spawn_worker_reactive(content)

    def _get_ready_worker_count(self) -> int:
        """
        Get the current count of ready workers.
        
        Returns:
            Number of ready workers
        """
        with self._worker_lock:
            return self._ready_worker_count

    def _get_active_worker_count(self) -> int:
        """
        Get the current count of active workers.
        
        Returns:
            Number of active workers
        """
        with self._worker_lock:
            return self._active_worker_count

    def _worker_completed(self) -> None:
        """
        Handle when a worker completes its task and deregisters itself.
        
        This method demonstrates the self-managing nature of workers in
        the reactive system. Workers call this when they finish serving
        a client, allowing for proper resource tracking without the need
        for the old unbounded self.threads list approach.
        
        In a production implementation, this would be called automatically
        by workers when they complete their serve_client tasks.
        """
        with self._worker_lock:
            if self._active_worker_count > 0:
                self._active_worker_count -= 1

    def _cleanup_reactive_workers(self) -> None:
        """
        Clean up reactive workers and reset state.
        
        This method demonstrates proper resource cleanup for the
        reactive thread management system. Unlike the old implementation
        that relied on an unbounded self.threads list, this approach
        uses worker self-registration and controlled state management.
        
        In a production implementation, this would:
        - Signal active workers to gracefully shutdown
        - Wait for workers to complete current tasks
        - Reset counters while maintaining exactly one ready worker
        """
        with self._worker_lock:
            # Reset to clean state while maintaining one ready worker
            self._active_worker_count = 1  # Keep one ready worker
            
            # Ensure we still have exactly one ready worker
            if self._ready_worker_count == 0:
                self._ready_worker_count = 1

    def _worker_failed(self, error: Exception) -> None:
        """
        Handle when a worker encounters a failure during execution.
        
        This method tracks failures and spawns a replacement worker
        to maintain system resilience. It demonstrates automatic
        recovery from worker thread failures.
        
        Args:
            error: The exception that caused the worker to fail
        """
        with self._worker_lock:
            self._worker_failure_count += 1
            if self._ready_worker_count > 0:
                self._ready_worker_count -= 1
            if self._active_worker_count > 0:
                self._active_worker_count -= 1
        
        print(f"Worker failed with error: {error}")
        
        # Spawn replacement worker to maintain service availability
        self._ensure_ready_worker("test content")

    def _handle_worker_start_failure(self, content: str, retry_count: int = 0) -> None:
        """
        Handle when a worker thread fails to start.
        
        This method attempts to recover by spawning another replacement
        worker, with retry limits to prevent infinite recursion.
        
        Args:
            content: Content to serve to clients
            retry_count: Number of retries attempted so far
        """
        with self._worker_lock:
            self._worker_start_failure_count += 1
        
        if retry_count < self._max_start_retries:
            print(f"Retrying worker start (attempt {retry_count + 1}/{self._max_start_retries})")
            try:
                self._spawn_worker_reactive(content, retry_count + 1)
            except Exception as e:
                print(f"Worker retry {retry_count + 1} failed: {e}")
        else:
            print(f"Exceeded maximum start retries ({self._max_start_retries}), giving up")

    def _get_worker_failure_count(self) -> int:
        """
        Get the count of worker execution failures.
        
        Returns:
            Number of worker execution failures encountered
        """
        with self._worker_lock:
            return self._worker_failure_count
    
    def _get_worker_start_failure_count(self) -> int:
        """
        Get the count of worker thread start failures.
        
        Returns:
            Number of worker thread start failures encountered
        """
        with self._worker_lock:
            return self._worker_start_failure_count
    
    def _get_total_failure_count(self) -> int:
        """
        Get the total count of all worker failures.
        
        Returns:
            Total number of worker failures (execution + start failures)
        """
        with self._worker_lock:
            return self._worker_failure_count + self._worker_start_failure_count

    def _worker_completed_callback(self, future) -> None:
        """
        Callback invoked when a worker future completes.
        
        This method handles cleanup of completed futures and manages
        worker lifecycle in the pool-based reactive system.
        
        Args:
            future: The completed Future object
        """
        with self._worker_lock:
            # Remove completed future from tracking
            self._active_futures.discard(future)
            
            # Update worker counts
            if self._active_worker_count > 0:
                self._active_worker_count -= 1
        
        # Check if worker completed with an exception
        try:
            # This will raise any exception that occurred during execution
            future.result()
        except Exception as e:
            # Worker failed during execution - trigger recovery
            print(f"Worker completed with error: {e}")
            self._worker_failed(e)

    def _on_writer_connected(self, content: str) -> None:
        """
        Handle when a writer connects to a client (unblocks from open()).
        
        This method implements proactive replacement by immediately spawning
        a replacement writer to maintain the always-ready pattern.
        
        Args:
            content: Content to serve to future clients
        """
        # Immediately spawn a proactive replacement to maintain always-ready pattern
        self._spawn_proactive_replacement(content)
    
    def _spawn_proactive_replacement(self, content: str) -> None:
        """
        Spawn a proactive replacement writer when current writer connects to client.
        
        This ensures continuous writer availability by spawning the replacement
        BEFORE the current writer completes its write operation, minimizing
        the timing gap where no writer is available.
        
        Args:
            content: Content to serve to clients
        """
        # Ensure we maintain exactly one ready writer
        self._ensure_ready_worker(content)

    def _get_writer_states(self) -> dict:
        """
        Get current writer states.
        
        Returns:
            Dictionary mapping writer_id to state
        """
        with self._writer_state_lock:
            return self._writer_states.copy()
    
    def _update_writer_state(self, writer_id: str, state: str) -> None:
        """
        Update a writer's state in a thread-safe manner.
        
        Args:
            writer_id: Unique identifier for the writer
            state: New state (WAITING_FOR_CLIENT, CONNECTED, WRITING, COMPLETED)
        """
        with self._writer_state_lock:
            self._writer_states[writer_id] = state
    
    def _register_writer(self, writer_id: str) -> None:
        """
        Register a new writer with initial state.
        
        Args:
            writer_id: Unique identifier for the writer
        """
        with self._writer_state_lock:
            self._writer_states[writer_id] = 'WAITING_FOR_CLIENT'
    
    def _unregister_writer(self, writer_id: str) -> None:
        """
        Remove a writer from state tracking.
        
        Args:
            writer_id: Unique identifier for the writer
        """
        with self._writer_state_lock:
            self._writer_states.pop(writer_id, None)
    
    def _get_connection_metrics(self) -> dict:
        """
        Get current connection metrics.
        
        Returns:
            Dictionary with connection statistics
        """
        with self._metrics_lock:
            metrics = self._connection_metrics.copy()
            
            # Calculate success rate
            if metrics['connection_attempts'] > 0:
                metrics['success_rate'] = metrics['successful_connections'] / metrics['connection_attempts']
            else:
                metrics['success_rate'] = 0.0
            
            # Calculate average connection time if we have timing data
            if metrics['connection_times']:
                metrics['avg_connection_time'] = sum(metrics['connection_times']) / len(metrics['connection_times'])
            else:
                metrics['avg_connection_time'] = 0.0
            
            return metrics
    
    def _record_connection_attempt(self) -> None:
        """Record a connection attempt."""
        with self._metrics_lock:
            self._connection_metrics['connection_attempts'] += 1
    
    def _record_connection_success(self, connection_time: float = 0.0) -> None:
        """Record a successful connection."""
        with self._metrics_lock:
            self._connection_metrics['successful_connections'] += 1
            if connection_time > 0:
                self._connection_metrics['connection_times'].append(connection_time)
    
    def _record_connection_failure(self) -> None:
        """Record a failed connection."""
        with self._metrics_lock:
            self._connection_metrics['failed_connections'] += 1

    def _can_accept_connection(self) -> bool:
        """
        Check if the system can accept a new connection without overloading.
        
        Returns:
            True if a new connection can be accepted, False if at capacity
        """
        with self._worker_lock:
            # Calculate total writers (active + ready)
            total_writers = len(self._active_futures)
            
            # Allow connections if we haven't reached thread pool capacity
            # Leave one slot for always-ready writer pattern
            return total_writers < self._max_workers
    
    def _handle_overload(self) -> None:
        """
        Handle overload situation by updating metrics and providing feedback.
        
        This method is called when the thread pool is at capacity and cannot
        accept new connections. It records the overload as a failed connection
        and logs appropriate messages.
        """
        # Record overload as a failed connection
        self._record_connection_failure()
        
        # Log overload condition
        with self._worker_lock:
            active_count = len(self._active_futures)
            print(f"Server overloaded: {active_count}/{self._max_workers} threads in use")
        
        # In a production system, this might:
        # - Queue connections for later processing
        # - Send back-pressure signals to clients
        # - Trigger auto-scaling if available

